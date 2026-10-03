---
name: dooers-agent
description: >-
  Builds AI agents on the Dooers platform with the dooers-starter kit:
  dooers-agents-server SDK (≥0.23), LLM via the Dooers Gateway, managed Dooers
  RAG, one agent with a stable tool catalog plus Skills loaded on demand,
  multimodal input (audio, images, documents), forms, charts, WhatsApp and
  dooers push deploy. Use when the user asks to create a Dooers agent, connect
  an integration (Gmail, ERP, CRM…) to Dooers, deploy with dooers push, or
  references dooers-starter or skills.md from Dooers-ai.
disable-model-invocation: true
---

# Dooers Agent Skill

Build production agents that run on **Dooers** (chat UI, Studio, WhatsApp, threads) using the public starter kit and SDK — without reimplementing the platform.

**Starter repo:** `https://github.com/Dooers-ai/dooers-starter`  
**Public packages only:** `dooers-agents-server`, `dooers-agents-client`, `dooers-cli`, this starter.  
**SDK baseline:** `dooers-agents-server[dooers,observability]>=0.23`.

---

## When to apply this skill

- Create a new agent connected to Dooers
- Add an integration (Gmail, calendar, CRM, database, API…) to a Dooers agent
- Use Dooers services: threads, RAG, forms, charts, uploads, WhatsApp, dispatch, observability
- Deploy with `dooers push`

---

## Golden rules

