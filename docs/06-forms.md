# Formulários na UI

Formulários são eventos interativos na thread — o utilizador preenche e submete; a resposta chega no próximo turno como `incoming.form_data`.

## Emitir um formulário

No handler, após lógica de negócio (ex.: tool pediu formulário):

```python
yield send.form(
    "Qual período você quer consultar?",
    [
        send.form_text("start_date", label="Data inicial", required=True, order=1),
        send.form_text("end_date", label="Data final", order=2),
    ],
    submit_label="Consultar",
    cancel_label="Cancelar",
)
yield send.run_end()
```

Elementos disponíveis: `form_text`, `form_textarea`, `form_select`, `form_radio`, `form_checkbox`, `form_file`.

## Receber resposta

```python
async def handler(incoming, send, ...):
    if incoming.form_cancelled:
        yield send.text("Cancelado.")
        yield send.run_end()
        return

    if incoming.form_data:
        start = incoming.form_data.get("start_date")
        # Tratar como nova mensagem do utilizador
        incoming.message = f"Período: {start} ..."
```

## Padrão tool → form

1. Uma tool retorna um marcador (ex.: `{"requiresForm": true, "formType": "feedback"}`)
2. O handler inspeciona `outcome.tools_called` / o resultado e emite `send.form()` em vez de texto
3. No turno seguinte, `incoming.form_data` chega ao handler — `form_data_to_text` em `agent.py` o transforma em texto para o modelo

Ver [recipes/feedback-form.md](recipes/feedback-form.md).

## Ficheiros em formulários

Use `send.form_file(...)` e `source=form` em `POST /uploads`.

## Client SDK

```tsx
const { submit, cancel } = useForm(eventId, formData, threadId);
await submit({ rating: "5", comment: "Ótimo!" });
```

O chat na **UI Dooers** (dashboard e public chat) renderiza formulários automaticamente via `dooers-agents-client`.

## Capturar credenciais de serviços externos

Um uso comum de formulário: quando falta a chave de API de um serviço externo, o runtime pede a credencial
no chat e grava em settings com `settings.set(...)`. Ver
[recipes/external-service-credentials.md](recipes/external-service-credentials.md).

## Boas práticas

- Um formulário por turno — depois `run_end()`
- Valide campos obrigatórios no handler após submit
- Mensagens de confirmação claras após processar `form_data`
