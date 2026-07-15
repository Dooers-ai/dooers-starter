# Observability (OpenTelemetry)

From `dooers-agents-server` **≥ 0.16**, turn traces export automatically to the Dooers observability service when the `[observability]` extra is installed.

This starter already depends on:

```toml
dooers-agents-server[dooers,observability]>=0.16.1
```

## What you get

- One root span per agent turn (`agent.id`, `thread.id`, `event.id`, `user.id`, `org.id`, `workspace.id`, `agent.channel`)
- Auto-instrumented LLM children (Anthropic / OpenAI / OpenAI Agents) when `openinference` is present
- Org dashboard in Dooers Studio (Settings → Observability) via Core BFF — **no GCP keys in the agent**

## Setup

1. Install extras (already in this starter): `uv sync`
2. Deploy / hire the agent so seed injects the runtime API key (`dooers_runtime_api_key` in service secrets)
3. Chat → traces appear at the platform defaults (`https://observability.dooers.ai`)

No URL config is required for production. Optional local/staging overrides:

| Env | Purpose |
|-----|---------|
| `AGENT_CORE_BASE_URL` | Core API used to mint short-lived `otel:write` tokens |
| `AGENT_OTEL_SERVICE_URL` | OTLP/HTTP base (SDK appends `/v1/traces`) |
| `OTEL_SERVICE_NAME` | Service name on spans (default `dooers-agent`) |

These map into `AgentConfig` in `src/modules/agent/agent_config.py` (same pattern as analytics).

## Local notes

- Traces need a seeded runtime API key. A bare local `poe dev` without platform seed will not mint tokens.
- To exercise end-to-end locally: run Core + otel (or point overrides at staging) and connect the agent via ngrok Messages URL, or rely on hosted deploy after `dooers push`.

## Not the same as chat charts

- **OTel / Observability tab** — platform metrics (turns, tokens, cost estimates)
- **`send.chart`** — BI visualizations inside a conversation — see [09-charts.md](09-charts.md)
