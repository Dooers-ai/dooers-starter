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
[ ] Dockerfile escuta em $PORT (--port ${PORT:-8080}), não numa porta fixa
[ ] .env preenchido com OPENAI_API_KEY + AGENT_DATABASE_* (é ENVIADO pelo push; nunca commitar)
[ ] API_AGENT_NAME no .env alinhado ao nome do serviço
[ ] Nenhum segredo em ficheiros tracked no git (git status limpo de .env / *.json keys)
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

> Deploy concluído. Próximos passos manuais no Studio:
>
> 1. Messages URL: `wss://<host>/api/prod/<API_AGENT_NAME>/ws`
> 2. Gere Runtime API key e salve no blueprint
> 3. Settings → escolha modelo LLM e cole `provider_api_key`
> 4. Ative o blueprint e contrate num time
> 5. (Opcional) Conecte WhatsApp no painel de canais
>
> Variáveis que precisam estar no `.env` ANTES do push (o push envia o `.env` e injeta no runtime):
> - `AGENT_DATABASE_*` (apontando para um Postgres acessível)
> - `OPENAI_API_KEY`
> - `SERVICE_URL=https://<host>`
> - `API_ENVIRONMENT=prod`
> - `API_AGENT_NAME=<nome>`

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

| Erro do `dooers validate` | Fix |
|---------------------------|-----|
| `dooers.yaml` inválido / faltam `agent_id`/`organization_id` | `protocol_version: "2"` + rodar `dooers agents create` |
| Dockerfile missing | Usar o Dockerfile do starter |
| Port mismatch | `CMD` deve escutar em `$PORT` (Cloud Run injeta 8080): `--port ${PORT:-8080}` — **não** fixar 8005 |
| Handler path | WebSocket em `{api_prefix}/ws` via `main.py` |
