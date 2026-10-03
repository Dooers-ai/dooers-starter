# Anatomia do agente

## Um handler, três portas de entrada

```
                    ┌─────────────────────────┐
                    │  dooers_agent_handler   │
                    └───────────┬─────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
  WebSocket /ws           dispatch()            Public chat
  (UI Dooers)             (WhatsApp, webhooks)  (link público → /ws)
```

Detalhes de canais: [07-channels.md](07-channels.md).

## Camadas

```
src/
  config.py                     # Settings (env) — gateway, RAG, banco, canais
  main.py                       # FastAPI: /ws /uploads /settings-upload /skills-upload /whatsapp/inbound /audio
  modules/agent/
    agent.py                    # Handler: normaliza entrada multimodal, chama o workflow, emite eventos
    workflow.py                 # Um turno: histórico + estado volátil → Runner.run_streamed → repair → outcome
    agent_config.py             # AgentConfig do SDK (banco, storage, allow-list, hooks)
    schemas.py                  # Studio: modelo, identidade, skills, guardrails, conhecimento, áudio
    core/
      tool_catalog.py           # Superfície de ferramentas (estável, documentada)
      skills.py                 # Parser/loader de Skills (repo skills/ + uploads do Studio)
      policies.py               # Cabeçalho estático do prompt (cacheável)
      context.py                # RuntimeContext — estado por turno (data, usuário, docs, skills carregadas)
      tools.py                  # load_skill, search_knowledge, get_thread_document_context, calculate
      execution_guard.py        # Detecta respostas passivas ("vou verificar…") e força execução
      guard.py                  # Guardrails do Agents SDK a partir das políticas do Studio
      agent.py                  # build_agent(settings) — um Agent, tools fixas, guardrails
  modules/llm/                  # Gateway Dooers: cliente, resolução de modelo, sync do picker
  modules/rag/                  # RAG gerenciado Dooers: search/upload/list/delete + hidratação do Studio
  modules/doc_processing/       # Documentos anexados: extração → Markdown → chunks → tabela no banco
  modules/helpers/              # speech (STT/TTS), llm_provider (RunConfig), chart_demo, wire_content
  modules/observability/        # record_soft_failure — eventos OTEL para falhas toleradas
  modules/upload/               # /uploads (chat), /settings-upload (RAG), /skills-upload (Skills)
  modules/channels/             # WhatsApp inbound → dispatch
skills/                         # Skills embutidas (*.md com frontmatter)
tests/                          # Invariantes: catálogo de tools, parser de Skills, prompt estável, schema
```

## Fluxo de um turno

1. SDK persiste a mensagem do usuário e chama o handler com `incoming`, `send`, `memory`, `analytics`, `settings`.
2. `agent.py`: `run_start` → valida gateway → normaliza entrada:
   - áudio → `speech.transcribe` (OpenAI STT) e `send.update_user_event` com a transcrição;
   - imagem → mantida como `ImagePart` (visão nativa do modelo);
   - documento → `doc_processing.process_document_part` (extração + chunks, persistido em `agent_thread_documents`); o modelo recebe uma nota com o `document_id`.
3. `workflow.py`: carrega documentos da thread, histórico (`openai_completions`), monta o `RuntimeContext`
   (reidrata Skills já carregadas a partir do rastro de tools), constrói o agente e roda `Runner.run_streamed`.
   Cada `ToolCallItem`/`ToolCallOutputItem`/`ReasoningItem` vira `send.tool_call` / `send.tool_result` / `send.reasoning`.
4. Execution guard: se a resposta final for passiva ("vou verificar…"), roda de novo com instrução de reparo; se insistir, resposta honesta de falha.
5. Guardrails do SDK (se configurados no Studio) podem interromper antes (entrada) ou depois (saída) — o motivo vira a resposta.
6. `agent.py` emite `send.text` (+ `send.audio` se `reply_mode` pedir voz), analytics (`tool.called`, `skill.loaded`) e `run_end`.

## Prompt: estático × volátil

- `policies.build_static_instructions(settings)` depende **só** das configurações do criador: identidade, instruções, contrato de execução, grounding, catálogo de Skills (id + descrição) e catálogo de tools. Bytes idênticos a cada turno → cache de prompt do provedor (`prompt_cache_key` por agente, 16 shards por thread).
- `RuntimeContext.state_message()` é a última mensagem `system`: data, canal, usuário, bases de conhecimento com conteúdo, manifesto de documentos, Skills já carregadas.

## Onde estender

| Quero… | Editar… |
|--------|---------|
| Ensinar um procedimento (sem código) | `skills/<id>.md` ou upload no Studio ([03-capabilities.md](03-capabilities.md)) |
| Nova ação com side-effect / API externa | `core/tool_catalog.py` + `core/tools.py` + `core/agent.py` |
| Novo campo no Studio | `schemas.py` |
| Nova rota HTTP | `main.py` |
| Novo canal externo | `dispatch()` em `channels/` |
| Tipos de anexo aceitos | `AGENT_ALLOWED_CONTENT_TYPES` + `agent_config.py` |

## Anti-patterns

- Não reimplemente persistência de threads — `memory`, `settings` e `await agent_server.database()` já existem.
- Não coloque data, nome do usuário ou lista de documentos no prompt estático (quebra o cache).
- Não crie um agente por domínio com handoffs: um agente + Skills + tools estáveis é mais barato, mais previsível e mais fácil de testar.
- Não exponha credenciais da plataforma no código do agente.
