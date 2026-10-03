# Capacidades: Skills e Tools

O starter usa **um agente** com uma superfície de ferramentas estável e **Skills** carregadas sob demanda
(progressive disclosure). Não há grafo de handoffs: especialização vem de instruções, não de agentes extras.

| | Skill | Tool |
|--|-------|------|
| O que é | Procedimento em Markdown escrito pelo criador | Função Python com side-effect/API/cálculo |
| Quem cria | Criador (Studio) ou repo `skills/` | Desenvolvedor |
| Quando entra no contexto | Só quando o modelo chama `load_skill` | Sempre disponível (catálogo fixo) |
| Exemplos | política de reembolso, roteiro de triagem, formato de relatório | consultar pedido, criar ticket, buscar conhecimento |

## Skills

Arquivo `.md` com frontmatter:

```markdown
---
id: refund-policy
name: Política de reembolso
description: Use quando o cliente pedir reembolso, troca ou cancelamento.
requires_tools: [search_knowledge]
---
1. Pergunte o número do pedido se não vier na mensagem.
2. Busque a política vigente com `search_knowledge` ("política de reembolso <categoria>").
3. ...
```

- `id` `[a-z0-9][a-z0-9_-]{1,79}`; `name` ≤ 120; `description` ≤ 500 (é o que o modelo vê no catálogo — escreva como gatilho).
- `requires_tools` deve referenciar nomes de `core/tool_catalog.py`; o upload rejeita tools inexistentes.
- Fontes: `skills/*.md` (embutidas, vão na imagem) + campo **Skills** do Studio (`/skills-upload`). Mesmo `id` → o Studio vence.
- O prompt só carrega `id` + `description`. O corpo chega como resultado de `load_skill` e fica no histórico; em turnos seguintes
  o `RuntimeContext` detecta o marcador `Skill '<id>' loaded.` e informa ao modelo que não precisa recarregar.

Testes: `tests/test_skills.py` valida o parser e as Skills embutidas.

## Tools

Catálogo atual (`core/tool_catalog.py`):

| Tool | Função |
|------|--------|
| `load_skill` | Carrega o corpo de uma Skill |
| `search_knowledge` | RAG gerenciado Dooers nas bases do agente |
| `get_thread_document_context` | Lê/busca documentos anexados na conversa (`mode`: search/full/summary) |
| `calculate` | Aritmética determinística (AST seguro) |

### Adicionar uma tool

1. Declare em `core/tool_catalog.py`:

```python
ToolSpec("get_order_status", "Looks up an order by id in the ERP."),
```

2. Implemente em `core/tools.py` (fina: valida, chama módulo de negócio, formata string; erros esperados viram texto):

```python
@function_tool
async def get_order_status(ctx: RunContextWrapper[RuntimeContext], order_id: str) -> str:
    """Look up an order by id."""
    ctx.context.record_tool_call("get_order_status")
    order = await erp_client.get_order(order_id.strip())
    if order is None:
        return f"Order {order_id!r} not found."
    return json.dumps(order, ensure_ascii=False)
```

3. Adicione em `ALL_TOOLS` e, se quiser rótulo na UI, em `_TOOL_DISPLAY` (`workflow.py`).
4. `tests/test_prompt_and_context.py::test_tool_catalog_matches_registered_tools` garante que catálogo e registro batem.

Clientes externos ficam em `src/modules/external/<serviço>/`. Credenciais: campos `PASSWORD` no `schemas.py`
(lidos de `ctx.context.agent_settings`) ou env — veja [recipes/external-service-credentials.md](recipes/external-service-credentials.md).

## Quando ainda faz sentido outro agente

Só para tarefas internas com saída estruturada (ex.: classificador de guardrail em `core/guard.py`). Para o usuário final, mantenha um agente.

## Guardrails

Campos do Studio `guardrails_prompt` (entrada e saída), `input_guardrails_prompt`, `output_guardrails_prompt`.
Um agente classificador (`GuardDecision`) roda antes/depois do turno; tripwire → o motivo vira a resposta e o `run_end` é normal
(bloqueio de política não é falha de sistema).

## Execution guard

`core/execution_guard.py` detecta finais passivos ("vou verificar…", "aguarde um instante") e roda uma continuação com
instrução de reparo. Se insistir, responde `SAFE_FAILURE_REPLY`. Ajuste os padrões se o seu domínio usar essas frases legitimamente.
