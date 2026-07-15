# Recipe: serviços externos que exigem conta e chaves de API

Sempre que você (IA ou criador) adicionar uma integração com um serviço externo que exige **conta**,
**chave de API**, **OAuth** ou **billing** (Stripe, SendGrid, Google, Slack, um ERP, etc.), o agente **não**
pode assumir que a chave existe. Há duas responsabilidades:

1. **No desenvolvimento** — instruir o solicitante a ter a conta e gerar as chaves necessárias.
2. **Em runtime** — detectar chaves faltando e pedi-las no chat via formulário, gravando em settings.

---

## 1. Responsabilidade no desenvolvimento (IA que constrói o agente)

Ao integrar um serviço externo, a IA **deve perguntar e orientar** o solicitante **antes** de fixar o desenho:

1. **Já tem conta?** O usuário já possui conta em `<serviço>`, ou precisa criar?
2. **Onde guardar a credencial?** Ofereça e deixe o usuário escolher (pode combinar):
   - **Env vars** (`.env` / `env.prod`) — segredo de deploy, pouco rotacionado
   - **Agent settings schema** (`SettingsField` no Studio) — editável sem novo push
   - **Captura via formulário no chat** — `send.form` + `settings.set` em runtime
3. **Formatos de autenticação** que a ferramenta disponibiliza — explique as opções reais (API key,
   Bearer, Basic, OAuth refresh, service account JSON, webhook HMAC, etc.), onde gerar, escopos mínimos
   e se há billing/plano pago.

Sempre informe também:

- **Onde gerar a chave:** caminho no painel (ex.: *Stripe → Developers → API keys*) + link direto quando souber.
- **Nunca invente nem hardcode chaves.** Não commite `.env`/`env.prod`/JSON de credenciais.

> Regra: a IA **pergunta** o formato de armazenamento, descreve **como o humano obtém** as credenciais e
> **onde colá-las**, mas **não** executa o cadastro nem gera as chaves pelo usuário.

### Onde a chave é armazenada (recomendação padrão)

Se o usuário não tiver preferência, use **settings** (PASSWORD) — preenchível no Studio **ou** via formulário
no chat (seção 2), sem re-deploy. Só use env vars sozinhas quando o usuário pedir explicitamente. Adicione em
`src/modules/agent/schemas.py`:

```python
SettingsField(
    id="stripe_api_key",
    type=SettingsFieldType.PASSWORD,   # armazenada como segredo
    label="Stripe — Secret key (sk_...)",
    placeholder="Crie em Stripe → Developers → API keys",
    required=True,
    visibility=SettingsFieldVisibility.CREATOR,
),
```

E leia a partir de settings (nunca hardcoded):

```python
async def create_billing_capability(agent_id, agent_settings):
    api_key = (agent_settings.get("stripe_api_key") or "").strip()
    client = StripeClient(api_key)
    ...
```

---

## 2. Runtime — detectar chave faltando e pedir no chat

O handler pode verificar, no início do turno, se as chaves obrigatórias estão presentes. Se faltarem,
envia um **formulário de captura** e, no turno seguinte, faz **patch em settings** com o valor recebido.

### Definir os requisitos e checar

```python
# Chaves obrigatórias de serviços externos: (field_id, rótulo, onde obter)
REQUIRED_SERVICE_KEYS = [
    ("stripe_api_key", "Stripe — Secret key", "Stripe → Developers → API keys (https://dashboard.stripe.com/apikeys)"),
]


def _missing_service_keys(agent_settings: dict) -> list[tuple[str, str, str]]:
    return [
        (fid, label, where)
        for (fid, label, where) in REQUIRED_SERVICE_KEYS
        if not str(agent_settings.get(fid) or "").strip()
    ]
```

### Emitir o formulário quando faltar

```python
async def dooers_agent_handler(incoming, send, memory, analytics, settings):
    agent_id = incoming.context.agent_id or ""
    agent_settings = await settings.get_all()

    yield send.run_start(agent_id=agent_id)

    # 1) Recebeu o formulário de credenciais preenchido? Grava e segue.
    if incoming.form_data and any(fid in incoming.form_data for fid, _, _ in REQUIRED_SERVICE_KEYS):
        saved = []
        for fid, label, _where in REQUIRED_SERVICE_KEYS:
            value = str(incoming.form_data.get(fid) or "").strip()
            if value:
                await settings.set(fid, value)   # valida no schema, persiste e faz broadcast p/ o Studio
                saved.append(label)
        if saved:
            yield send.text(f"Credenciais salvas: {', '.join(saved)}. Pode continuar.")
        # segue o fluxo normal abaixo (recarregue settings se for usar já neste turno)
        agent_settings = await settings.get_all()

    # 2) Ainda falta alguma chave? Pede via formulário e encerra o turno.
    missing = _missing_service_keys(agent_settings)
    if missing:
        yield send.form(
            "Para usar essa integração, preciso das seguintes credenciais:",
            [
                send.form_text(
                    fid,
                    label=label,
                    required=True,
                    placeholder=f"Obtenha em: {where}",
                    input_type="password",   # mascara a chave na digitação
                    order=i + 1,
                )
                for i, (fid, label, where) in enumerate(missing)
            ],
            submit_label="Salvar credenciais",
            cancel_label="Agora não",
        )
        yield send.run_end()
        return

    # 3) Tudo presente — segue o fluxo normal do agente.
    ...
```

### Cancelamento

```python
if incoming.form_cancelled:
    yield send.text("Sem as credenciais eu não consigo acessar o serviço. É só me chamar quando tiver a chave.")
    yield send.run_end()
    return
```

---

## Notas importantes

- **`settings.set(field_id, value)`** só aceita `field_id` que **exista no schema** (`build_settings_schema`)
  e que não seja `readonly`. Sempre adicione o `SettingsField` (seção 1) antes de gravar.
- **Broadcast:** `settings.set` propaga um patch para o **Studio** em tempo real — o campo aparece preenchido lá.
- **Mascare a captura:** use `send.form_text(..., input_type="password")` para a chave não aparecer em claro
  na digitação, e **armazene** num `SettingsField` do tipo `PASSWORD` (fica secreto no armazenamento). Os
  elementos de form disponíveis estão em [06-forms.md](../06-forms.md).
- **Não bloqueie o boot:** chaves faltando devem degradar só a integração afetada e serem pedidas no chat —
  nunca derrubar o processo (mantém o padrão de deploy do starter).
- **Um formulário por turno**, seguido de `run_end()`.

## Checklist

```
- [ ] Informei o solicitante: conta no serviço + onde gerar a(s) chave(s) + escopos + plano/billing
- [ ] Adicionei SettingsField(PASSWORD) por credencial em schemas.py (visibility=CREATOR)
- [ ] A capability/cliente lê a chave de agent_settings (nunca hardcoded)
- [ ] Handler detecta chave faltando → send.form(...) de captura
- [ ] Ao receber form_data → settings.set(field_id, value) e segue
- [ ] Tratei form_cancelled e não derrubei o boot quando falta chave
```

Ver também: [06-forms.md](../06-forms.md) e [03-capabilities.md](../03-capabilities.md).
