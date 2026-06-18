---
name: dooers-agent
description: >-
  Builds AI agents on the Dooers platform using dooers-agents-server SDK,
  capabilities architecture, RAG, WhatsApp, forms, uploads, and dooers push deploy.
  Use when the user asks to create a Dooers agent, connect an integration (Gmail,
  Slack, ERP, etc.) to Dooers, deploy with dooers push, or references dooers-starter
  or skills.md from Dooers-ai.
disable-model-invocation: true
---

# Dooers Agent Skill

Build production agents that run on **Dooers** (chat UI, Studio, WhatsApp, threads) using the public starter kit and SDK — without reimplementing the platform.

**Starter repo:** `https://github.com/Dooers-ai/dooers-starter`  
**This skill:** `skills.md` in that repo (you may be reading a copy or the live file).

**Public packages only:** `dooers-agents-server`, `dooers-agents-client`, `dooers-cli`, and this starter. Do not reference private Dooers repositories in docs or code.

---

## When to apply this skill

Apply when the user wants to:

- Create a new agent connected to Dooers
- Add an integration (Gmail, calendar, CRM, database, API…) to a Dooers agent
- Use Dooers services: chat threads, RAG, forms, uploads, WhatsApp, dispatch
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
5. **Secrets in Studio/env** — never commit `.env`, OAuth JSON, or service account keys.
6. **Use only public packages** — `dooers-agents-server`, `dooers-agents-client`, `dooers-cli`, and this starter. Do not reference or import private Dooers repositories.

---

## Workflow (new agent)

Copy this checklist and track progress:

```
- [ ] 1. Clone starter (or verify project matches layout)
- [ ] 2. Rename in dooers.yaml + API_AGENT_NAME
- [ ] 3. Implement domain capability + tools
- [ ] 4. Register handoff in workflow.py
- [ ] 5. Add creator settings in schemas.py (API keys, OAuth fields)
- [ ] 6. uv run poe check
- [ ] 7. Guide user: dooers login && dooers push
- [ ] 8. Guide user: Studio Messages URL + runtime API key + LLM settings
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

Read credentials from **creator settings** (`schemas.py`), not hardcoded:

```python
async def create_gmail_capability(agent_id, agent_settings):
    client = GmailClient.from_settings(agent_settings)
    ...
```

Add `SettingsField` entries (PASSWORD for tokens, TEXT for client id) with `visibility=CREATOR`.

### Step 6 — Forms (if UI input needed)

- Tool returns `{"requiresForm": true}` OR handler yields `send.form(...)` directly
- Next turn: `incoming.form_data` → normalize to `incoming.message`
- See starter: `capabilities/feedback.py` + `agent.py`

### Step 7 — Lint

```bash
uv run poe check
```

---

## How the agent is exposed (channels)

One handler serves **all entry points**. Choose how users reach the agent:

| Mode | Entry | Agent code | Published via Dooers platform |
|------|-------|------------|-------------------------------|
| **Dooers UI** | `WebSocket {api_prefix}/ws` | `agent_server.handle(ws, handler)` — already in starter | Studio Messages URL + hire in team |
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

## Deploy (`dooers push`)

**You prepare the repo; the user runs auth and push.**

```bash
pip install dooers-cli
dooers login          # user only — interactive
dooers validate       # optional
dooers push
```

After push, tell user to configure in **Studio**:

1. Messages URL: `wss://<host>/api/prod/<API_AGENT_NAME>/ws`
2. Runtime API key
3. LLM model + `provider_api_key`
4. Hire blueprint into a team

Production env (runtime panel, not git): `AGENT_DATABASE_*`, `OPENAI_API_KEY`, `SERVICE_URL`, `API_ENVIRONMENT=prod`.

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
uv run poe dev        # testar local
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
| `docs/02-sdk-contract.md` | Handler API |
| `docs/03-capabilities.md` | Handoffs |
| `docs/04-rag.md` | Knowledge base |
| `docs/06-forms.md` | UI forms |
| `docs/07-channels.md` | UI WebSocket, dispatch, public chat, WhatsApp |
| `docs/08-deploy.md` | dooers push |
| `docs/recipes/deploy-with-dooers-push.md` | Deploy checklist |

SDK reference: https://github.com/Dooers-ai/dooers-agents-server/blob/main/docs/sdk-handler-reference.md

---

## Anti-patterns

- Monolithic handler with all business logic (use capabilities)
- Storing messages in custom tables
- Committing `gcp-service-account.json` or `.env`
- Calling undocumented Dooers APIs
- Skipping `run_start` / `run_end`
