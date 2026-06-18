# Recipe: resposta proativa via dispatch

## Código

```python
from dooers.agents.server import User

async def notify_user(agent_server, agent_id: str, user_id: str, message: str):
    stream = await agent_server.dispatch(
        dooers_agent_handler,
        agent_id,
        message=message,
        user=User(user_id=user_id, user_name="Cliente"),
        channel="api",
    )
    async for _ in stream:
        pass
    return stream.thread_id
```

## Uso

Chame de um cron, fila ou webhook seu — **não** exponha endpoint público sem autenticação.

O handler trata como turno normal: persiste na thread e aparece na UI.
