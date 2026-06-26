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

Antes do push: preencha o `.env` (segredos vão por aí — ver aviso abaixo). Depois do push: ligar o
blueprint à URL do WebSocket no **Studio** (ver [Pós-deploy](#pós-deploy-no-studio)).

---

## O que o `dooers push` faz

> ⚠️ **Segredos:** o `dooers push` **envia o `.env`** da raiz e injeta cada linha como variável de
> ambiente no runtime. Esse é hoje o **único** caminho para `OPENAI_API_KEY`, `AGENT_DATABASE_*` etc.
> chegarem ao container — não existe painel de secrets que faça essa injeção. O `.gitignore` mantém o
> `.env` fora do git, mas o push **ainda o envia**. Preencha-o com valores de produção e nunca o commite.

Em alto nível, o CLI:

1. Lê `dooers.yaml` na raiz do projeto (precisa de `agent_id` + `organization_id` — ver pré-requisitos)
2. Arquiva o projeto (incluindo o `.env`) e faz build da imagem com o `Dockerfile`
3. Publica a imagem no registry da plataforma
4. Sobe/atualiza o runtime do agente (container), injetando as variáveis do `.env`
5. Registra ou atualiza o blueprint com metadados do `dooers.yaml`

O agente em produção expõe as mesmas rotas que em local:

| Rota | Uso |
|------|-----|
| `wss://…{api_prefix}/ws` | Chat na UI Dooers |
| `GET /health` | Health check |
| `POST …/whatsapp/inbound` | WhatsApp (se `whatsapp.enabled: true`) |
| `POST …/uploads` | Anexos de chat |
| `POST …/settings-upload` | Upload RAG |

`api_prefix` = `/api/{API_ENVIRONMENT}/{API_AGENT_NAME}` (ex.: `/api/prod/meu-agente`).

---

## Pré-requisitos (checklist)

Antes do primeiro `dooers push`, confirme:

### Conta e ferramentas

- [ ] Conta Dooers com plano **Pro** ou **Max** (Studio)
- [ ] `dooers-cli` instalado (`dooers --version`)
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
| `.env` | Variáveis de produção — **enviado pelo `dooers push`** e injetado no runtime (nunca commitar) |

### Ficheiros que **nunca** devem ir para o git

- `.env` — segredos locais
- `gcp-service-account.json` ou qualquer JSON de service account
- Chaves API em código

Estão no `.gitignore`. A IA **não deve** adicionar estes ficheiros ao commit.

### Infra de produção (no `.env`, enviado pelo push)

Estas variáveis vão no `.env` da raiz — o `dooers push` as injeta no runtime. Sem `OPENAI_API_KEY` o
RAG fica indisponível; sem um `AGENT_DATABASE_*` apontando para um Postgres acessível, chat/threads
ficam indisponíveis (o serviço sobe em modo degradado, mas não funciona de verdade).

| Recurso | Onde configurar |
|---------|-----------------|
| PostgreSQL acessível pelo runtime | Provisione você (DB gerenciado) e aponte `AGENT_DATABASE_*` para ele |
| `OPENAI_API_KEY` | `.env` (RAG + STT/TTS) |
| `AGENT_DATABASE_*` | `.env` (host/port/user/password/name do seu Postgres) |
| `SERVICE_URL` | `.env` — URL pública HTTPS do agente deployado |
| `API_ENVIRONMENT=prod` | `.env` |
| `API_AGENT_NAME` | `.env` — nome estável do serviço (alinhar com URL) |
| GCS/Azure (opcional) | `.env` — credenciais + flags `STORE_*` |

Chaves LLM de chat (`provider_api_key`) vão no **Studio** (settings do blueprint), não no Dockerfile.

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

### 2. Ajustar `.env` de produção

Use `.env.example` como modelo. O `dooers push` **envia o `.env`** e injeta cada chave como variável de
ambiente no runtime — preencha com valores de produção e nunca commite o ficheiro.

Mínimo para produção:

```env
API_ENVIRONMENT=prod
API_AGENT_NAME=meu-agente
SERVICE_URL=https://meu-agente.run.dooers.ai
AGENT_DATABASE_HOST=...
AGENT_DATABASE_PASSWORD=...
OPENAI_API_KEY=...
```

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

O `dooers push` sobe o runtime; você ainda precisa ligar o blueprint à plataforma:

1. **Studio** → abra o blueprint criado/atualizado pelo push
2. **Messages URL** = `wss://{host}{api_prefix}/ws`  
   Ex.: `wss://meu-agente.run.dooers.ai/api/prod/meu-agente/ws`
3. **Runtime API key** — gere e guarde no blueprint
4. **Settings** — configure modelo LLM e `provider_api_key` na UI
5. **Ativar** o blueprint → **Publicar** (se marketplace) → **Contratar** num time
6. **WhatsApp** (opcional) — conectar instância no painel de canais; inbound aponta para `{SERVICE_URL}{api_prefix}/whatsapp/inbound`

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
| Push rejeitado (`field required: agent_id` / `organization_id`) | `dooers.yaml` sem identidade | Rode `dooers agents create` nesta pasta antes do push |
| `unauthorized` no push | Sessão expirada | `dooers login` de novo |
| Build Docker falha | Dependência de sistema | Ajuste `Dockerfile` (ex.: `libpq-dev` para Postgres) |
| Deploy falha: "container failed to start and listen on PORT 8080" | Dockerfile escuta porta fixa | `CMD` deve usar `--port ${PORT:-8080}` (não 8005) |
| Deploy "sobe" mas a URL dá 503 / crash-loop | Faltou `OPENAI_API_KEY` ou `AGENT_DATABASE_*` no `.env` | Preencha o `.env` (é enviado pelo push) e re-deploy |
| Health OK mas chat não conecta | Messages URL errada | Confira `wss://` + `api_prefix` + `/ws` |
| Agente sobe mas LLM não responde | Settings vazias | Configure LLM + API key no Studio |
| RAG não indexa | `OPENAI_API_KEY` ausente no runtime | Inclua `OPENAI_API_KEY` no `.env` (enviado pelo push) |
| WhatsApp não chega | HMAC / URL inbound | `whatsapp.enabled: true` no yaml; URL correta no provisionamento |

---

## Para assistentes de IA (Cursor / Claude Code)

### O que a IA **pode** fazer no deploy

- Editar `dooers.yaml` (nome, descrição, perfil)
- Ajustar `Dockerfile` e `pyproject.toml`
- Correr `uv run poe check` e corrigir lint
- Correr `dooers validate` e corrigir erros estruturais
- Listar as variáveis de ambiente necessárias para o criador preencher no `.env` (enviado pelo push)

### O que a IA **não deve** fazer

- Commitar `.env`, service account JSON ou API keys
- Inventar flags do CLI — usar `dooers push --help`
- Executar `dooers login` ou `dooers push` sem o criador autenticado (requer conta e token)
- Documentar APIs ou serviços Dooers fora dos pacotes públicos

### Prompt copiável para o criador

Cole no Cursor/Claude Code:

```
Quero fazer deploy deste agente na Dooers.

Siga docs/08-deploy.md e docs/recipes/deploy-with-dooers-push.md:

1. Revise dooers.yaml (nome, descrição, whatsapp.enabled).
2. Confirme que Dockerfile e pyproject.toml estão corretos.
3. Rode uv run poe check e corrija erros.
4. Liste as variáveis de ambiente que preciso configurar no painel de produção
   (não commite .env).
5. Diga os comandos exatos que EU devo rodar: dooers login e dooers push.
6. Após o push, diga o que configurar no Studio (Messages URL, runtime API key, LLM settings).

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
