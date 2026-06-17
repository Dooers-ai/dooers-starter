# Uploads

## Duas rotas

| Rota | Quem usa | Persistência |
|------|----------|--------------|
| `POST .../uploads` | Chat composer, ficheiros em forms | Memória (default) ou GCS+RAG se configurado |
| `POST .../settings-upload` | Studio — base de conhecimento | Sempre indexa RAG |

## Chat upload (`/uploads`)

Multipart form:

- `file` — ficheiro
- `agent_id` — obrigatório
- `thread_id`, `run_id` — opcionais
- `source` — `chat` (default) ou `form`

Resposta: `{ "ref_id": "..." }` — referência nas partes da mensagem WebSocket.

### Staging em memória (default)

`ref_id` válido para o turno atual. Adequado para imagens no chat.

### Persistência durável

Ative no servidor:

```env
STORE_CHAT_UPLOADS=true
CHAT_STORAGE_SERVICE=gcp  # ou azure
GCP_BUCKET_NAME=...
```

E no Studio: `persist_chat_attachments = true`.

O SDK grava blob + opcionalmente indexa no Vector Store.

## Settings upload (`/settings-upload`)

- `file`, `agent_id`, `field_id` (ex.: `knowledge_files`)
- Sempre persiste e indexa quando RAG configurado

## Client SDK

```tsx
const { upload } = useUpload();
const { ref_id } = await upload(file, { agentId, threadId });
// Enviar mensagem com part document/image referenciando ref_id
```

## Policy de tipos

`AGENT_ALLOWED_CONTENT_TYPES=text,audio,image` em `.env`.

Tipos não permitidos recebem mensagem de negação na thread (SDK) sem chamar o LLM.

## Implementação

- `src/modules/upload/chat_upload.py`
- `src/modules/upload/settings_upload.py`
