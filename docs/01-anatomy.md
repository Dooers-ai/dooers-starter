# Anatomia do agente

## Visão geral — três formas de expor o agente

O **mesmo handler** atende UI interna, visitantes via link público e canais externos:

```
                    ┌─────────────────────────┐
                    │  dooers_agent_handler   │
                    └───────────┬─────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
  WebSocket /ws           dispatch()            Public chat
  (UI Dooers +            (rotas HTTP:          (link criado na
   membros do time)         WhatsApp, CRM…)       plataforma → /ws)
```

| Modo | Endpoint no agente | Quem configura o acesso |
|------|-------------------|-------------------------|
| UI Dooers | `wss://…/ws` | Studio — Messages URL |
| Public chat | Mesmo `/ws` (sem rota extra) | Workspace — Public Chat Link |
| Externo | `/whatsapp/inbound` ou rota custom + `dispatch()` | Agente + plataforma (WhatsApp) ou só agente (webhook) |

Detalhes: [07-channels.md](07-channels.md).

## Diagrama de camadas

## Camadas

### `src/main.py`

Aplicação FastAPI. Registra:

| Rota | Função |
|------|--------|
| `GET /health` | Probe |
| `WebSocket /ws` | Chat em tempo real |
| `POST /uploads` | Anexos do composer |
| `POST /settings-upload` | Ficheiros RAG |
| `POST /whatsapp/inbound` | Mensagens WhatsApp (HMAC) |

Todas as rotas de agente ficam sob `{api_prefix}` = `/api/{env}/{agent-name}`.

### `src/modules/agent/agent.py` — Handler

Generator async — **único ponto de entrada** da lógica de negócio:

```python
async def dooers_agent_handler(incoming, send, memory, analytics, settings):
    yield send.run_start()
    # ... normalizar áudio/imagem, validar settings
    out = await run_workflow(...)
    yield send.text(out["reply"])
    yield send.run_end()
```

Regras:

- Todo turno começa com `send.run_start()` e termina com `send.run_end()`.
- Eventos `yield send.*` são **persistidos na thread** e enviados à UI automaticamente.
- Não aceda ao banco diretamente — use `memory` e `settings`.

### `src/modules/agent/workflow.py` — Orquestração

Monta o grafo OpenAI Agents SDK:

1. `create_cortex()` — agente central com tools RAG
2. `_create_additional_capabilities()` — capabilities de domínio
3. `cortex.handoffs.append(capability)` — routing por handoff
4. `Runner.run(starting_capability, history + user_message)`

Guardrails opcionais em `capabilities/guard.py`.

### `src/modules/agent/capabilities/`

**Uma capability = um ficheiro** com `create_<nome>() -> Agent`:

- `cortex.py` — triagem, RAG geral, handoffs
- `feedback.py` — exemplo: formulário de feedback
- `guard.py` — validação entrada/saída

Padrão de handoff (ver `dufrio-agente-rh` para grafos maiores):

```python
cortex = await create_cortex(...)
feedback = await create_feedback_capability(...)
cortex.handoffs.append(feedback)
```

### `src/modules/agent/schemas.py`

Define campos do Studio (`build_settings_schema()`). Campos `CREATOR` aparecem para quem publica o blueprint; `USER` para quem usa o agente contratado.

### `src/modules/agent/agent_config.py`

Instancia `AgentConfig` do SDK: banco, storage, allowlist de anexos, webhook analytics, hook RAG.

## Fluxo de um turno

1. Cliente envia `event.create` (WebSocket) ou `dispatch()` é chamado
2. SDK persiste mensagem do utilizador na thread
3. Handler é invocado com `incoming` + `memory` + `settings`
4. Workflow executa o grafo de agents
5. Handler emite `send.text`, `send.form`, etc.
6. SDK persiste cada evento e faz broadcast à UI

## Onde estender

| Quero… | Editar… |
|--------|---------|
| Nova área de conhecimento | Nova capability + handoff |
| Novo campo no Studio | `schemas.py` |
| Nova rota HTTP | `main.py` |
| Novo canal externo | `dispatch()` ou `channels/` |
| Política de anexos | `agent_config.py` + `.env` |

## Anti-patterns

- Não reimplemente persistência de threads — o SDK já faz isso
- Não exponha credenciais da plataforma Dooers no código do agente
- Não misture lógica de ERP/CRM no handler — use capabilities + tools