1. **Start from the starter** — clone `dooers-starter` or match its layout exactly.
2. **One handler, one agent** — `dooers_agent_handler` in `agent.py`; `build_agent()` in `core/agent.py`. Specialization comes from **Skills** and **tools**, never from extra agents/handoffs.
3. **LLM through the Dooers Gateway** — `DOOERS_GATEWAY_API_KEY`; models come from the key's allow-list. Never ask the creator for OpenAI/Gemini/Anthropic keys for chat. `OPENAI_API_KEY` only for audio (STT/TTS).
4. **Knowledge through the managed Dooers RAG** — `DOOERS_RAG_SERVICE_URL` + `AGENT_SEED_SECRET`; never vendor vector stores.
5. **SDK for persistence** — `memory`, `settings`, `await agent_server.database()`; never your own thread tables or asyncpg pools.
6. **Stable prompt head** — `core/policies.py` depends only on creator settings. Volatile state goes in `RuntimeContext.state_message()`.
7. **Secrets in Studio/env** — never commit `.env`, `env.prod`, OAuth JSON, service-account keys.
8. **External services need onboarding** — ask the user how to supply credentials (env vs settings vs chat form) and which auth formats the tool supports; never invent keys. See [Best practices](#best-practices-for-developer-agents).
9. **Test before push** — `uv run poe check && uv run poe test`, then optional `poe dev`; only then `dooers push`.
10. **Audience-aware** — branch behaviour by `incoming.context.user.organization_role` / `workspace_role` / `incoming.context.channel` via Skills or tool guards.

---

## Best practices for developer agents

### 1. Credentials & paid / authenticated tools

1. Ask whether the user already has an account on the service.
2. Ask where to store credentials: env (`.env`/`env.prod`), Studio `SettingsField` PASSWORD/TEXT (rotatable without redeploy), chat form capture (`send.form` + `await settings.set`), or a mix.
3. Guide the auth formats the tool supports (API key, OAuth refresh, service account, webhook HMAC…) and billing caveats.
4. Default when unsure: **PASSWORD `SettingsField` + runtime form**. Full pattern: [docs/recipes/external-service-credentials.md](docs/recipes/external-service-credentials.md).

### 2. Test locally before `dooers push`

| Check | Command |
|-------|---------|
| Lint | `uv run poe check` |
| Invariants | `uv run poe test` (tool catalog ↔ registry, Skills parse, prompt stable, schema fields) |
| Boot | `uv run poe dev` → `GET /health` returns `{"llm":"dooers_gateway", ...}` |
| Qualitative (optional) | chat via Studio / ngrok `wss://…/ws` against a local Dooers |

### 3. Skills vs tools — decide first

| The user wants… | Build… |
|-----------------|--------|
| A procedure, policy, script, tone, checklist | **Skill** (`skills/<id>.md`) — no code |
| An action with side effects or external data | **Tool** (`core/tool_catalog.py` + `core/tools.py`) |
| Both ("follow this process using the ERP") | Tool for the action + Skill that explains when/how to use it (`requires_tools`) |

---

## Workflow (new agent)

```
- [ ] 1. Clone starter (or verify layout)
- [ ] 2. Rename in dooers.yaml + API_AGENT_NAME; set DOOERS_GATEWAY_API_KEY in .env
- [ ] 3. Ask about external credentials (account? env vs settings vs form? auth format)
- [ ] 4. Tools: ToolSpec + implementation + ALL_TOOLS (+ external client in src/modules/external/<svc>/)
- [ ] 5. Skills: skills/<id>.md for procedures (requires_tools referencing step 4)
- [ ] 6. Studio fields in schemas.py (credentials, options); env in config.py + .env.example + env.prod.example
- [ ] 7. uv run poe check && uv run poe test (+ optional poe dev)
- [ ] 8. Guide user: dooers login && dooers validate && dooers push
- [ ] 9. Guide user: Studio — model, system prompt, Skills, knowledge files, guardrails
```

### Step 1 — Bootstrap

```bash
git clone https://github.com/Dooers-ai/dooers-starter.git my-agent
cd my-agent && uv sync --extra dev && cp .env.example .env
```

### Step 2 — Layout (do not deviate)

```
src/main.py                         # /ws /uploads /settings-upload /skills-upload /whatsapp/inbound /audio
src/modules/agent/agent.py          # handler: normalize audio/images/documents → workflow → events
src/modules/agent/workflow.py       # one turn: history + state → Runner.run_streamed → repair → outcome
src/modules/agent/core/
  tool_catalog.py                   # ToolSpec list (the contract)
  tools.py                          # @function_tool implementations, ALL_TOOLS
  skills.py                         # Skill parser/loader
  policies.py                       # static prompt head
  context.py                        # RuntimeContext (per-turn state)
  guard.py / execution_guard.py     # SDK guardrails / passive-reply repair
  agent.py                          # build_agent(settings)
src/modules/agent/schemas.py        # Studio settings
src/modules/llm/                    # gateway model resolution + picker sync
src/modules/rag/                    # managed RAG façade
src/modules/doc_processing/         # attached documents
src/modules/external/<service>/     # third-party clients
skills/*.md                         # built-in Skills
tests/                              # invariants
```

### Step 3 — Handler contract (already implemented)

```python
async def dooers_agent_handler(incoming, send, memory, analytics, settings):
    yield send.run_start(agent_id=...)
    # normalize: audio→transcript, image→ImagePart, document→processed + note
    async for event in run_workflow(...):   # yields send.tool_call / tool_result / reasoning, then WorkflowOutcome
        ...
    yield send.text(reply, author=...)
    yield send.run_end()                    # or run_end(status="failed", error=code)
```

Do not fork the handler per channel; branch inside via `incoming.context`.

### Step 4 — Tool

```python
# core/tool_catalog.py
ToolSpec("search_emails", "Searches the creator's Gmail inbox."),

# core/tools.py
@function_tool
async def search_emails(ctx: RunContextWrapper[RuntimeContext], query: str, max_results: int = 5) -> str:
    """Search Gmail messages matching query."""
    ctx.context.record_tool_call("search_emails")
    client = GmailClient.from_settings(ctx.context.agent_settings)   # src/modules/external/gmail/client.py
    if client is None:
        return "Gmail is not configured. Ask the creator to fill the Gmail credentials in Studio."
    rows = await client.search(query.strip(), limit=max(1, min(20, max_results)))
    return json.dumps(rows, ensure_ascii=False) if rows else "No messages matched."

ALL_TOOLS = [..., search_emails]
```

Rules: validate args, return business errors as text (the model recovers), raise only on bugs, keep output compact (≤ ~1.5k chars), record the call. If the tool uses `dooers.tools.rag`, call `rebind_execution_context(...)` first (see `search_knowledge`).

### Step 5 — Skill

```markdown
---
id: inbox-triage
name: Triagem de inbox
description: Use quando o usuário pedir para revisar, priorizar ou resumir e-mails recebidos.
requires_tools: [search_emails]
---
1. Chame `search_emails` com `is:unread newer_than:1d` (ajuste se o usuário der período).
2. Agrupe por remetente/assunto; destaque prazos e pedidos explícitos.
3. Proponha no máximo 3 próximas ações; não envie nada sem confirmação.
```

`description` is what the model sees in the catalog — write it as a trigger. The body is only loaded when the model calls `load_skill`.

### Step 6 — Studio fields

```python
SettingsField(id="gmail_refresh_token", type=SettingsFieldType.PASSWORD, label="Gmail refresh token",
              visibility=SettingsFieldVisibility.CREATOR),
```

Keep the existing groups (model, identity, skills, guardrails, knowledge, audio). Field ids referenced by code are pinned in `tests/test_schema_and_llm.py`; extend the set when you add ones the code depends on.

### Step 7 — Verify

```bash
uv run poe check && uv run poe test
uv run poe dev     # GET /health → {"status":"ok","llm":"dooers_gateway","rag":"dooers"|"none"}
```

---

## How the agent is exposed (channels)

| Mode | Entry | Agent code | Published via Dooers |
|------|-------|------------|----------------------|
| Dooers UI | `WebSocket /ws` (root; `USE_API_PREFIX=false`) | already in starter | Studio Messages URL |
| Public chat | same `/ws` | no extra routes | Workspace → Public Chat Link |
| WhatsApp | `POST /whatsapp/inbound` → `dispatch(channel="whatsapp")` | already in starter | connect instance in workspace |
| Custom webhook | your route → `agent_server.dispatch(...)` | add route | — |

Full guide: `docs/07-channels.md`.

---

## Dooers services map

| Need | How |
|------|-----|
| LLM | Dooers Gateway (`DOOERS_GATEWAY_API_KEY`); model picker synced from `/v1/models`; `reasoning_effort` field |
| Knowledge / RAG | Studio **Documentos** → `/settings-upload` → managed RAG; tool `search_knowledge` |
| Attached documents | `document` content parts → `doc_processing` → tool `get_thread_document_context` |
| Audio in / out | OpenAI STT/TTS (`OPENAI_API_KEY`), `reply_mode` text/voz/ambos |
| Images | native vision through `format_user_input` |
| Procedures without code | Skills (`skills/*.md`, Studio upload `/skills-upload`) |
| Guardrails | Studio `guardrails_prompt` (+ input/output specific) → Agents SDK guardrails |
| UI events | `send.tool_call` / `send.tool_result` / `send.reasoning` streamed by `workflow.py` |
| Forms / charts | `send.form()` + `incoming.form_data`; `send.chart(...)` (`docs/09-charts.md`, smoke `/test-chart`) |
| History | `memory.get_history(format="openai_completions")` (gateway uses Chat Completions) |
| Observability | `[observability]` extra; `record_soft_failure` for tolerated errors |
| Deploy | `dooers push` (`dooers.yaml` + `Dockerfile` + `env.prod`) |

---

## Deploy (`dooers push`)

You prepare the repo; the user runs auth and push.

```bash
pip install dooers-cli
dooers login && dooers validate && dooers push
```

`env.prod` (injected at deploy, never committed): `DOOERS_GATEWAY_API_KEY`, `DOOERS_RAG_SERVICE_URL`, `AGENT_SEED_SECRET`,
`AGENT_DATABASE_TYPE=dooers` (managed DB — do not set host/user/password/credentials), `USE_API_PREFIX=false`,
`AGENT_ALLOWED_CONTENT_TYPES=text,audio,image,document`, `OPENAI_API_KEY` only if audio is needed.

After push, in **Studio**: confirm Messages URL `wss://agents.dooers.ai/<agent-id>/ws`, pick the model, write the
system prompt/persona, upload Skills and knowledge files, set guardrails, hire the blueprint.

Full guide: `docs/08-deploy.md`.

---

## Security boundaries

Stay within the public SDK contract: WebSocket + HTTP routes + handler. No platform admin APIs, no credential
provisioning beyond env/Studio fields, no reverse-engineering of Dooers services.

---

## Output format for the user

```markdown
## O que foi feito
- [bullets: tools, skills, campos, env]

## Configurar no Studio
- Modelo, prompt, Skills, documentos, guardrails, campos de credenciais

## Comandos para você rodar
uv run poe check && uv run poe test
uv run poe dev
dooers login && dooers validate && dooers push

## Segredos necessários
- [names only, never values]
```

---

## Deep reference (if repo is open)

| Doc | Topic |
|-----|-------|
| `docs/01-anatomy.md` | Layers, turn flow, static vs volatile prompt |
| `docs/02-sdk-contract.md` | Handler API |
| `docs/03-capabilities.md` | Skills, tools, guardrails, execution guard |
| `docs/04-rag.md` | Managed RAG |
| `docs/05-uploads.md` | Attachments and multimodal input |
| `docs/06-forms.md` · `docs/07-channels.md` · `docs/08-deploy.md` · `docs/09-charts.md` · `docs/10-observability.md` | Forms · channels · deploy · charts · OTel |

SDK reference: https://github.com/Dooers-ai/dooers-agents-server/blob/main/docs/sdk-handler-reference.md

---

## Anti-patterns

- Adding an `Agent` per business domain with handoffs (use Skills + tools)
- Vendor LLM keys in Studio for chat (use the gateway); vendor vector stores (use managed RAG)
- Volatile data (date, user name, document list) in `policies.py`
- Dropping `document` parts or stuffing whole files into the prompt (use `doc_processing` + the tool)
- Custom message tables or asyncpg pools (use the SDK database façade)
- Skipping `run_start` / `run_end`, swallowing errors silently (use `record_soft_failure`)
- Committing `.env` / `env.prod` / service-account JSON
- Pushing without `poe check` and `poe test`
