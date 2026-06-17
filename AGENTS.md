# AGENTS.md

Instructions for AI coding agents working in this repository.

## Primary skill

**Read [skills.md](skills.md) first** — canonical workflow for building Dooers-connected agents and integrations.

If the user links `skills.md` from GitHub or asks for a Dooers agent, follow that file end-to-end.

## Project

Official **Dooers agent starter kit** — FastAPI service using `dooers-agents-server` SDK.

## Read before coding

1. [docs/01-anatomy.md](docs/01-anatomy.md) — architecture
2. [docs/02-sdk-contract.md](docs/02-sdk-contract.md) — handler API
3. [.cursor/rules/dooers-agent.mdc](.cursor/rules/dooers-agent.mdc) — constraints

## Commands

```bash
uv sync --extra dev
uv run poe dev      # local server :8005
uv run poe check    # lint
dooers validate     # optional pre-push check
dooers push         # deploy (creator runs after dooers login)
```

Deploy guide: [docs/08-deploy.md](docs/08-deploy.md)  
Deploy recipe (AI prompt): [docs/recipes/deploy-with-dooers-push.md](docs/recipes/deploy-with-dooers-push.md)

## Extension pattern

New business domain → new file in `src/modules/agent/capabilities/` + handoff in `workflow.py`.

Do not modify SDK packages or platform internals.
