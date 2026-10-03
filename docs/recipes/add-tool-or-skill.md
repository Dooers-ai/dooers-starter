# Recipe: adicionar uma tool ou uma Skill

Prompt copiável para Cursor / Claude Code:

```
Adicione ao agente a capacidade de <descrever>. Siga docs/03-capabilities.md:

- Se for um procedimento/política: crie skills/<id>.md com frontmatter (id, name, description como gatilho, requires_tools).
- Se for uma ação com dados externos: ToolSpec em core/tool_catalog.py, implementação em core/tools.py
  (valida args, erros de negócio como texto, saída compacta), registre em ALL_TOOLS e, se precisar de
  credenciais, campos PASSWORD em schemas.py lidos de ctx.context.agent_settings.
- Não crie agentes/handoffs. Não coloque dados voláteis em core/policies.py.
- Rode uv run poe check && uv run poe test.
```

Checklist:

- [ ] `ToolSpec` + função `@function_tool` + `ALL_TOOLS` (tools) ou `skills/<id>.md` (Skills)
- [ ] `_TOOL_DISPLAY` em `workflow.py` para rótulo amigável na UI (opcional)
- [ ] Campos de credenciais em `schemas.py` (CREATOR, PASSWORD) — veja `external-service-credentials.md`
- [ ] `uv run poe test` verde (o teste de catálogo falha se a tool não estiver registrada)
- [ ] Testar no chat: a Skill deve aparecer no catálogo e ser carregada via `load_skill` quando o pedido bater com a `description`
