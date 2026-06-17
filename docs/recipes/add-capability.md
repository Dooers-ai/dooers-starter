# Recipe: adicionar capability

## Prompt para Cursor / Claude Code

```
Siga docs/03-capabilities.md e docs/01-anatomy.md.

Adicione uma capability "suporte" que:
- Responde dúvidas sobre horário de atendimento (9h–18h)
- Tem handoff_description claro
- É ligada ao cortex em workflow.py
- Não altere arquivos fora de capabilities/ e workflow.py
```

## Checklist manual

- [ ] `capabilities/suporte.py` com `create_suporte()`
- [ ] Import + registro em `_create_additional_capabilities`
- [ ] Testar handoff: "qual o horário de atendimento?"
- [ ] `uv run poe check`
