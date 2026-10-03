# AGENTS.md

Instructions for AI coding agents working in this repository.

## Primary skill

**Read [skills.md](skills.md) first** — canonical workflow for building Dooers agents on this starter
(gateway LLM, managed RAG, Skills, tools, multimodal input, deploy).

## Project

Official **Dooers agent starter kit** — FastAPI + `dooers-agents-server[dooers,observability]>=0.23`.
LLM through the **Dooers Gateway** (OpenAI-compatible), knowledge through the **managed Dooers RAG**,
one agent with a stable tool catalog and **Skills** loaded on demand.

## Read before coding

1. [docs/01-anatomy.md](docs/01-anatomy.md) — layers and the turn flow
2. [docs/03-capabilities.md](docs/03-capabilities.md) — Skills vs tools, how to add each
3. [docs/02-sdk-contract.md](docs/02-sdk-contract.md) — handler API
4. [docs/04-rag.md](docs/04-rag.md) / [docs/05-uploads.md](docs/05-uploads.md) when touching knowledge or attachments

## Commands

```bash
uv sync --extra dev
uv run poe check    # ruff on src + tests — required before suggesting push
uv run poe test     # pytest invariants (tool catalog, skills parser, prompt stability, schema)
uv run poe dev      # local server :8000
dooers validate && dooers push
```

## Extension pattern

- Procedure / policy the model should follow → a Skill (`skills/<id>.md` or Studio upload). No code.
- New action (API, DB, side effect) → `ToolSpec` in `core/tool_catalog.py` + implementation in `core/tools.py` + `ALL_TOOLS`.
- Do **not** add agents/handoffs for business domains. Do **not** put volatile data (date, user, documents) in `policies.py`.
- Studio fields → `schemas.py`; env → `config.py` (+ `.env.example`, `env.prod.example`).

When integrations need accounts/keys: **ask** the user (env vs settings vs chat form, auth format) before wiring secrets.
Never commit `.env`, `env.prod`, service-account JSON. Do not modify published SDK packages.
