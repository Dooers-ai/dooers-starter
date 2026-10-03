# SDK contract

O agente usa o pacote Python **`dooers-agents-server`**.

```python
from dooers.agents.server import AgentConfig, AgentServer
```

Documentação completa do handler: [dooers-agents-server SDK reference](https://github.com/Dooers-ai/dooers-agents-server/blob/main/docs/sdk-handler-reference.md).

## Assinatura do handler

```python
async def handler(incoming, send, memory, analytics, settings):
    yield send.run_start()
    yield send.text("Olá!")
    yield send.run_end()
```

## `incoming` — mensagem recebida

| Campo | Descrição |
|-------|-----------|
| `message` | Texto agregado |
| `content` | Partes tipadas (text, audio, image, document…) |
| `context.thread_id` | ID do thread |
| `context.event_id` | ID do evento do utilizador |
| `context.user` | `user_id`, `user_name`, `user_email`… |
| `form_data` | Dict com valores se resposta a formulário |
| `form_cancelled` | `True` se cancelou formulário |
| `form_event_id` | ID do evento form original |

## `send` — eventos para UI e thread

| Método | Efeito |
|--------|--------|
| `send.run_start()` | Inicia run (obrigatório) |
| `send.run_end(status=...)` | Finaliza run |
| `send.text(content, author=...)` | Mensagem assistente |
| `send.reasoning(text, author=...)` | Bloco colapsável de raciocínio (não entra no histórico LLM) |
| `send.chart(...)` | Gráfico BI na UI (`bar`, `line`, `pie`, …) — ver [09-charts.md](09-charts.md) |
| `send.chart_series(key, label=..., color=...)` | Metadados de série para `send.chart` |
| `send.audio(url=..., mime_type=...)` | Áudio TTS |
| `send.form(message, elements, ...)` | Formulário na UI |
| `send.form_text(name, ...)` | Elemento do form (helper) |
| `send.update_thread(title=...)` | Título do thread |
| `send.update_user_event(...)` | Atualiza evento (ex.: transcrição STT) |
| `send.whatsapp.text(...)` | Resposta só WhatsApp (opcional; `send.text` também roteia) |

Cada `yield` é **gravado na thread** e enviado ao cliente.

### Exemplo — chart + reasoning

```python
yield send.reasoning("Agregando vendas por região…")
yield send.chart(
    chart_type="bar_horizontal",
    data=[{"region": "North", "sales": 320}, {"region": "South", "sales": 280}],
    x_key="region",
    y_keys=["sales"],
    title="Sales by Region",
    size="medium",
)
```

## Roles e canal no `incoming`

Use roles e canal para escolher workflows distintos (ex.: BI só para owners):

| Campo | Valores típicos |
|-------|-----------------|
| `incoming.context.user.organization_role` | `owner` \| `manager` \| `member` |
| `incoming.context.user.workspace_role` | `manager` \| `member` |
| `incoming.context.user.system_role` | `admin` \| `user` |
| `incoming.context.channel` | `dooers-platform`, `whatsapp`, … |

## Observability (OTel)

Com o extra `[observability]` (§ [10-observability.md](10-observability.md)), o SDK exporta traces por turno automaticamente após o seed da runtime API key.

## `memory` — histórico

```python
history = await memory.get_history(limit=30, format="openai_responses")
raw = await memory.get_history_raw(limit=10)
```

## `settings` — configuração do agente

```python
agent_settings = await settings.get_all()
# dict com campos de schemas.py (system_prompt, llm_models, skills, knowledge…)
```

## `analytics` — telemetria

```python
await analytics.track("llm.request", data={"agent_id": agent_id})
```

## Dual transport

O **mesmo handler** serve três modos de exposição:

| Transporte | Quem conecta | Endpoint no agente |
|------------|--------------|-------------------|
| `AgentServer.handle(ws, handler)` | UI Dooers (membros) + **public chat** (visitantes via link da plataforma) | `WebSocket …/ws` |
| `AgentServer.dispatch(handler, …)` | WhatsApp, CRM, cron, webhooks | Rota HTTP sua + `dispatch(channel=…)` |

```python
# UI interna + public chat (ambos WebSocket)
await agent_server.handle(websocket, handler)

# Canal externo (ex. WhatsApp, webhook)
stream = await agent_server.dispatch(
    handler,
    agent_id,
    message="...",
    user=user,
    channel="whatsapp",
    channel_meta={"whatsapp": {...}},
)
```

Public chat **não** exige rota nova no agente — a plataforma publica o link e o visitante usa o mesmo `/ws`. Ver [07-channels.md](07-channels.md).

## Client SDK (UI)

Para apps React customizadas: pacote **`dooers-agents-client`**.

```tsx
import { AgentProvider, useMessage } from "dooers-agents-client";
```

Hooks principais: `useConnection`, `useMessage`, `useForm`, `useUpload`, `useSettings`.

Para apps customizadas use `dooers-agents-client`. Para chat na plataforma Dooers, basta o server SDK neste starter.
