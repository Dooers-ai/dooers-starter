# Implementation Plan: Fix `dooers-starter` deploy step

**Date:** 2026-06-24
**Branch:** `feat/fix-deploy-step`
**Scope:** Make `dooers-starter` deploy successfully on the current `dooers-push` platform.
Platform-side work (managed DB provisioning, Studio secret injection) is **out of scope** — see
[Out of scope](#out-of-scope).

---

## Problem

`dooers-agent-deploy-test` (a minimal stateless agent) deploys reliably via `dooers push`, while
teams using `dooers-starter` cannot get a successful deploy. Investigation showed this is **not** a
CLI-version issue and **not** one bug — the starter hits a stack of independent walls, each of which
alone fails the deploy. All of them surface in Cloud Run as the same confusing symptom:
*"container failed to start and listen on PORT 8080."*

The working test agent was built to match the platform's **real** contract (`.env` uploaded → env
vars; stateless; listen on `$PORT`). The starter and its docs assume an **aspirational** contract
(Studio-injected secrets, managed Postgres, fixed port) that `dooers-push` does not implement today.

## Root-cause findings

| # | Finding | Evidence | Why it blocks deploy |
|---|---------|----------|----------------------|
| 1 | Secrets only reach the runtime via `.env` in the uploaded archive; the starter ships **no** `.env` and its docs say not to use one | CLI `ignore.py` does not exclude `.env`; `dooers-push` `cloudbuild.py` parses `.env`/`env.{env}`; `provisioner.py` is a stub | `config.py:_validate()` runs at import and `sys.exit(1)` on missing `OPENAI_API_KEY` (default `RAG_PIPELINE=openai`) → container never listens |
| 2 | Dockerfile hardcodes port 8005; Cloud Run injects `PORT=8080` and probes it | `Dockerfile` `CMD [... "--port", "8005"]`; `dooers-push` does not pass `--port` to `gcloud run deploy` | Container listens on 8005, platform probes 8080 → readiness fails → deploy fails |
| 3 | Lifespan eagerly connects to Postgres + runs migrations + SDK init; nothing is provisioned | `main.py` lifespan `await init_pool()` / `ensure_initialized()`; defaults `localhost:5432` | Connection refused → lifespan raises → uvicorn never serves → crash loop |
| 4 | Shipped `dooers.yaml` lacks required `agent_id` + `organization_id` | protocol-v2 schema `extra="forbid"`, fields required | `dooers push`/`validate` fail before upload unless `dooers agents create` was run first |
| 5 | Misleading docs: "the CLI does not upload `.env`; set secrets in the Studio/panel" | `docs/08-deploy.md`, `README.md`, recipe | Teams follow docs → no secrets in archive → Finding 1 |
| 6 | `dooers-agents-server>=0.12.0` resolvability | local workspace pkg is `dooers-agents` 0.11.0 | If the published package isn't reachable at `>=0.12.0`, the Docker build fails — **verify** |

## Fix design (starter-side)

The strategy mirrors the working test agent: **fail open, not closed.** The container must always
boot and pass its readiness check; secret/DB-dependent features degrade at request time until the
creator wires them up via `.env` + a reachable Postgres.

### Changes

1. **`Dockerfile` — listen on `$PORT`** (Finding 2)
   - `CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers"]`
   - `EXPOSE 8080`; drop `ENV HTTP_PORT=8005`. `--proxy-headers` because the agent sits behind the LB.

2. **`src/config.py` — don't `sys.exit` at import** (Finding 1)
   - New `CONFIG_STRICT` setting (default `false`). When `false`, configuration problems are logged
     and startup continues (degraded). When `true` (local/CI), they remain fatal.

3. **`src/main.py` — resilient lifespan** (Finding 3)
   - Wrap `agent_server.ensure_initialized()` and `init_pool()` in `try/except` that logs and
     continues, so a missing/unreachable DB degrades chat/RAG instead of crash-looping the service.
     Shutdown steps are likewise guarded.

4. **`dooers.yaml` — document required identity fields** (Finding 4)
   - Header comment explaining `agent_id`/`organization_id` come from `dooers agents create` and are
     required before the first push.

5. **Docs corrections** (Findings 1, 2, 4, 5) — `README.md`, `docs/08-deploy.md`,
   `docs/recipes/deploy-with-dooers-push.md`, `.env.example`:
   - `.env` **is** uploaded by `dooers push` and is the only way secrets reach the runtime today.
   - The "Port mismatch → EXPOSE 8005" troubleshooting row is replaced with "listen on `$PORT`".
   - Add the `dooers agents create` step to prerequisites/checklists.
   - New troubleshooting rows for the two real failure modes (PORT listen failure; 503/crash-loop
     from missing `.env` secrets).

## Out of scope

These are real gaps but belong to `dooers-push`, not the starter, and are a **separate task**:

- **Managed Postgres provisioning** — `ProvisionerStep` is a stub (`needs_db` always `false`). Until
  it provisions a DB and injects `AGENT_DATABASE_*`, creators must bring their own reachable Postgres.
- **Studio/panel secret injection** — no such mechanism exists; `.env` upload is the only path.

The starter changes above make the agent deploy *given* a creator-supplied `.env` + Postgres; they do
not add platform infrastructure.

## Verification

- [ ] `python -m py_compile src/config.py src/main.py` (syntax)
- [ ] `uv run poe check` (ruff) passes
- [ ] Local boot with no `OPENAI_API_KEY` and no DB: container starts, `GET /health` → `200`
      (degraded), logs show the warnings rather than a crash. (`CONFIG_STRICT=false` default.)
- [ ] `CONFIG_STRICT=true` with missing key still `sys.exit(1)` (local guardrail preserved).
- [ ] `docker build` + run with `PORT=8080`: process binds 8080, `/health` reachable.
- [ ] End-to-end: `dooers agents create` → fill `.env` (key + reachable Postgres) → `dooers push`
      → deploy reports succeeded and the URL responds.

## Risks

- **Finding 6 (dependency):** confirm `dooers-agents-server>=0.12.0` resolves from the index the
  Docker build uses. If it does not, the build fails regardless of the changes here — track
  separately. No version change is made in this PR.
- **Degraded-mode masking:** booting on missing infra means a misconfigured agent deploys "green" but
  doesn't function. Mitigated by loud `WARNING`/`exception` logs and the new troubleshooting rows;
  `CONFIG_STRICT=true` restores fail-fast for local/CI.
