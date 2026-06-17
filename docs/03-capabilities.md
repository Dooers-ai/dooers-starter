# Capabilities

Capabilities são **agentes especializados** no grafo OpenAI Agents SDK, ligados por **handoffs**.

## Estrutura

```
capabilities/
  cortex.py      # Entrada — triagem e RAG geral
  feedback.py    # Exemplo — coleta feedback
  guard.py       # Guardrails
  minha_area.py  # ← adicione aqui
```

## Criar uma capability

1. Crie `src/modules/agent/capabilities/minha_area.py`:

```python
from agents import Agent, function_tool

@function_tool
def consultar_pedido(pedido_id: str) -> str:
    """Consulta status de um pedido pelo ID."""
    return f"Pedido {pedido_id}: em separação"

async def create_minha_area(agent_id: str, agent_settings: dict) -> Agent:
    return Agent(
        name="pedidos",
        instructions="Você ajuda com pedidos. Use consultar_pedido quando souber o ID.",
        tools=[consultar_pedido],
        handoff_description="Dúvidas sobre pedidos, entregas e rastreio.",
    )
```

2. Registe em `workflow.py`:

```python
from src.modules.agent.capabilities.minha_area import create_minha_area

async def _create_additional_capabilities(agent_id, agent_settings):
    pedidos = await create_minha_area(agent_id, agent_settings)
    return [pedidos]
```

O loop existente já faz `cortex.handoffs.append(agent)`.

3. Ajuste instruções do **cortex** se necessário (em `schemas.py` → `system_prompt`).

## Handoffs encadeados

Para grafos com vários níveis de especialista:

```python
suporte = await create_suporte(...)
escalacao = await create_escalacao(...)
cortex.handoffs.append(suporte)
suporte.handoffs.append(escalacao)
```

Ver `workflow.py` e `capabilities/feedback.py` neste repositório.

## RAG por capability

Limite tools de conhecimento a campos específicos:

```python
cortex = await create_cortex(
    agent_id=agent_id,
    agent_settings=agent_settings,
    attach_knowledge_tools=True,
    knowledge_field_allowlist=("knowledge_files",),  # só este campo
)
```

## Tools vs handoffs

| Use handoff quando… | Use tool quando… |
|---------------------|------------------|
| Domínio distinto com instruções próprias | Ação pontual (API, cálculo) |
| Conversa longa no especialista | Dados estruturados rápidos |
| RAG com escopo diferente | Side-effect idempotente |

## Exemplo no starter: feedback

`feedback.py` expõe `request_feedback_form` → handler detecta `requiresForm` → emite `send.form()`.

Ver [06-forms.md](06-forms.md) e `src/modules/agent/agent.py`.
