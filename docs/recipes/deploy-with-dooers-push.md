# Recipe: deploy com `dooers push`

Passo a passo para criadores e para IAs que ajudam no deploy.

## Pré-condições

O criador já tem:

- Projeto clonado deste starter
- Conta Dooers com Studio
- Postgres de produção acessível pelo runtime (o agente conecta no startup)
- `dooers-cli` instalável (`pip install dooers-cli`)
- Agente registrado com `dooers agents create` (grava `agent_id` + `organization_id` no `dooers.yaml`)

## Checklist da IA antes de sugerir push

```
[ ] dooers.yaml — name/description atualizados E agent_id/organization_id presentes (dooers agents create)
[ ] dooers.yaml — message_path: / (rotas na raiz)
[ ] dooers.yaml — database.type: postgres OU dooers (se dooers, ver env.prod abaixo)
[ ] Dockerfile escuta em $PORT (--port ${PORT:-8080}), não numa porta fixa
[ ] env.prod gerado a partir de env.prod.example (INJETADO no runtime; nunca commitar)
[ ] env.prod — USE_API_PREFIX=false (rotas na raiz, casando com o strip de prefixo do LB)
[ ] Se database.type=dooers: AGENT_DATABASE_TYPE=dooers, APP_POSTGRES_POOL_ENABLED=false,
    SEM GOOGLE_APPLICATION_CREDENTIALS, SEM AGENT_DATABASE_HOST/USER/PASSWORD
[ ] Se database.type=postgres: AGENT_DATABASE_* apontando para Postgres acessível (não localhost)
[ ] dooers-cli ≥ 0.8.0 (pip show dooers-cli)
[ ] Nenhum segredo em ficheiros tracked no git (git status limpo de .env / env.prod / *.json keys)
[ ] uv run poe check passa
[ ] README/docs não referenciam credenciais reais
```

## Comandos (o criador executa)

```bash
# Terminal do criador — requer login interativo ou DOOERS_API_TOKEN no CI
dooers login
dooers validate    # opcional
dooers push
```

A IA pode preparar o projeto; **login e push exigem credenciais do criador**.

## Após o push — mensagem modelo para o criador

> Deploy concluído. A Messages URL já foi gravada no blueprint pelo push. Próximos passos no Studio:
>
> 1. Messages URL: confirme `wss://agents.dooers.ai/<agent-id>/ws` (não inclua `/api/...`)
> 2. Gere Runtime API key e salve no blueprint
> 3. Settings → escolha modelo LLM e cole `provider_api_key`
> 4. Ative o blueprint e contrate num time
> 5. (Opcional) Conecte WhatsApp no painel de canais
>
> Variáveis que precisam estar no `env.prod` ANTES do push (injetadas no runtime):
> - `USE_API_PREFIX=false`
> - `OPENAI_API_KEY`
> - **Postgres próprio:** `AGENT_DATABASE_*` (host acessível pelo Cloud Run, não `localhost`) + `APP_POSTGRES_POOL_ENABLED=true` se usar RAG SQL
> - **Banco gerenciado (`database.type: dooers`):** `AGENT_DATABASE_TYPE=dooers`, `APP_POSTGRES_POOL_ENABLED=false` — sem host/senha/GOOGLE_APPLICATION_CREDENTIALS

## Prompt para vibe coding

```
Objetivo: preparar este repo para dooers push.

Leia docs/08-deploy.md. Faça apenas:
- Atualizar dooers.yaml com nome "<NOME>" e descrição "<DESC>"
- Garantir que .gitignore bloqueia segredos
- Rodar uv run poe check e corrigir lint
- Gerar lista markdown das env vars de produção

NÃO rode dooers login nem dooers push.
NÃO crie nem commite ficheiros .env ou service account JSON.
No final, imprima os 3 comandos que eu devo executar no terminal.
```

## Erros comuns que a IA deve corrigir no código

| Erro / sintoma | Fix |
|----------------|-----|
| `dooers.yaml` inválido / faltam `agent_id`/`organization_id` | `protocol_version: "2"` + rodar `dooers agents create` |
| `PushResponse.image Field required` no push | Atualizar `dooers-cli` para ≥ 0.8.0 |
| Dockerfile missing | Usar o Dockerfile do starter |
| Port mismatch | `CMD` deve escutar em `$PORT` (Cloud Run injeta 8080): `--port ${PORT:-8080}` — **não** fixar 8005 |
| Handler path | WebSocket em `/ws` via `main.py` (raiz; `USE_API_PREFIX=false`) |
| `DefaultCredentialsError` no Cloud Run | Remover `GOOGLE_APPLICATION_CREDENTIALS` do `env.prod` |
| `ValueError: '@localhost:5432'` em `init_pool` | `APP_POSTGRES_POOL_ENABLED=false` quando `AGENT_DATABASE_TYPE=dooers` |
| `AGENT_DATABASE_HOST=localhost` no deploy | Remover (managed DB) ou trocar por host real (Postgres próprio) |
| `main.py` sempre chama `init_pool()` | Guard com `settings.app_postgres_pool_enabled` (padrão do starter) |
