# RAG (base de conhecimento) — serviço gerenciado Dooers

## Fluxo

1. Criador envia arquivos no Studio (campo **Documentos**, `field_id=knowledge`) → `POST /settings-upload`.
2. `rag_service.ingest_bytes` → `dooers.tools.rag.upload` (knowledge base = `field_id`, estratégia por extensão).
3. O Studio mostra o inventário real do serviço: `knowledge_sync.install_settings_knowledge_hydrate` sobrepõe os
   campos `FILE_MULTI` ao ler settings. Remover no Studio → `knowledge_settings_hook.on_settings_updated` apaga no serviço.
4. No turno, `RuntimeContext.knowledge_bases` lista as bases com conteúdo; o modelo chama `search_knowledge`.
5. Resultados voltam com cabeçalho `[knowledge_base=… score=… document_id=… source=…]` para citação.

## Configuração

```env
DOOERS_RAG_SERVICE_URL=https://rag.dooers.ai   # vazio → RAG desligado
AGENT_SEED_SECRET=...                          # mint do token de serviço
```

Sem `DOOERS_RAG_SERVICE_URL`, `/settings-upload` responde 503 e o prompt diz ao modelo para não buscar.

## Contexto de execução (importante para tools)

O SDK do RAG lê `agent_id`/`organization_id`/`workspace_id`/`user_id` de um contexto **por asyncio Task**. O Agents SDK
executa tools em tasks filhas, então `search_knowledge` chama `rebind_execution_context(...)` antes de buscar. Qualquer
nova tool que use `dooers.tools.rag` deve fazer o mesmo (`src/modules/rag/managed.py`).

## Várias bases

Uma knowledge base por campo `FILE_MULTI`. Para separar domínios, adicione campos em `schemas.py` e inclua os ids em
`rag/knowledge_settings.py::KNOWLEDGE_FIELD_IDS`. `search_knowledge` recebe `knowledge_bases` do contexto.

## Extensões aceitas

`.pdf .csv .xlsx .xls .docx .json .txt .md` — `rag/ingest_filename.py`.

## Boas práticas

- O prompt já instrui: responder com base nos trechos retornados e dizer de onde vieram.
- Queries curtas e específicas; `max_results` 5–8.
- Documentos anexados **na conversa** não vão para o RAG — usam `get_thread_document_context` ([05-uploads.md](05-uploads.md)).
