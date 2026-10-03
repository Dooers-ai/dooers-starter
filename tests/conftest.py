import os

# Deterministic environment for the test process: gateway on, RAG off, no DB connection.
os.environ.setdefault("DOOERS_GATEWAY_API_KEY", "dk_live_test")
os.environ.setdefault("DOOERS_RAG_SERVICE_URL", "")
os.environ.setdefault("AGENT_SEED_SECRET", "")
os.environ.setdefault("CONFIG_STRICT", "false")
