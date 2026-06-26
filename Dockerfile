FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations

RUN uv pip install --system .

# The hosting platform (Cloud Run behind the Dooers global load balancer)
# injects a PORT env var (default 8080) and probes it for readiness. The
# container MUST listen on $PORT — do NOT hardcode a port here. --proxy-headers
# is required because the agent sits behind the load balancer.
EXPOSE 8080

CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers"]
