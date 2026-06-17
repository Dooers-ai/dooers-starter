# SDK contract

O agente usa o pacote Python **`dooers-agents-server`** (`import dooers`).

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
| `send.audio(url=..., mime_type=...)` | Áudio TTS |
| `send.form(message, elements, ...)` | Formulário na UI |
| `send.form_text(name, ...)` | Elemento do form (helper) |
| `send.update_thread(title=...)` | Título do thread |
| `send.update_user_event(...)` | Atualiza evento (ex.: transcrição STT) |
| `send.whatsapp.text(...)` | Resposta só WhatsApp (opcional; `send.text` também roteia) |

Cada `yield` é **gravado na thread** e enviado ao cliente.

## `memory` — histórico

```python
history = await memory.get_history(limit=30, format="openai_responses")
raw = await memory.get_history_raw(limit=10)
```

## `settings` — configuração do agente

```python
agent_settings = await settings.get_all()
# dict com campos de schemas.py (system_prompt, llm_model, knowledge_files…)
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

A UI oficial da plataforma (`dooers-app-web`) já usa estes hooks — na maioria dos casos você só precisa do server SDK.
