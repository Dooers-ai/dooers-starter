# Canais e exposição do agente

Um agente Dooers pode ser alcançado de **três formas**. O **mesmo handler** (`dooers_agent_handler`) atende todos — o que muda é **como a mensagem entra** e o valor de `channel` / `channel_meta` na thread.

```
                         ┌─────────────────────────────────────┐
                         │     Seu agente (FastAPI + SDK)      │
                         │  dooers_agent_handler (um só)       │
                         └──────────────┬──────────────────────┘
                                        │
          ┌─────────────────────────────┼─────────────────────────────┐
          │                             │                             │
          ▼                             ▼                             ▼
   WebSocket /ws              dispatch() + rota HTTP          Plataforma Dooers
   (UI + public chat)         (canais externos)             (publica links)
```

---

## Modo 1 — UI Dooers (WebSocket)

**Quem usa:** membros do time no dashboard (operadores, viewers).

**Endpoint do agente:** `wss://{host}{api_prefix}/ws`

**Como funciona:**

1. Blueprint registado no Studio com **Messages URL** apontando para esse WebSocket.
2. Utilizador contrata (hire) o blueprint num **workspace/team**.
3. A UI Dooers (`dooers-agents-client`) conecta ao `/ws` com JWT do utilizador autenticado.
4. O handler recebe `incoming` normalmente; `send.text()` grava na thread e aparece no chat.

**Código (já no starter):**

```python
@api_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await agent_server.handle(websocket, dooers_agent_handler)
```

**O criador precisa:** expor `/ws` publicamente (HTTPS/WSS) e configurar a URL no Studio. Não há código extra no agente para o chat interno.

---

## Modo 2 — Canais externos (`dispatch` + endpoints HTTP)

**Quem usa:** sistemas externos (WhatsApp, CRM, cron, webhooks próprios, filas).

**Padrão:** uma rota HTTP no **seu** FastAPI recebe o evento e chama `agent_server.dispatch()` com o **mesmo handler** do WebSocket.

```python
stream = await agent_server.dispatch(
    dooers_agent_handler,
    agent_id,
    message="...",
    user=user,
    thread_id=thread_id,          # opcional — novo thread se omitido
    channel="api",                # identificador do canal
    channel_meta={"source": "my-crm"},  # metadados para auditoria na UI
)
async for event in stream:
    ...
```

Cada evento do handler é **persistido na thread** (como no WebSocket). A UI Dooers mostra o histórico e metadados de entrega (`delivery.channel`, etc.).

### Endpoints típicos no agente

| Rota | Canal | Quem chama |
|------|-------|------------|
| `{api_prefix}/ws` | `dooers-platform` (default) | UI Dooers |
| `{api_prefix}/whatsapp/inbound` | `whatsapp` | Serviço Dooers WhatsApp Tools (HMAC) |
| *sua rota* ex. `/hooks/crm` | `api`, `crm`, … | Seu backend — você implementa e chama `dispatch()` |

### WhatsApp (canal externo gerido pela Dooers)

Já incluído no starter:

```
WhatsApp → Dooers Tools Service → POST …/whatsapp/inbound
         → dispatch(channel="whatsapp", channel_meta={whatsapp: {...}})
         → handler → send.text() → outbound → WhatsApp
```

- **No agente:** rota `/whatsapp/inbound` + `dooers.yaml` com `whatsapp.enabled: true`.
- **Na plataforma:** manager conecta instância WhatsApp no workspace (Studio / canais). A Dooers provisiona secrets e aponta o inbound para o seu agente.

### Canal customizado (ex.: webhook CRM)

1. Adicione rota em `main.py` (autentique com API key ou HMAC).
2. Parse do body → `User` + `message`.
3. Chame `dispatch(..., channel="crm", channel_meta={...})`.
4. Não duplique lógica — reutilize `dooers_agent_handler`.

Recipe: [recipes/proactive-dispatch.md](recipes/proactive-dispatch.md).

---

## Modo 3 — Public Chat (links públicos na plataforma Dooers)

**Quem usa:** visitantes externos (site, landing page) **sem conta Dooers**.

**Importante:** o visitante **não** chama um endpoint novo no seu agente. A **plataforma Dooers** publica um link e a UI pública conecta ao **mesmo WebSocket `/ws`** do agente, com:

- `channel="dooers-public-chat"`
- `channel_meta` com `public_chat_label`

O agente **não implementa** public chat — só precisa do WebSocket a funcionar e do blueprint contratado no workspace.

### Como o criador publica (na plataforma, não no código)

1. **Workspace** → ativar **Allow public chats**.
2. **Channels / Public Chats** → **Create Public Chat Link**:
   - escolher o **agent** (worker contratado),
   - label, greeting, campos pré-chat (nome, email…),
   - modo anónimo ou autenticado.
3. A plataforma gera URL partilhável (token na URL).
4. Visitante abre o link → chat leve → mensagens vão para o **mesmo** `/ws` e **mesmas threads** visíveis no dashboard.

Threads de public chat aparecem no histórico do agente com origem `dooers-public-chat` — útil para operadores acompanharem conversas externas.

### O que o agente precisa fazer

| Precisa | Não precisa |
|---------|-------------|
| `/ws` público e estável | Rota `/public-chat` no FastAPI |
| Blueprint ativo + hire no workspace | Lógica de geração de links |
| Handler normal (`send.text`, forms, RAG) | Auth de visitantes (plataforma trata) |

---

## Comparativo

| | UI Dooers | Public chat | Canal externo (dispatch) |
|--|-----------|-------------|---------------------------|
| **Entrada** | WebSocket `/ws` | WebSocket `/ws` (via link Dooers) | HTTP → `dispatch()` |
| **Utilizador** | Membro autenticado | Visitante (guest ou login leve) | Sistema externo / WhatsApp |
| **Config** | Studio Messages URL | Workspace → Public Chat Link | Rota HTTP + `dispatch` no agente |
| **Canal na thread** | default / platform | `dooers-public-chat` | `whatsapp`, `api`, custom… |
| **Código extra no agente** | Nenhum | Nenhum | Rota + adapter (ex. `whatsapp_channel.py`) |

---

## Dual transport — regra de ouro

```python
# Chat em tempo real (UI + public chat)
await agent_server.handle(websocket, dooers_agent_handler)

# Eventos externos (WhatsApp, webhooks, proativo)
await agent_server.dispatch(dooers_agent_handler, agent_id, ...)
```

**Um handler, múltiplos pontos de entrada.** Eventos sempre gravados na thread; a UI Dooers mostra tudo num só lugar.

---

## Metadados de canal

O SDK persiste `channel` e `channel_meta` nos eventos. Na UI de chat é possível ver de onde veio a mensagem (WhatsApp, public chat label, etc.).

Para WhatsApp, use `send.text()` — o SDK roteia para o telefone quando `channel=whatsapp`.

---

## O que fica na plataforma (não no repo do agente)

- Publicação de links de public chat
- Provisionamento WhatsApp (instância, QR, Meta/Evolution)
- Hire de blueprint em team/workspace
- Marketplace / billing

O criador expõe **runtime do agente** (WebSocket + rotas de canal que escolher) e regista no Studio.
