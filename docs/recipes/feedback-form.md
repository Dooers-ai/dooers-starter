# Recipe: formulário de feedback

Já implementado no starter. Para replicar noutro domínio:

1. Tool retorna `{"requiresForm": true, "formType": "..."}`
2. Handler verifica output da tool em `new_runner_items`
3. Emite `send.form()` com elementos
4. Próximo turno: `incoming.form_data` → normalizar em `incoming.message`

Ver:

- `src/modules/agent/capabilities/feedback.py`
- `src/modules/agent/agent.py` — `_feedback_form`, `_message_from_feedback_form`

Teste no chat: "Quero deixar um feedback"
