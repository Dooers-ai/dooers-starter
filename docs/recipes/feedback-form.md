# Recipe: formulário de feedback

Padrão para pedir dados estruturados ao usuário sem sair do fluxo.

1. Tool `request_feedback_form` (em `core/tools.py`) retorna `{"requiresForm": true, "formType": "feedback"}` e registra a chamada.
2. No handler, após o `WorkflowOutcome`, verifique `"request_feedback_form" in outcome.tools_called` e emita `send.form(...)` com `send.form_select` / `send.form_text`.
3. No turno seguinte, `incoming.form_data` chega preenchido; `form_data_to_text` (em `agent.py`) já o converte em texto para o modelo. Para campos específicos, trate antes dessa conversão.
4. `incoming.form_cancelled` → responda e encerre o turno.

```python
if "request_feedback_form" in outcome.tools_called:
    yield send.form(
        "Como foi sua experiência?",
        [
            send.form_select("rating", label="Nota", order=1, required=True,
                             options=[{"value": str(n), "label": str(n)} for n in range(5, 0, -1)]),
            send.form_text("comment", label="Comentário", order=2, required=False),
        ],
        submit_label="Enviar",
    )
    yield send.run_end()
    return
```

Lembre de declarar a tool em `core/tool_catalog.py` e, se quiser que o modelo saiba quando pedir feedback, descreva o gatilho numa Skill.

Ver [../06-forms.md](../06-forms.md).
