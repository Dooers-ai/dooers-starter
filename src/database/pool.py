"""Async Postgres pool for app RAG tables (alongside dooers-agents-server DB)."""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import quote_plus

import asyncpg

from src.config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


def _dsn() -> str:
    user = quote_plus(settings.agent_database_user)
    password = quote_plus(settings.agent_database_password)
    return (
        f"postgresql://{user}:{password}"
        f"@{settings.agent_database_host}:{settings.agent_database_port}/{settings.agent_database_name}"
    )


async def init_pool() -> asyncpg.Pool | None:
    global _pool
    if not settings.app_postgres_pool_enabled:
        logger.info("APP_POSTGRES_POOL_ENABLED=false — skipping app RAG Postgres pool")
        return None
    db_type = (settings.agent_database_type or "").strip().lower()
    if db_type == "dooers":
        logger.warning(
            "AGENT_DATABASE_TYPE=dooers — app RAG Postgres pool skipped "
            "(password DSN incompatible with IAM AlloyDB; set APP_POSTGRES_POOL_ENABLED=false "
            "in env.prod to silence this warning)"
        )
        return None
    if _pool is not None:
        return _pool
    ssl = settings.agent_database_ssl
    ssl_arg: bool | str = False
    if ssl is True or (isinstance(ssl, str) and ssl.lower() in ("true", "require")):
        ssl_arg = True
    _pool = await asyncpg.create_pool(_dsn(), min_size=1, max_size=10, ssl=ssl_arg)
    await ensure_rag_schema()
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_pool() in lifespan")
    return _pool


async def ensure_rag_schema() -> None:
    if _pool is None:
        return
    mig_dir = Path(__file__).resolve().parent.parent.parent / "migrations"
    if not mig_dir.is_dir():
        logger.warning("RAG migrations directory not found: %s", mig_dir)
        return
    for sql_path in sorted(mig_dir.glob("*.sql")):
        sql = sql_path.read_text(encoding="utf-8")
        async with _pool.acquire() as conn:
            await conn.execute(sql)
        logger.info("RAG migration applied: %s", sql_path.name)
