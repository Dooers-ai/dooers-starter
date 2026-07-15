# Dooers Agent Starter

Starter kit oficial para criar agentes de IA na plataforma [Dooers](https://dooers.ai): FastAPI + **dooers-agents-server** SDK (≥ **0.16.1**), arquitetura por **capabilities**, RAG, formulários e **gráficos** na UI, uploads, WhatsApp, **OpenTelemetry** e deploy com **`dooers push`**.

Destinado a criadores que usam ferramentas como Cursor ou Claude Code — use **[skills.md](skills.md)** como skill principal (URL compartilhável para prompts).

## Pacotes públicos Dooers

Este starter usa apenas artefactos publicados:

| Pacote | Uso |
|--------|-----|
| [`dooers-agents-server`](https://github.com/Dooers-ai/dooers-agents-server) | SDK Python — handler, threads, charts, OTel, dispatch, WhatsApp, RAG (`[dooers,observability]`) |
| [`dooers-agents-client`](https://github.com/Dooers-ai/dooers-agents-client) | SDK React (opcional — UI customizada) |
| `dooers-cli` | Deploy — `dooers push` |

Toda a documentação baseia-se neste repositório e nesses pacotes.

## Skill para IAs

Cole no prompt:

```
Crie um agente conectado ao [Gmail/…] com base no skill Dooers:
https://github.com/Dooers-ai/dooers-starter/blob/main/skills.md
```

Ou, com o repo aberto: `@skills.md` / skill `dooers-agent` em `.cursor/skills/`.

A documentação em `docs/` descreve apenas este starter e os pacotes públicos acima.

## O que vem pronto

- Handler WebSocket + `dispatch()` para canais externos
- Grafo **cortex → capabilities** (exemplo: `feedback` com formulário)
- **Charts** via `send.chart` (smoke: `/test-chart-all`) — renderizados no app-web
- **Observability** — extra `[observability]`; traces por turno após seed da runtime API key
- RAG via OpenAI Vector Store (`/settings-upload`)
- Uploads de chat (`/uploads`) com persistência opcional
- WhatsApp inbound (`/whatsapp/inbound`) via serviço WhatsApp da Dooers
- Settings schema para o Studio (`schemas.py`)
- `dooers.yaml` — metadados do blueprint
- `Dockerfile` — imagem para deploy

## Requisitos

- Python **3.11+**
- PostgreSQL
- `OPENAI_API_KEY` (RAG + STT/TTS)
- Chave do fornecedor LLM configurada no Studio (Gemini, Claude, OpenAI, Azure…)

## Quickstart

```bash
git clone https://github.com/Dooers-ai/dooers-starter.git
cd dooers-starter
uv sync --extra dev
cp .env.example .env
# Edite .env — banco, OPENAI_API_KEY, SERVICE_URL

uv run poe dev
```

Rotas na raiz (padrão `USE_API_PREFIX=false`):

- WebSocket: `ws://localhost:8005/ws` (hospedado: `wss://agents.dooers.ai/<agent-id>/ws`)
- Health: `/health`

Crie um blueprint no Studio apontando para a URL do WebSocket e configure as chaves LLM na UI.

## Deploy com Dooers CLI

Instale o CLI:

```bash
pip install dooers-cli
# ou: uv tool install dooers-cli
```

Autentique e faça push do agente (build da imagem + registro na plataforma):

```bash
dooers login
dooers push
```

O CLI lê `dooers.yaml` e o `Dockerfile`. As variáveis de produção (incluindo `OPENAI_API_KEY` e
`AGENT_DATABASE_*`) devem estar num arquivo **`env.prod`** na raiz: o `dooers push` envia o projeto e
o deploy injeta cada linha do `env.prod` como variável de ambiente no runtime. (O `.env` local **não**
é enviado — ele fica só para o dev local.) Use `env.prod.example` como template. Nunca commite `env.prod`.

**Guia completo:** [docs/08-deploy.md](docs/08-deploy.md) (checklist, pós-deploy no Studio, CI, prompt para Cursor).

## Banco gerenciado pela Dooers (opcional)

Em vez de fornecer seu próprio PostgreSQL (`AGENT_DATABASE_*`), a plataforma pode provisionar um
banco **por agente** (AlloyDB), conectado via **IAM, sem senha**. Três passos:

1. No `dooers.yaml`: `database: { type: dooers }` → o `dooers push` provisiona o banco.
2. No `env.prod`: `AGENT_DATABASE_TYPE=dooers` e `APP_POSTGRES_POOL_ENABLED=false` → o SDK conecta via IAM; o pool SQL do starter (tabelas RAG) fica desligado.
3. Dependência (já no starter): `dooers-agents-server[dooers,observability]>=0.16.1`.

O deploy injeta `AGENT_DATABASE_INSTANCE`/`USER`/`NAME` automaticamente — **não** configure
`AGENT_DATABASE_HOST`, `PORT`, `USER`, `PASSWORD` nem `GOOGLE_APPLICATION_CREDENTIALS` no `env.prod`.
O `.env` local continua com `AGENT_DATABASE_TYPE=postgres` (ou omitido), então o dev local segue no
seu Postgres. **Atenção:** o banco gerenciado elimina só o `AGENT_DATABASE_*` do `env.prod` — as
chaves de LLM (`OPENAI_API_KEY`, …) continuam sendo necessárias lá. A organização precisa estar
habilitada para hosting/banco gerenciado na Dooers.

Template mínimo para `env.prod` com banco gerenciado (copie de `env.prod.example`):

```bash
AGENT_DATABASE_TYPE=dooers
APP_POSTGRES_POOL_ENABLED=false
USE_API_PREFIX=false
OPENAI_API_KEY=sk-...
RAG_PIPELINE=openai
```

```bash
dooers validate   # opcional — valida yaml + Dockerfile antes do push
dooers push
```

**Do's e don'ts no `env.prod` (deploy hospedado):**

| ✅ Faça | ❌ Não faça |
|--------|------------|
| `AGENT_DATABASE_TYPE=dooers` quando `database.type: dooers` | `AGENT_DATABASE_HOST=localhost` |
| `APP_POSTGRES_POOL_ENABLED=false` com banco gerenciado | `GOOGLE_APPLICATION_CREDENTIALS=./sandbox-….json` |
| `USE_API_PREFIX=false` | Copiar o `.env` inteiro para `env.prod` (o push não envia `.env`) |
| `OPENAI_API_KEY` e demais segredos de runtime | Commitar `env.prod` no git |

Guia completo e troubleshooting: [docs/08-deploy.md](docs/08-deploy.md).

## Documentação

| Guia | Conteúdo |
|------|----------|
| [docs/00-quickstart.md](docs/00-quickstart.md) | Setup local passo a passo |
| [docs/01-anatomy.md](docs/01-anatomy.md) | Handler, workflow, capabilities |
| [docs/02-sdk-contract.md](docs/02-sdk-contract.md) | API do handler (`send`, `incoming`, `memory`) |
| [docs/03-capabilities.md](docs/03-capabilities.md) | Criar capabilities e handoffs |
| [docs/04-rag.md](docs/04-rag.md) | Base de conhecimento |
| [docs/05-uploads.md](docs/05-uploads.md) | Anexos no chat |
| [docs/06-forms.md](docs/06-forms.md) | Formulários na UI |
| [docs/07-channels.md](docs/07-channels.md) | UI (`/ws`), public chat, dispatch, WhatsApp |
| [docs/08-deploy.md](docs/08-deploy.md) | **`dooers push`** — guia completo + prompt para IA |
| [docs/09-charts.md](docs/09-charts.md) | Gráficos BI no chat (`send.chart`) |
| [docs/10-observability.md](docs/10-observability.md) | OpenTelemetry / traces na org |
| [docs/recipes/deploy-with-dooers-push.md](docs/recipes/deploy-with-dooers-push.md) | Checklist e prompt copiável para deploy |
| [docs/recipes/](docs/recipes/) | Receitas copiáveis |

## Estrutura do projeto

```
src/
  main.py                 # FastAPI — rotas HTTP/WS
  modules/agent/
    agent.py              # Handler principal
    workflow.py           # Orquestração OpenAI Agents SDK
    capabilities/         # Uma capability por domínio
    schemas.py            # Settings do Studio
  modules/rag/            # Ingest + file search
  modules/channels/       # WhatsApp dispatch
  modules/upload/         # /uploads e /settings-upload
migrations/               # SQL RAG
dooers.yaml               # Metadados do blueprint
docs/                     # Guias para humanos e LLMs
```

## Para usar com Cursor / Claude Code

**Skill principal:** [skills.md](skills.md) — instruções completas para criar agentes Dooers + integrações.

Exemplo de prompt:

> Crie um agente conectado ao meu Gmail com base no skill Dooers:  
> https://github.com/Dooers-ai/dooers-starter/blob/main/skills.md

Com o repo local: referencie `skills.md` ou o skill `.cursor/skills/dooers-agent/`.

Docs detalhados: `docs/01-anatomy.md`, `docs/03-capabilities.md`.

## Licença

MIT — veja [LICENSE](LICENSE).
