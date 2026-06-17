-- Application RAG metadata (separate from dooers-agents-server tables).
CREATE TABLE IF NOT EXISTS agent_rag_vector_store (
    agent_id TEXT PRIMARY KEY,
    vector_store_id TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_knowledge_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('settings', 'chat')),
    field_id TEXT,
    thread_id TEXT,
    filename TEXT NOT NULL,
    gcs_uri TEXT,
    openai_file_id TEXT NOT NULL,
    vector_store_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_knowledge_files_agent ON agent_knowledge_files (agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_knowledge_files_thread ON agent_knowledge_files (thread_id);
