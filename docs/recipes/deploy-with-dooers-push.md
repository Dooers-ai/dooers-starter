# Recipe: deploy com `dooers push`

Passo a passo para criadores e para IAs que ajudam no deploy.

## Pré-condições

O criador já tem:

- Projeto clonado deste starter
- Conta Dooers com Studio
- Postgres de produção acessível pelo runtime
- `dooers-cli` instalável (`pip install dooers-cli`)

## Checklist da IA antes de sugerir push

```
[ ] dooers.yaml — name e description atualizados
[ ] API_AGENT_NAME em .env.example alinhado ao nome do serviço
[ ] Dockerfile presente na raiz
[ ] Nenhum segredo em ficheiros tracked (git status limpo de .env / *.json keys)
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
> Variáveis no painel de deploy do runtime:
> - `AGENT_DATABASE_*`
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
| `dooers.yaml` inválido | Corrigir YAML, `protocol_version: "2"` |
| Dockerfile missing | Usar o Dockerfile do starter |
| Port mismatch | `EXPOSE 8005` + `HTTP_PORT=8005` |
| Handler path | WebSocket em `{api_prefix}/ws` via `main.py` |
