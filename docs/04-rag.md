# RAG (base de conhecimento)

## Fluxo

1. Criador faz upload no Studio → `POST /settings-upload`
2. Ficheiro vai para OpenAI Files + Vector Store (+ GCS/Azure opcional)
3. Capability recebe tool `dooers_file_search_{field_id}`
4. LLM chama a tool com query curta → extratos voltam ao modelo

## Configuração

### Env (servidor)

```env
RAG_PIPELINE=openai
OPENAI_API_KEY=sk-...
STORE_RAG_UPLOADS=false   # true + GCS/Azure para arquivo dos originais
RAG_STORAGE_SERVICE=none  # gcp | azure
```

### Studio (criador)

Campo `knowledge_files` em `schemas.py` — tipo `FILE_UPLOAD`, visibility `CREATOR`.

### Persistir anexos de chat no RAG

```env
STORE_CHAT_UPLOADS=true
CHAT_STORAGE_SERVICE=gcp
GCP_BUCKET_NAME=...
```

No Studio: ativar `persist_chat_attachments`.

Quando ativo, `POST /uploads` também indexa no Vector Store (source `chat` ou `form`).

## Scoping por capability

```python
await create_cortex(
    ...,
    knowledge_field_allowlist=("knowledge_files",),
)
```

Cada capability pode ter allowlist diferente — ver `feedback.py`.

## Hook de reindexação

`knowledge_settings_hook.py` reprocessa ficheiros quando settings mudam no Studio.

## Migrações

`migrations/001_agent_rag.sql` — tabelas `agent_knowledge_files`, `agent_rag_vector_store`.

Aplicadas no startup via `src/database/pool.py`.

## Extensões permitidas

`pdf, csv, xlsx, xls, doc, docx` — validado em `settings_upload.py`.

## Boas práticas

- Instrua o modelo a citar apenas extratos devolvidos pela tool
- Queries curtas e específicas funcionam melhor
- Separe bases por `field_id` se tiver domínios distintos
