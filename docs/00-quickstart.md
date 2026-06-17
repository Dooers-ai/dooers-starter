# Quickstart

## 1. Clone e dependências

```bash
git clone https://github.com/Dooers-ai/dooers-starter.git
cd dooers-starter
uv sync --extra dev
cp .env.example .env
```

## 2. PostgreSQL

Crie um banco local:

```sql
CREATE DATABASE dooers_agent;
```

Configure em `.env`:

```
AGENT_DATABASE_HOST=localhost
AGENT_DATABASE_PORT=5432
AGENT_DATABASE_USER=postgres
AGENT_DATABASE_PASSWORD=postgres
AGENT_DATABASE_NAME=dooers_agent
```

O SDK cria as tabelas de threads/eventos no startup. As migrações em `migrations/` criam tabelas RAG.

## 3. Chaves

| Variável | Uso |
|----------|-----|
| `OPENAI_API_KEY` | RAG (Vector Store), STT, TTS |
| `provider_api_key` (Studio) | Chat LLM (Gemini, Claude, OpenAI…) |

## 4. Rodar localmente

```bash
uv run poe dev
```

Rotas (com prefixo padrão):

- WebSocket: `ws://localhost:8005/api/dev/dooers-starter/ws`
- Health: `http://localhost:8005/health`
- Uploads: `POST /api/dev/dooers-starter/uploads`
- Settings upload: `POST /api/dev/dooers-starter/settings-upload`

## 5. Conectar ao Studio

1. Crie um blueprint no Studio (organização Pro/Max).
2. Defina **Messages URL** = URL WebSocket pública do agente.
3. Gere **Runtime API key** e salve no blueprint.
4. Configure modelo LLM e chave na aba Settings.
5. Ative o blueprint e contrate (hire) num time.

## 6. Testar sem Studio

Use o pacote `dooers-agents-client` numa página React, ou teste o health:

```bash
curl http://localhost:8005/health
```

Para dispatch programático, veja [07-channels.md](07-channels.md).

## Deploy

Depois de testar localmente, siga [docs/08-deploy.md](08-deploy.md):

```bash
pip install dooers-cli
dooers login
dooers push
```

Para preparar o deploy com Cursor/Claude Code, use o prompt em [recipes/deploy-with-dooers-push.md](recipes/deploy-with-dooers-push.md).

## Próximos passos

- [01-anatomy.md](01-anatomy.md) — entenda a arquitetura
- [03-capabilities.md](03-capabilities.md) — adicione domínios
- [08-deploy.md](08-deploy.md) — `dooers push`
