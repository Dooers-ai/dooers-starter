# Uploads e entrada multimodal

## Rotas

| Rota | Quem usa | Destino |
|------|----------|---------|
| `POST /uploads` | Composer do chat, arquivos em forms | Staging em memória (ou blob se `STORE_CHAT_UPLOADS`) → parte da mensagem |
| `POST /settings-upload` | Studio — base de conhecimento | RAG gerenciado Dooers ([04-rag.md](04-rag.md)) |
| `POST /skills-upload` | Studio — Skills | Validação do Markdown; conteúdo fica nos settings |

## O que o handler faz com cada tipo

`AGENT_ALLOWED_CONTENT_TYPES=text,audio,image,document` (tipos fora da lista recebem a mensagem de negação do SDK sem chamar o LLM).

| Parte | Tratamento |
|-------|------------|
| `text` | Mensagem do usuário |
| `audio` | `speech.transcribe` (OpenAI STT, exige `OPENAI_API_KEY`); transcrição anexada ao evento do usuário via `send.update_user_event` |
| `image` | Mantida como `ImagePart` → `format_user_input` gera `input_image` (visão nativa) |
| `document` | `doc_processing.process_document_part`: extração local (PDF/DOCX/XLSX/XLS/CSV/JSON/TXT/MD) → Markdown → chunks → `agent_thread_documents` |

Para documentos, o modelo recebe uma nota `[Documento recebido e processado: … document_id=…]` e o manifesto no
`RuntimeContext`. O conteúdo só entra no contexto quando o modelo chama `get_thread_document_context`:

- `mode="summary"` — primeiros 4k chars (estrutura);
- `mode="search"` + `query` — chunks mais relevantes (ranking lexical determinístico);
- `mode="full"` — documento inteiro (até 60k chars; documentos `direct` curtos entram inteiros).

PDFs sem texto extraível são marcados `ocr_required` e o manifesto avisa o modelo.

## Persistência

`agent_thread_documents` é criada no boot via `await agent_server.database()` — funciona com Postgres próprio e com o banco
gerenciado (`AGENT_DATABASE_TYPE=dooers`). Há cache em memória por processo; se o banco estiver indisponível o turno continua.

## Client SDK

```tsx
const { upload } = useUpload();
const { ref_id } = await upload(file, { agentId, threadId });
// enviar mensagem com part document/image referenciando ref_id
```

## Implementação

- `src/modules/upload/chat_upload.py`, `settings_upload.py`, `skills_upload.py`
- `src/modules/doc_processing/` (`extractors/local_basic.py`, `chunking.py`, `search.py`, `repository.py`)
