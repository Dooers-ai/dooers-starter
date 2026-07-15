# AGENTS.md

Instructions for AI coding agents working in this repository.

## Primary skill

**Read [skills.md](skills.md) first** — canonical workflow for building Dooers-connected agents and integrations, including **best practices** (credentials ask, test-before-push, role/channel workflows).

If the user links `skills.md` from GitHub or asks for a Dooers agent, follow that file end-to-end.

## Project

Official **Dooers agent starter kit** — FastAPI service using `dooers-agents-server[dooers,observability]>=0.16.1` (charts, reasoning, OTel).

## Read before coding

1. [docs/01-anatomy.md](docs/01-anatomy.md) — architecture
2. [docs/02-sdk-contract.md](docs/02-sdk-contract.md) — handler API
3. [.cursor/rules/dooers-agent.mdc](.cursor/rules/dooers-agent.mdc) — constraints
4. [docs/09-charts.md](docs/09-charts.md) / [docs/10-observability.md](docs/10-observability.md) when touching BI or traces

## Commands

```bash
uv sync --extra dev
uv run poe check    # required before suggesting push
uv run poe dev      # local server :8005 (optional qualitative; ngrok → Messages URL)
dooers validate     # optional pre-push check
dooers push         # deploy (creator runs after dooers login)
```

Deploy guide: [docs/08-deploy.md](docs/08-deploy.md)  
Deploy recipe (AI prompt): [docs/recipes/deploy-with-dooers-push.md](docs/recipes/deploy-with-dooers-push.md)

## Extension pattern

New business domain → new file in `src/modules/agent/capabilities/` + handoff in `workflow.py`.

When integrations need accounts/keys: **ask** the user (account exists? env vs settings vs chat form? auth formats) before wiring secrets.

When audiences differ: branch capabilities by `incoming.context.user.organization_role` / `workspace_role` and/or `incoming.context.channel`.

Do not modify the published SDK packages. Stay within this starter and public Dooers packages.
