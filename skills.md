---
name: dooers-agent
description: >-
  Builds AI agents on the Dooers platform using dooers-agents-server SDK
  (≥0.16: charts, reasoning, OpenTelemetry), capabilities architecture, RAG,
  WhatsApp, forms, uploads, and dooers push deploy. Use when the user asks to
  create a Dooers agent, connect an integration (Gmail, Slack, ERP, etc.) to
  Dooers, deploy with dooers push, or references dooers-starter or skills.md
  from Dooers-ai.
disable-model-invocation: true
---

# Dooers Agent Skill

Build production agents that run on **Dooers** (chat UI, Studio, WhatsApp, threads) using the public starter kit and SDK — without reimplementing the platform.

**Starter repo:** `https://github.com/Dooers-ai/dooers-starter`  
**This skill:** `skills.md` in that repo (you may be reading a copy or the live file).

**Public packages only:** `dooers-agents-server`, `dooers-agents-client`, `dooers-cli`, and this starter. Do not reference private Dooers repositories in docs or code.

**SDK baseline:** `dooers-agents-server[dooers,observability]>=0.16.1` (charts, reasoning, OTel).

---

## When to apply this skill

Apply when the user wants to:

- Create a new agent connected to Dooers
- Add an integration (Gmail, calendar, CRM, database, API…) to a Dooers agent
- Use Dooers services: chat threads, RAG, forms, charts, uploads, WhatsApp, dispatch, observability
- Deploy with `dooers push`

**User prompt example:**

> Crie um agente conectado ao meu Gmail com base no skill Dooers.

Parse: domain = Gmail + Dooers platform wiring from this skill.

---

## Golden rules

