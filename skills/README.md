# Built-in Skills

Every `*.md` file in this folder (except this README) is a Skill shipped with the agent. Creators
can add more in Studio (field **Skills**); a Studio Skill with the same `id` overrides the built-in.

Format:

```markdown
---
id: refund-policy                  # [a-z0-9][a-z0-9_-]{1,79}
name: Política de reembolso        # ≤ 120 chars
description: Como tratar pedidos de reembolso e troca.   # ≤ 500 chars — this is what the model sees in the catalog
requires_tools: [search_knowledge] # optional; must exist in src/modules/agent/core/tool_catalog.py
---
Step-by-step instructions the model follows after calling `load_skill`.
```

The prompt carries only `id` + `description`. The body enters the conversation as the result of the
`load_skill` tool, so write the description as a trigger ("when to use") and the body as a procedure.
