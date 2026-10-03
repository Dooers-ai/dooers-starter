# Dooers Agent Starter

Starter kit oficial para criar agentes de IA na plataforma [Dooers](https://dooers.ai): FastAPI +
**dooers-agents-server** SDK (≥ 0.23), LLM via **Dooers Gateway**, base de conhecimento no **RAG gerenciado
Dooers**, **Skills** carregadas sob demanda, entrada **multimodal** (texto, áudio, imagem, documentos),
formulários, gráficos, WhatsApp, OpenTelemetry e deploy com **`dooers push`**.

Para quem usa Cursor / Claude Code: **[skills.md](skills.md)** é a skill principal (URL compartilhável).

## Pacotes públicos Dooers

| Pacote | Uso |
|--------|-----|
| [`dooers-agents-server`](https://github.com/Dooers-ai/dooers-agents-server) | SDK Python — handler, threads, settings, RAG (`dooers.tools.rag`), WhatsApp, OTel |
| [`dooers-agents-client`](https://github.com/Dooers-ai/dooers-agents-client) | SDK React (opcional — UI customizada) |
| `dooers-cli` | Deploy — `dooers push` |

## O que vem pronto

- **LLM via Dooers Gateway** — uma chave `dk_live_…`; o seletor de modelo do Studio é sincronizado com a allow-list da chave (`/v1/models`).
- **Um agente, Skills progressivas** — o prompt carrega só o catálogo (id + descrição); o corpo da Skill entra via tool `load_skill`. Skills em `skills/*.md` ou upload no Studio.
- **Catálogo de tools estável** — `load_skill`, `search_knowledge`, `get_thread_document_context`, `calculate`; adicionar tool = 3 linhas + implementação.
- **RAG gerenciado Dooers** — upload no Studio → serviço RAG; inventário sincronizado de volta para o Studio; remoção propaga.
- **Multimodal** — áudio transcrito (STT), imagens por visão nativa, documentos extraídos localmente (PDF/DOCX/XLSX/CSV/JSON/TXT/MD) e consultáveis por tool.
- **Eventos ricos na UI** — `tool_call`/`tool_result`/`reasoning` em streaming, `run_start`/`run_end` com códigos de erro.
- **Hardening agentico** — prompt estático cacheável + estado volátil separado, execution guard contra respostas passivas, guardrails do Agents SDK a partir das políticas do Studio, soft-failures em OTEL.
- Formulários, gráficos (`/test-chart`), WhatsApp inbound, boot degradado (sobe mesmo sem banco/RAG), testes de invariantes.

## Requisitos

- Python **3.11+**, `uv`
- PostgreSQL local (ou banco gerenciado no deploy)
- `DOOERS_GATEWAY_API_KEY` (LLM) — `OPENAI_API_KEY` só para áudio (STT/TTS)
- `DOOERS_RAG_SERVICE_URL` + `AGENT_SEED_SECRET` para base de conhecimento (opcional)

## Quickstart

```bash
git clone https://github.com/Dooers-ai/dooers-starter.git
cd dooers-starter
uv sync --extra dev
cp .env.example .env     # preencha DOOERS_GATEWAY_API_KEY e AGENT_DATABASE_*
uv run poe dev           # http://localhost:8000  — WebSocket em ws://localhost:8000/ws
uv run poe test
```

Crie um blueprint no Studio apontando para a URL do WebSocket (`wss://agents.dooers.ai/<agent-id>/ws` no hospedado).

## Deploy com Dooers CLI

```bash
pip install dooers-cli      # ou: uv tool install dooers-cli
dooers login
dooers validate
dooers push
```

O CLI lê `dooers.yaml` + `Dockerfile` e injeta cada linha de **`env.prod`** como variável de ambiente no runtime
(o `.env` local **não** é enviado). Use `env.prod.example` como template. Nunca commite `env.prod`.

### Banco gerenciado (recomendado)

`dooers.yaml` → `database: { type: dooers }` e `env.prod` → `AGENT_DATABASE_TYPE=dooers`. A plataforma injeta a
conexão; **não** configure `AGENT_DATABASE_HOST/USER/PASSWORD` nem `GOOGLE_APPLICATION_CREDENTIALS`. Tudo o que o starter
persiste (threads, settings, documentos processados) passa pelo SDK, então funciona igual nos dois modos.

Guia completo: [docs/08-deploy.md](docs/08-deploy.md).

## Documentação

| Guia | Conteúdo |
|------|----------|
| [docs/00-quickstart.md](docs/00-quickstart.md) | Setup local |
| [docs/01-anatomy.md](docs/01-anatomy.md) | Camadas, fluxo do turno, prompt estático × volátil |
| [docs/02-sdk-contract.md](docs/02-sdk-contract.md) | API do handler (`send`, `incoming`, `memory`) |
| [docs/03-capabilities.md](docs/03-capabilities.md) | Skills × tools, guardrails, execution guard |
| [docs/04-rag.md](docs/04-rag.md) | RAG gerenciado Dooers |
| [docs/05-uploads.md](docs/05-uploads.md) | Anexos e entrada multimodal |
| [docs/06-forms.md](docs/06-forms.md) | Formulários |
| [docs/07-channels.md](docs/07-channels.md) | `/ws`, public chat, dispatch, WhatsApp |
| [docs/08-deploy.md](docs/08-deploy.md) | `dooers push` |
| [docs/09-charts.md](docs/09-charts.md) | Gráficos (`send.chart`) |
| [docs/10-observability.md](docs/10-observability.md) | OpenTelemetry |
| [docs/recipes/](docs/recipes/) | Receitas copiáveis |

## Estrutura

```
src/main.py                    # rotas HTTP/WS + lifespan (SDK, RAG hydrate, tabela de docs, sync de modelos)
src/modules/agent/agent.py     # handler
src/modules/agent/workflow.py  # um turno (streaming, repair, outcome)
src/modules/agent/core/        # tool_catalog, skills, policies, context, tools, guard, execution_guard, agent
src/modules/llm/               # gateway: modelo, picker, erros
src/modules/rag/               # RAG gerenciado
src/modules/doc_processing/    # documentos anexados
skills/                        # Skills embutidas
tests/                         # invariantes
```

## Licença

MIT — veja [LICENSE](LICENSE).
