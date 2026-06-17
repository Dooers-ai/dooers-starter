"""Persistence for RAG vector store ids and knowledge file rows."""

from __future__ import annotations

from src.database import get_pool


class KnowledgeRepository:
    @staticmethod
    def _scope_agent_id(agent_id: str, field_id: str | None) -> str:
        if not field_id:
            return agent_id
        return f"{agent_id}__{field_id}"

    async def get_backend_store_id(self, agent_id: str, field_id: str | None = None) -> str | None:
        """Backend-native store identifier for the configured RAG provider."""
        return await self.get_vector_store_id(agent_id, field_id=field_id)

    async def get_vector_store_id(self, agent_id: str, field_id: str | None = None) -> str | None:
        """Resolve backend store id for a specific `(agent, field)` scope."""
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT NULLIF(
                    TRIM(
                        COALESCE(
                            (SELECT r.vector_store_id
                             FROM agent_rag_vector_store r
                             WHERE r.agent_id = $1
                             LIMIT 1),
                            (SELECT COALESCE(
                                NULLIF(trim(s.values->$3->0->>'vector_store_id'), ''),
                                NULLIF(trim(s.values->'base_de_conhecimento'->0->>'vector_store_id'), '')
                             )
                             FROM agent_settings s
                             WHERE s.agent_id = $2
                               AND (
                                 CASE
                                   WHEN NOT (s.values ? $3) THEN FALSE
                                   WHEN jsonb_typeof(s.values->$3) <> 'array' THEN FALSE
                                   ELSE jsonb_array_length(s.values->$3) > 0
                                 END
                                 OR
                                 CASE
                                   WHEN NOT (s.values ? 'base_de_conhecimento') THEN FALSE
                                   WHEN jsonb_typeof(s.values->'base_de_conhecimento') <> 'array' THEN FALSE
                                   ELSE jsonb_array_length(s.values->'base_de_conhecimento') > 0
                                 END
                               )
                             LIMIT 1
                            )
                        )
                    ),
                    ''
                ) AS vector_store_id
                """,
                self._scope_agent_id(agent_id, field_id),
                agent_id,
                field_id or "base_de_conhecimento",
            )
        if not row or row["vector_store_id"] is None:
            return None
        return str(row["vector_store_id"])

    async def upsert_vector_store(self, agent_id: str, vector_store_id: str, *, field_id: str | None = None) -> None:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_rag_vector_store (agent_id, vector_store_id, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (agent_id) DO UPDATE SET vector_store_id = EXCLUDED.vector_store_id, updated_at = NOW()
                """,
                self._scope_agent_id(agent_id, field_id),
                vector_store_id,
            )

    async def insert_knowledge_file(
        self,
        *,
        agent_id: str,
        source: str,
        field_id: str | None,
        thread_id: str | None,
        filename: str,
        gcs_uri: str | None,
        openai_file_id: str,
        vector_store_id: str,
    ) -> None:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_knowledge_files
                (agent_id, source, field_id, thread_id, filename, gcs_uri, openai_file_id, vector_store_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                agent_id,
                source,
                field_id,
                thread_id,
                filename,
                gcs_uri,
                openai_file_id,
                vector_store_id,
            )

    async def insert_knowledge_asset(
        self,
        *,
        agent_id: str,
        source: str,
        field_id: str | None,
        thread_id: str | None,
        filename: str,
        gcs_uri: str | None,
        provider_file_id: str,
        backend_store_id: str,
    ) -> None:
        """Provider-agnostic alias (maps to current table columns)."""
        await self.insert_knowledge_file(
            agent_id=agent_id,
            source=source,
            field_id=field_id,
            thread_id=thread_id,
            filename=filename,
            gcs_uri=gcs_uri,
            openai_file_id=provider_file_id,
            vector_store_id=backend_store_id,
        )

    async def get_by_openai_file_id(self, agent_id: str, openai_file_id: str) -> dict | None:
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, gcs_uri, vector_store_id, filename
                FROM agent_knowledge_files
                WHERE agent_id = $1 AND openai_file_id = $2
                """,
                agent_id,
                openai_file_id,
            )
        if not row:
            return None
        return dict(row)

    async def get_by_provider_file_id(self, agent_id: str, provider_file_id: str) -> dict | None:
        """Provider-agnostic alias (maps to current table columns)."""
        return await self.get_by_openai_file_id(agent_id, provider_file_id)

    async def delete_by_openai_file_id(self, agent_id: str, openai_file_id: str) -> None:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM agent_knowledge_files WHERE agent_id = $1 AND openai_file_id = $2",
                agent_id,
                openai_file_id,
            )

    async def delete_by_provider_file_id(self, agent_id: str, provider_file_id: str) -> None:
        """Provider-agnostic alias (maps to current table columns)."""
        await self.delete_by_openai_file_id(agent_id, provider_file_id)


knowledge_repository = KnowledgeRepository()