1. **Start from the starter** — clone `dooers-starter` or match its layout exactly.
2. **One handler** — `dooers_agent_handler` in `agent.py`; async generator with `yield send.*`.
3. **Capabilities per domain** — `src/modules/agent/capabilities/<name>.py` + handoff in `workflow.py`.
4. **SDK for persistence** — `dooers-agents-server` (`from dooers.agents.server import ...`); never roll your own thread DB.
5. **Secrets in Studio/env** — never commit `.env`, `env.prod`, OAuth JSON, or service account keys.
6. **Managed DB deploy** — when `database.type: dooers`, set `AGENT_DATABASE_TYPE=dooers` and `APP_POSTGRES_POOL_ENABLED=false` in `env.prod`; never put `GOOGLE_APPLICATION_CREDENTIALS` or `AGENT_DATABASE_HOST=localhost` in `env.prod`.
7. **Use only public packages** — `dooers-agents-server`, `dooers-agents-client`, `dooers-cli`, and this starter. Do not reference or import private Dooers repositories.
8. **External services need onboarding** — when you add an integration that requires an account/API key/OAuth/billing, you MUST ask the user how they want to supply credentials (env vs settings vs chat form), guide them through the auth formats the tool supports, and never invent or hardcode keys. See [Best practices](#best-practices-for-developer-agents) and [docs/recipes/external-service-credentials.md](docs/recipes/external-service-credentials.md).
9. **Test before push** — unit checks (`poe check`), build verification, and optionally qualitative local testing (`poe dev` ± ngrok) before guiding `dooers push`.
10. **Audience-aware workflows** — prefer distinct capabilities/workflows keyed by `organization_role` / `workspace_role` and/or `channel` (e.g. analytics & agent config tools only for `owner`/`manager`).

---

## Best practices for developer agents

These rules apply to **AI agents that create or extend Dooers agents for end users**.

### 1. Credentials & paid / authenticated tools

Whenever an integration needs a subscription, account, API key, OAuth, or other auth:

1. **Ask the user first** whether they already have an account on that service.
2. **Ask how they want to store credentials**, offering the platform options:
   - **Env vars** (`.env` / `env.prod`) — good for deploy-time secrets that rarely change
   - **Agent settings schema** (`SettingsField` PASSWORD/TEXT in `schemas.py`) — editable in Studio without redeploy
   - **Chat form capture** — `yield send.form(...)` + `await settings.set(...)` when a key is missing at runtime
   - Combinations are fine (e.g. settings + form fallback)
3. **Guide auth formats** the tool actually supports (API key, Bearer, Basic, OAuth refresh, service account JSON, webhook HMAC, etc.): where to create them, required scopes/permissions, and billing/plan caveats.
4. Prefer **settings fields + runtime form** for creator-owned keys so values can be rotated without a new push. Full pattern: [docs/recipes/external-service-credentials.md](docs/recipes/external-service-credentials.md).

Never invent, scrape, or hardcode secrets.

### 2. Test locally before `dooers push`

Before suggesting deploy:

| Check | Command / action |
|-------|------------------|
| Lint / unit-style static checks | `uv run poe check` (and any project tests if present) |
| Build sanity | Ensure the app imports/starts; Docker build if the user will push a custom image |
| Qualitative (optional) | `uv run poe dev` and exercise the flow in chat |
| Expose to local Dooers | Optionally run **ngrok** (or similar) on the agent port and set the Studio Messages URL to the ngrok `wss://…/ws` against a **local Dooers platform** |

Only after these pass should you guide `dooers login && dooers push`.

### 3. Distinct workflows by audience (role + channel)

Agents may expose **different workflows / capabilities** for different audiences. Use SDK context:

| Signal | Examples | Typical use |
|--------|----------|-------------|
| `incoming.context.user.organization_role` | `owner`, `manager`, `member` | Owners/managers: analytics (`send.chart`), agent configuration tools, admin handoffs |
| `incoming.context.user.workspace_role` | `manager`, `member` | Workspace-level admin tools |
| `incoming.context.channel` | `dooers-platform`, `whatsapp`, … | Shorter replies / no forms on WhatsApp; full BI UI on web |

Example policy: register an analytics capability only when `organization_role in ("owner", "manager")`, or branch cortex instructions so members get task help while managers get dashboards and settings.

---

## Workflow (new agent)

Copy this checklist and track progress:

```
- [ ] 1. Clone starter (or verify project matches layout)
- [ ] 2. Rename in dooers.yaml + API_AGENT_NAME
- [ ] 3. Ask user about external credentials (account? env vs settings vs form? auth format)
- [ ] 4. Implement domain capability + tools (role/channel-aware if needed)
- [ ] 5. Register handoff in workflow.py
- [ ] 6. Add creator settings in schemas.py (API keys, OAuth fields)
- [ ] 7. uv run poe check (+ optional poe dev / ngrok qualitative test)
- [ ] 8. Guide user: dooers login && dooers push
- [ ] 9. Guide user: Studio Messages URL + runtime API key + LLM settings
```

### Step 1 — Bootstrap

```bash
git clone https://github.com/Dooers-ai/dooers-starter.git my-agent
cd my-agent
uv sync --extra dev
cp .env.example .env
```

If the user already has a repo open, skip clone and edit in place.

### Step 2 — Project layout (do not deviate)

```
src/main.py                      # FastAPI: /ws, /uploads, /settings-upload, /whatsapp/inbound
src/modules/agent/agent.py       # Handler: dooers_agent_handler
src/modules/agent/workflow.py    # Runner + handoffs
src/modules/agent/capabilities/  # One file per domain
src/modules/agent/schemas.py     # Studio settings UI
src/modules/external/            # Third-party API clients (Gmail, etc.)
dooers.yaml                      # Blueprint metadata for CLI
Dockerfile                       # Production image
```

### Step 3 — Handler contract

```python
async def dooers_agent_handler(incoming, send, memory, analytics, settings):
    yield send.run_start()
    agent_settings = await settings.get_all()
    # ... validate, audio/images, form_data handling
    out = await run_workflow(incoming=incoming, send=send, memory=memory, ...)
    yield send.text(out["reply"], author=...)
    yield send.run_end()
```

Every turn: `run_start` → events → `run_end`. Each `yield send.*` is stored in the thread and shown in the UI.

### Step 4 — Capability + handoff

```python
# capabilities/gmail.py
from agents import Agent, function_tool

@function_tool
async def list_recent_emails(query: str = "is:unread", max_results: int = 5) -> str:
    """List recent Gmail messages matching query."""
    ...

async def create_gmail_capability(agent_id: str, agent_settings: dict) -> Agent:
    return Agent(
        name="gmail",
        instructions="You help with email. Use tools for inbox actions.",
        tools=[list_recent_emails, ...],
        handoff_description="Email: read, search, draft, send via Gmail.",
    )
```

```python
# workflow.py — in _create_additional_capabilities
gmail = await create_gmail_capability(agent_id, agent_settings)
return [gmail]
# cortex.handoffs.append(gmail) happens in _execute_agent_workflow
```

### Step 5 — External integration (pattern)

Put OAuth/API clients in `src/modules/external/<service>/`:

```
external/gmail/
  client.py      # Gmail API wrapper, reads tokens from agent_settings
  auth.py        # OAuth refresh if needed
```

**Before coding credentials storage**, ask the user (see [Best practices](#best-practices-for-developer-agents)):

1. Do they already have an account on the service?
2. Prefer env vars, Studio settings fields, chat form capture, or a mix?
3. Which auth formats does the tool support (API key, OAuth, service account, …)?

Default recommendation when the user is unsure: **PASSWORD `SettingsField` + runtime chat form** (no redeploy to rotate).

```python
async def create_gmail_capability(agent_id, agent_settings):
    client = GmailClient.from_settings(agent_settings)
    ...
```

Add `SettingsField` entries (PASSWORD for tokens, TEXT for client id) with `visibility=CREATOR`.

**Credential onboarding is required for any service with an account/key/OAuth/billing:**

- **Ask + tell the requester** (do not do it for them): create an account on `<service>`, where to generate the
  key(s) (panel path + link), the minimum scopes/permissions, and any paid plan/billing requirement.
- **Store** each credential per the user's chosen option (env and/or PASSWORD `SettingsField`).
- **Request missing keys at runtime** when using settings — check `agent_settings`; if missing,
  `yield send.form(...)`, then `await settings.set(field_id, value)`. Do not crash on missing keys — degrade the
  affected integration only.

Full pattern + code: [docs/recipes/external-service-credentials.md](docs/recipes/external-service-credentials.md).

### Step 6 — Forms / charts / reasoning (if UI output needed)

- Forms: tool returns `{"requiresForm": true}` OR handler yields `send.form(...)` — see `capabilities/feedback.py`
- Charts: `yield send.chart(chart_type=..., data=..., x_key=..., y_keys=...)` — see [docs/09-charts.md](docs/09-charts.md); smoke with `/test-chart-all`
- Reasoning: `yield send.reasoning("…")` for collapsible thinking in the UI (not sent to LLM history)

### Step 7 — Lint, build, optional local qualitative test

```bash
uv run poe check          # required before suggesting push
uv run poe dev            # optional qualitative — chat via Studio/local client
# optional: ngrok http 8005 → set Messages URL to wss://<ngrok>/ws against local Dooers
```

Do **not** jump straight to `dooers push` without at least `poe check` succeeding.
---

## How the agent is exposed (channels)

One handler serves **all entry points**. Choose how users reach the agent:

| Mode | Entry | Agent code | Published via Dooers platform |
|------|-------|------------|-------------------------------|
| **Dooers UI** | `WebSocket /ws` (root; `USE_API_PREFIX=false`) | `agent_server.handle(ws, handler)` — already in starter | Studio Messages URL + hire in team |
| **Public chat** | Same `/ws` — visitors use a shareable link | **No extra routes** — platform hosts the public UI | Workspace → enable Public Chats → Create link |
| **External channels** | HTTP route → `agent_server.dispatch(...)` | Add route (e.g. `/whatsapp/inbound`) + call `dispatch` with `channel` + `channel_meta` | WhatsApp: connect instance in workspace channels |

**Rule:** never fork the handler. UI, public chat, WhatsApp, and custom webhooks all call `dooers_agent_handler`.

- Public chat: platform publishes URL; agent only needs working `/ws`.
- Custom CRM/webhook: you add `POST /hooks/...` and `dispatch(channel="api", ...)`.
- WhatsApp: starter includes `/whatsapp/inbound`; platform provisions inbound URL.

Full guide: `docs/07-channels.md`.

---

## Dooers services map

Use these platform features — do not reimplement:

| Need | How |
|------|-----|
| Dooers dashboard chat | WebSocket `/ws` — `AgentServer.handle()` |
| Public chat links (external visitors) | Same `/ws` — link created in Dooers workspace (no extra agent route) |
| Chat + threads | SDK persists all channels in one thread store |
| History | `memory.get_history(format="openai_responses")` |
| Creator settings UI | `build_settings_schema()` in `schemas.py` |
| Knowledge / RAG | `POST /settings-upload` + `dooers_file_search_*` tools |
| Chat attachments | `POST /uploads` → `ref_id`; optional `persist_chat_attachments` |
| Interactive forms | `send.form()` + `incoming.form_data` |
| BI charts in chat | `send.chart(...)` — rendered by app-web (see `docs/09-charts.md`) |
| Reasoning blocks | `send.reasoning(...)` |
| Role / channel routing | `incoming.context.user.*_role`, `incoming.context.channel` |
| OpenTelemetry traces | Extra `[observability]` — auto export after seed (`docs/10-observability.md`) |
| WhatsApp | `POST /whatsapp/inbound` → `dispatch(channel="whatsapp")` |
| Custom external channel | Your HTTP route → `dispatch(channel="...", channel_meta={...})` |
| Proactive / webhooks | `agent_server.dispatch(handler, agent_id, message=..., channel="api")` |
| Deploy | `dooers push` (reads `dooers.yaml` + `Dockerfile`) |
| Multimodal input | `format_user_input(incoming, api_provider)` from `dooers.agents.server` in workflow |

**Packages (PyPI/npm):**

- Server: `dooers-agents-server` — `from dooers.agents.server import AgentServer, AgentConfig`
- Client UI (optional custom app): `dooers-agents-client`
- CLI: `dooers-cli` — `pip install dooers-cli` → command `dooers`

---

## Example: Gmail agent

When user asks for Gmail + Dooers:

### Scope

- **In scope:** capability with Gmail tools, OAuth settings, handoff from cortex, deploy guide
- **Out of scope:** building the Dooers Studio UI or OAuth consent screens — document manual setup for the creator

### Implementation steps

1. Add dependency: `google-api-python-client`, `google-auth-oauthlib` in `pyproject.toml`
2. `schemas.py` — fields: `gmail_client_id`, `gmail_client_secret`, `gmail_refresh_token` (CREATOR, PASSWORD)
3. `external/gmail/client.py` — build service from refresh token
4. `capabilities/gmail.py` — tools: `search_emails`, `read_email`, `create_draft` (start read-only if user unsure)
5. `workflow.py` — register `create_gmail_capability`
6. Update `dooers.yaml` name/description/capabilities list
7. Document for user: Google Cloud Console OAuth desktop/app credentials → paste refresh token in Studio

### Cortex routing

Add to `system_prompt` in schemas or cortex instructions:

> When the user asks about email, inbox, or Gmail, hand off to the gmail capability.

### Safety

- Confirm before `send` email unless user explicitly asked to send
- Never log refresh tokens
- Store tokens only via Studio settings (encrypted at rest by platform)

---

## RAG (optional for any agent)

1. Creator uploads PDFs in Studio → `settings-upload`
2. `create_cortex(..., attach_knowledge_tools=True)`
3. Per-capability: `knowledge_field_allowlist=("knowledge_files",)`

Env: `OPENAI_API_KEY`, `RAG_PIPELINE=openai`.

---

## WhatsApp (optional)

Already wired in starter. Ensure `dooers.yaml`:

```yaml
whatsapp:
  enabled: true
  path: /whatsapp/inbound
```

User connects instance in Dooers Studio (not in agent code). Handler uses `send.text()` — SDK routes to WhatsApp when `channel=whatsapp`.

---

## Charts & observability (SDK ≥ 0.15 / 0.16)

- **Charts:** `yield send.chart(...)` — types `bar`, `bar_horizontal`, `stacked_bar`, `line`, `area`, `pie`, `donut`, `scatter`. Prefer charts over markdown tables for numeric summaries. Guide: `docs/09-charts.md`. Starter smoke: `/test-chart-all`.
- **Observability:** dependency includes `[observability]`. After hire/seed, turn traces export to Dooers observability; optional env overrides `AGENT_CORE_BASE_URL`, `AGENT_OTEL_SERVICE_URL`, `OTEL_SERVICE_NAME`. Guide: `docs/10-observability.md`. No GCP exporter keys in the agent.

---

## Deploy (`dooers push`)

**You prepare the repo; the user runs auth and push.** Finish [Step 7](#step-7--lint-build-optional-local-qualitative-test) first.

```bash
pip install dooers-cli
dooers login          # user only — interactive
dooers validate       # optional
dooers push
```

After push, tell user to configure in **Studio**:

1. Messages URL: already written by push — confirm it is `wss://agents.dooers.ai/<agent-id>/ws` (no `/api/...`)
2. Runtime API key
3. LLM model + `provider_api_key`
4. Hire blueprint into a team

Production env (in `env.prod`, injected at deploy — not git):

- `USE_API_PREFIX=false` (always for hosted)
- `OPENAI_API_KEY`
- **Self-hosted Postgres:** `AGENT_DATABASE_*` (reachable from Cloud Run, not `localhost`) + `APP_POSTGRES_POOL_ENABLED=true` if RAG SQL metadata is needed
- **Managed DB (`database.type: dooers`):** `AGENT_DATABASE_TYPE=dooers`, `APP_POSTGRES_POOL_ENABLED=false` — do **not** set `AGENT_DATABASE_HOST`, `GOOGLE_APPLICATION_CREDENTIALS`, or password fields

The starter has two DB paths: SDK persistence (works with managed DB) and optional app Postgres pool for RAG SQL tables (disable with managed DB). See `env.prod.example` and `docs/04-rag.md`.

Full guide in repo: `docs/08-deploy.md`.

---

## Security boundaries

Stay within the **public SDK contract**. Do not implement or document:

- Platform admin or marketplace APIs not covered in this skill
- Credential provisioning beyond env vars / Studio settings fields
- Reverse-engineering Dooers platform services

The agent repo only exposes: **WebSocket + HTTP routes + SDK handler**.

---

## Output format for the user

When finishing, provide:

```markdown
## O que foi feito
- [bullets]

## Configurar no Studio
- Messages URL: ...
- Settings: [fields]

## Comandos para você rodar
\`\`\`bash
uv run poe check      # lint antes do push
uv run poe dev        # teste qualitativo local (opcional: ngrok → Messages URL)
dooers login && dooers push
\`\`\`

## Segredos necessários
- [list without values]
```

---

## Deep reference (if repo is open)

| Doc | Topic |
|-----|-------|
| `docs/01-anatomy.md` | Architecture |
| `docs/02-sdk-contract.md` | Handler API (`send.*`, roles, channel) |
| `docs/03-capabilities.md` | Handoffs |
| `docs/04-rag.md` | Knowledge base |
| `docs/06-forms.md` | UI forms |
| `docs/07-channels.md` | UI WebSocket, dispatch, public chat, WhatsApp |
| `docs/08-deploy.md` | dooers push |
| `docs/09-charts.md` | `send.chart` BI in chat |
| `docs/10-observability.md` | OpenTelemetry / org traces |
| `docs/recipes/deploy-with-dooers-push.md` | Deploy checklist |
| `docs/recipes/external-service-credentials.md` | Credentials onboarding |

SDK reference: https://github.com/Dooers-ai/dooers-agents-server/blob/main/docs/sdk-handler-reference.md

---

## Anti-patterns

- Monolithic handler with all business logic (use capabilities)
- Storing messages in custom tables
- Committing `gcp-service-account.json` or `.env`
- Calling undocumented Dooers APIs
- Skipping `run_start` / `run_end`
- Hardcoding API keys or skipping the credentials ask (env vs settings vs form)
- Pushing without `poe check` / any local verification
- One-size-fits-all workflow when owners need admin/analytics and members need a simpler path
