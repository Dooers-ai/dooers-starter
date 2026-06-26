# Dooers Agent Starter

Starter kit oficial para criar agentes de IA na plataforma [Dooers](https://dooers.ai): FastAPI + **dooers-agents-server** SDK, arquitetura por **capabilities**, RAG, formulários na UI, uploads, WhatsApp e deploy com **`dooers push`**.

Destinado a criadores que usam ferramentas como Cursor ou Claude Code — use **[skills.md](skills.md)** como skill principal (URL compartilhável para prompts).

## Pacotes públicos Dooers

Este starter usa apenas artefactos publicados:

| Pacote | Uso |
|--------|-----|
| [`dooers-agents-server`](https://github.com/Dooers-ai/dooers-agents-server) | SDK Python — handler, threads, dispatch, WhatsApp, RAG |
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

- WebSocket: `{SERVICE_URL}{api_prefix}/ws`
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
`AGENT_DATABASE_*`) devem estar no `.env` da raiz: **o `dooers push` envia o `.env`** e injeta cada
linha como variável de ambiente no runtime. O `.gitignore` mantém o `.env` fora do git, mas o push
**ainda o envia** — portanto preencha-o com valores de produção e **nunca** o commite.

**Guia completo:** [docs/08-deploy.md](docs/08-deploy.md) (checklist, pós-deploy no Studio, CI, prompt para Cursor).

```bash
dooers validate   # opcional — valida yaml + Dockerfile antes do push
dooers push
```

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
