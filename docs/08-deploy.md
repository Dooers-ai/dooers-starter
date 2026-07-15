# Deploy com `dooers push`

Guia para **criadores humanos** e para **assistentes de IA** (Cursor, Claude Code) publicarem o agente na Dooers.

## Resumo em 30 segundos

```bash
pip install dooers-cli          # ou: uv tool install dooers-cli
dooers login                    # autentica na conta Dooers (organização com Studio)
uv run poe check                # lint local (recomendado antes do push)
dooers validate                 # valida dooers.yaml + Dockerfile (opcional)
dooers push                     # build da imagem + deploy + registro do blueprint
```

Antes do push: crie o `env.prod` com os segredos de produção (ver aviso abaixo). Depois do push: revise o
blueprint no **Studio** (Messages URL já é gravada pelo push — ver [Pós-deploy](#pós-deploy-no-studio)).

---

## O que o `dooers push` faz

> ⚠️ **Segredos (runtime):** as variáveis de produção do container vêm do ficheiro
> **`env.prod`** (o `dooers push` injeta `env.<env>` como variáveis de ambiente no runtime). O `.env`
> local **não** é injetado — serve apenas para `poe dev`. Esse é hoje o **único** caminho para
> `OPENAI_API_KEY`, `AGENT_DATABASE_*` etc. chegarem ao container. O `.gitignore` mantém ambos fora do
> git — nunca commite segredos.

Em alto nível, o CLI:

1. Lê `dooers.yaml` na raiz do projeto (precisa de `agent_id` + `organization_id` — ver pré-requisitos)
2. Arquiva o projeto e faz build da imagem com o `Dockerfile`
3. Publica a imagem no registry da plataforma
4. Sobe/atualiza o runtime do agente (container), injetando as variáveis de `env.prod`
5. Registra ou atualiza o blueprint com metadados do `dooers.yaml` (incl. a URL de mensagens)

### URLs e o prefixo do agente (leia com atenção)

O agente **serve todas as rotas na raiz `/`** (com `USE_API_PREFIX=false`, o padrão). Em produção ele
fica atrás do load balancer da Dooers, acessível em:

```
https://agents.dooers.ai/<agent-id>/…
```

O LB casa `/<agent-id>` (e `/<agent-id>/*`), **remove esse prefixo** e encaminha para o container. Ou
seja: **o agente nunca vê o próprio `/<agent-id>`** — ele sempre recebe `/…`. Por isso `message_path` no
`dooers.yaml` é `/` e `USE_API_PREFIX` deve ficar `false` para deploys hospedados.

| Rota (o agente serve) | URL pública (o LB roteia) | Uso |
|-----------------------|---------------------------|-----|
| `/ws` | `wss://agents.dooers.ai/<agent-id>/ws` | Chat na UI Dooers |
| `GET /health` | `https://agents.dooers.ai/<agent-id>/health` | Health check |
| `POST /whatsapp/inbound` | `https://agents.dooers.ai/<agent-id>/whatsapp/inbound` | WhatsApp (se `whatsapp.enabled: true`) |
| `POST /uploads` | `https://agents.dooers.ai/<agent-id>/uploads` | Anexos de chat |
| `POST /settings-upload` | `https://agents.dooers.ai/<agent-id>/settings-upload` | Upload RAG |
| `GET /audio/{ref_id}` | `https://agents.dooers.ai/<agent-id>/audio/{ref_id}` | Áudio TTS |

**Por isso `USE_API_PREFIX` deve ser `false` (o padrão) em produção.** Assim as rotas do agente ficam em
`/ws`, `/uploads`, `/settings-upload`, `/whatsapp/inbound` — batendo com o que a plataforma chama após o
strip do prefixo. Com `USE_API_PREFIX=true` as rotas iriam para `/api/{env}/{name}/…` e o chat/uploads
dariam 404.

> `api_prefix` (`/api/{env}/{name}`) só existe quando `USE_API_PREFIX=true`, um modo de dev local para
> rodar vários agentes atrás de um proxy compartilhado. **Não use em produção.**

---

## Pré-requisitos (checklist)

Antes do primeiro `dooers push`, confirme:

### Conta e ferramentas

- [ ] Conta Dooers com plano **Pro** ou **Max** (Studio)
- [ ] `dooers-cli` instalado (`pip show dooers-cli` — versão ≥ 0.8.0 recomendada)
- [ ] Docker disponível localmente **ou** build remoto feito pelo CLI (depende da versão do CLI)
- [ ] Projeto baseado neste starter (ou equivalente com `dooers.yaml` + `Dockerfile`)
- [ ] Agente registrado: `dooers agents create --name "<nome>"` rodado uma vez nesta pasta, para
      gravar `agent_id` + `organization_id` no `dooers.yaml` (o push é rejeitado sem eles)

### Ficheiros na raiz (obrigatórios para o CLI)

| Ficheiro | Função |
|----------|--------|
| `dooers.yaml` | Metadados do blueprint — **requer** `agent_id` + `organization_id` (de `dooers agents create`) |
| `Dockerfile` | Imagem de produção — deve escutar em `$PORT` (Cloud Run injeta 8080), não numa porta fixa |
| `pyproject.toml` | Dependências Python (`dooers-agents-server`, etc.) |
| `env.prod` | Variáveis de produção — **injetadas no runtime pelo `dooers push`** (nunca commitar) |
| `.env` | Variáveis de dev local (`poe dev`) — **não** injetadas no deploy (nunca commitar) |

### Ficheiros que **nunca** devem ir para o git

- `.env` e `env.prod` — segredos
- `gcp-service-account.json` ou qualquer JSON de service account
- Chaves API em código

Estão no `.gitignore`. A IA **não deve** adicionar estes ficheiros ao commit.

### Infra de produção (no `env.prod`, injetado no runtime)

Estas variáveis vão no `env.prod` da raiz — o `dooers push` as injeta no runtime. Sem `OPENAI_API_KEY` o
RAG fica indisponível; sem um `AGENT_DATABASE_*` apontando para um Postgres acessível, chat/threads
ficam indisponíveis (o serviço sobe em modo degradado, mas não funciona de verdade).

| Recurso | Onde configurar |
|---------|-----------------|
| PostgreSQL acessível pelo runtime | Provisione você (DB gerenciado) e aponte `AGENT_DATABASE_*` para ele — ou use `database.type: dooers` (ver README) |
| `OPENAI_API_KEY` | `env.prod` (RAG + STT/TTS) |
| `AGENT_DATABASE_*` | `env.prod` — **somente** com `database.type: postgres` (host/port/user/password/name do seu Postgres acessível pelo Cloud Run, **não** `localhost`) |
| `AGENT_DATABASE_TYPE=dooers` | `env.prod` — com `database.type: dooers` no yaml; **não** defina host/senha |
| `APP_POSTGRES_POOL_ENABLED=false` | `env.prod` — **obrigatório** com banco gerenciado (`dooers`); desliga o pool SQL do starter (tabelas RAG) que usa DSN com senha |
| `USE_API_PREFIX=false` | `env.prod` — obrigatório para deploys hospedados (rotas na raiz `/`) |
| GCS/Azure (opcional) | `env.prod` — credenciais + flags `STORE_*` (não use `GOOGLE_APPLICATION_CREDENTIALS` com path local no `env.prod`) |

Chaves LLM de chat (`provider_api_key`) vão no **Studio** (settings do blueprint), não no Dockerfile.

### `env.prod` com banco gerenciado (`database.type: dooers`)

Use o template `env.prod.example`. Mínimo:

```bash
AGENT_DATABASE_TYPE=dooers
APP_POSTGRES_POOL_ENABLED=false
USE_API_PREFIX=false
OPENAI_API_KEY=sk-...
RAG_PIPELINE=openai
```

**Não inclua** no `env.prod`: `AGENT_DATABASE_HOST`, `AGENT_DATABASE_USER`, `AGENT_DATABASE_PASSWORD`,
`GOOGLE_APPLICATION_CREDENTIALS`. O Cloud Run usa ADC (service account do tenant); um path `./sandbox-….json`
causa `DefaultCredentialsError` no container.

O starter tem **dois** caminhos de Postgres:

| Caminho | Quem usa | Com `dooers` |
|---------|----------|--------------|
| SDK (`agent_server.ensure_initialized`) | Threads, settings, eventos | AlloyDB via IAM — funciona |
| App pool (`init_pool` / `APP_POSTGRES_POOL_ENABLED`) | Metadados SQL do RAG (`agent_rag_vector_store`) | Desligado — DSN com senha é incompatível com user IAM |

Chat e persistência do SDK funcionam com `APP_POSTGRES_POOL_ENABLED=false`. Upload RAG via
`/settings-upload` que depende das tabelas SQL do starter fica indisponível até suporte futuro ao pool
em banco gerenciado — ou use Postgres próprio com `APP_POSTGRES_POOL_ENABLED=true`.

---

## Passo a passo — primeiro deploy

### 1. Registrar e personalizar `dooers.yaml`

Registre o agente uma vez (grava `agent_id` + `organization_id`), depois edite nome, descrição e perfil:

```bash
dooers agents create --name "Suporte ACME"   # adiciona agent_id + organization_id ao dooers.yaml
```

```yaml
protocol_version: "2"
agent_id: <uuid>            # ← gerado por `dooers agents create` (obrigatório)
organization_id: <uuid>     # ← gerado por `dooers agents create` (obrigatório)
name: Suporte ACME          # ← nome visível no marketplace/studio
description: Agente de suporte da ACME
whatsapp:
  enabled: true
  path: /whatsapp/inbound
```

### 2. Criar `env.prod` de produção

Use `.env.example` como referência dos nomes. Crie um ficheiro `env.prod` na raiz — o `dooers push`
injeta cada chave dele como variável de ambiente no runtime. Nunca commite o ficheiro.

Mínimo para produção:

```env
USE_API_PREFIX=false
AGENT_DATABASE_HOST=...
AGENT_DATABASE_PASSWORD=...
OPENAI_API_KEY=...
```

> `USE_API_PREFIX=false` é o padrão e o correto para deploys hospedados (rotas na raiz `/`, casando com
> o strip de prefixo do LB).

### 3. Testar localmente

```bash
uv sync --extra dev
uv run poe dev
curl http://localhost:8005/health
```

### 4. Instalar e autenticar o CLI

```bash
pip install dooers-cli
# ou: uv tool install dooers-cli

dooers login
# Abre browser ou pede token — associa ao CLI a sua organização
```

Verifique: `dooers whoami` (se disponível na sua versão do CLI).

### 5. Validar (recomendado)

```bash
dooers validate
```

Corrige erros reportados (YAML inválido, Dockerfile ausente, campos obrigatórios em `dooers.yaml`) **antes** do push.

### 6. Deploy

```bash
dooers push
```

O CLI mostra URL do serviço, logs de build e ID do blueprint quando concluir.

Flags adicionais dependem da versão do CLI — consulte:

```bash
dooers push --help
```

---

## Pós-deploy no Studio

O `dooers push` sobe o runtime e já grava a **Messages URL** no blueprint (derivada da URL deployada +
`message_path`), então normalmente você não precisa configurá-la à mão. Confira e complete o resto:

1. **Studio** → abra o blueprint criado/atualizado pelo push
2. **Messages URL** — confirme que ficou `wss://agents.dooers.ai/<agent-id>/ws` (com `message_path: /`,
   fica `wss://agents.dooers.ai/<agent-id>`). Não inclua `api_prefix`.
3. **Runtime API key** — gere e guarde no blueprint
4. **Settings** — configure modelo LLM e `provider_api_key` na UI
5. **Ativar** o blueprint → **Publicar** (se marketplace) → **Contratar** num time
6. **WhatsApp** (opcional) — conectar instância no painel de canais; inbound é
   `https://agents.dooers.ai/<agent-id>/whatsapp/inbound`

Teste: abra o chat do worker contratado e envie uma mensagem.

---

## Deploy em CI (GitHub Actions)

Para pipeline sem browser (`dooers login` interativo):

```yaml
name: Deploy agent
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Dooers CLI
        run: pip install dooers-cli

      - name: Lint
        run: |
          pip install uv
          uv sync --extra dev
          uv run poe check

      - name: Push to Dooers
        env:
          DOOERS_API_TOKEN: ${{ secrets.DOOERS_API_TOKEN }}
        run: dooers push
```

Gere `DOOERS_API_TOKEN` no painel da organização (Settings → API / CLI tokens). Não use `.env` no CI.

---

## Troubleshooting

| Problema | Causa provável | Ação |
|----------|----------------|------|
| `dooers: command not found` | CLI não instalado | `pip install dooers-cli` ou `uv tool install dooers-cli` |
| `PushResponse.image Field required` | CLI desatualizado | Atualize: `pip install -U dooers-cli` (≥ 0.8.0) |
| Push rejeitado (`field required: agent_id` / `organization_id`) | `dooers.yaml` sem identidade | Rode `dooers agents create` nesta pasta antes do push |
| `unauthorized` no push | Sessão expirada | `dooers login` de novo |
| Build Docker falha | Dependência de sistema | Ajuste `Dockerfile` (ex.: `libpq-dev` para Postgres) |
| Deploy falha: "container failed to start and listen on PORT 8080" | Dockerfile escuta porta fixa, ou crash no startup | `CMD` deve usar `--port ${PORT:-8080}`; veja linhas abaixo |
| Deploy falha: `DefaultCredentialsError` / `GOOGLE_APPLICATION_CREDENTIALS` | Path de JSON local no `env.prod` | Remova `GOOGLE_APPLICATION_CREDENTIALS` do `env.prod`; Cloud Run usa ADC |
| Deploy falha: `ValueError: '@localhost:5432'` em `init_pool` | `APP_POSTGRES_POOL_ENABLED=true` com user IAM (`tenant-…@dooers-agents.iam`) | Defina `APP_POSTGRES_POOL_ENABLED=false` no `env.prod` |
| Deploy falha: connection refused em `localhost:5432` | `AGENT_DATABASE_HOST=localhost` no `env.prod` | Com banco gerenciado: remova `AGENT_DATABASE_HOST`; com Postgres próprio: use host acessível pelo Cloud Run |
| Deploy "sobe" mas a URL dá 503 / crash-loop | Faltou `OPENAI_API_KEY` ou DB inacessível no `env.prod` | Preencha o `env.prod` e re-deploy |
| Health OK mas chat não conecta | Messages URL errada, ou rotas sob `api_prefix` | Confira `wss://agents.dooers.ai/<agent-id>/ws` e `USE_API_PREFIX=false` |
| `/uploads`, `/ws` ou `/whatsapp/inbound` dão 404 | `USE_API_PREFIX=true` no deploy (rotas ficaram sob `/api/...`) | Defina `USE_API_PREFIX=false` no `env.prod` e re-deploy |
| Agente sobe mas LLM não responde | Settings vazias | Configure LLM + API key no Studio |
| RAG não indexa | `OPENAI_API_KEY` ausente no runtime, ou pool SQL desligado | Inclua `OPENAI_API_KEY` no `env.prod`; com `APP_POSTGRES_POOL_ENABLED=false`, metadados SQL do RAG ficam off |
| WhatsApp não chega | HMAC / URL inbound | `whatsapp.enabled: true` no yaml; URL correta no provisionamento |

---

## Para assistentes de IA (Cursor / Claude Code)

### O que a IA **pode** fazer no deploy

- Editar `dooers.yaml` (nome, descrição, perfil, `database.type`)
- Ajustar `Dockerfile` e `pyproject.toml`
- Garantir `main.py` só chama `init_pool()` quando `APP_POSTGRES_POOL_ENABLED=true`
- Correr `uv run poe check` e corrigir lint
- Correr `dooers validate` e corrigir erros estruturais
- Gerar `env.prod` a partir de `env.prod.example` (managed DB ou Postgres próprio)
- Listar as variáveis de ambiente necessárias para o criador preencher no `env.prod` (injetado no deploy)

### O que a IA **não deve** fazer

- Commitar `.env`, `env.prod`, service account JSON ou API keys
- Colocar `GOOGLE_APPLICATION_CREDENTIALS` ou `AGENT_DATABASE_HOST=localhost` no `env.prod` de produção
- Deixar `APP_POSTGRES_POOL_ENABLED=true` quando `AGENT_DATABASE_TYPE=dooers`
- Inventar flags do CLI — usar `dooers push --help`
- Executar `dooers login` ou `dooers push` sem o criador autenticado (requer conta e token)
- Documentar APIs ou serviços Dooers fora dos pacotes públicos

### Prompt copiável para o criador

Cole no Cursor/Claude Code:

```
Quero fazer deploy deste agente na Dooers.

Siga docs/08-deploy.md e docs/recipes/deploy-with-dooers-push.md:

1. Revise dooers.yaml (nome, descrição, whatsapp.enabled, database.type).
2. Se database.type=dooers: env.prod com AGENT_DATABASE_TYPE=dooers e APP_POSTGRES_POOL_ENABLED=false;
   sem GOOGLE_APPLICATION_CREDENTIALS nem AGENT_DATABASE_HOST.
3. Confirme que Dockerfile e pyproject.toml estão corretos.
4. Rode uv run poe check e corrija erros.
5. Gere env.prod a partir de env.prod.example (não commite).
6. Liste as variáveis que ainda preciso preencher.
7. Diga os comandos exatos que EU devo rodar: dooers login e dooers push.
8. Após o push, diga o que configurar no Studio (Messages URL, runtime API key, LLM settings).

Não commite segredos. Não rode dooers login/push por mim — só me guie.
```

Recipe detalhada: [recipes/deploy-with-dooers-push.md](recipes/deploy-with-dooers-push.md).

---

## Alternativa sem CLI

Se o CLI não estiver disponível:

1. `docker build -t my-agent .`
2. Push para o seu registry
3. Deploy no Cloud Run / K8s
4. Registre manualmente a URL WebSocket no Studio

O `dooers push` automatiza estes passos na infra Dooers.
