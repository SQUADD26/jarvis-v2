"""
Eseguire questo SQL in Supabase Dashboard -> SQL Editor
"""

SCHEMA_SQL = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Chat History
CREATE TABLE IF NOT EXISTS chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    tokens_used INT,  -- Track token usage per message
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created_at ON chat_history(created_at DESC);

-- Memory Facts (fatti estratti dalle conversazioni)
CREATE TABLE IF NOT EXISTS memory_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    fact TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('preference', 'fact', 'episode', 'task')),
    embedding VECTOR(768),  -- Gemini embedding dimension
    importance FLOAT DEFAULT 0.5,
    source_message_id UUID REFERENCES chat_history(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memory_facts_user_id ON memory_facts(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_facts_embedding ON memory_facts USING hnsw (embedding vector_cosine_ops);

-- RAG Documents
CREATE TABLE IF NOT EXISTS rag_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    chunk_index INT DEFAULT 0,
    embedding VECTOR(768),
    metadata JSONB DEFAULT '{}',
    source_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_documents_user_id ON rag_documents(user_id);
CREATE INDEX IF NOT EXISTS idx_rag_documents_embedding ON rag_documents USING hnsw (embedding vector_cosine_ops);

-- User Preferences
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id TEXT PRIMARY KEY,
    timezone TEXT DEFAULT 'Europe/Rome',
    language TEXT DEFAULT 'it',
    notification_enabled BOOLEAN DEFAULT TRUE,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable Row Level Security (RLS) for all tables
ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_facts ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;

-- RLS Policies for chat_history
CREATE POLICY "Users can only access their own chat history"
    ON chat_history FOR ALL
    USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

CREATE POLICY "Service role can access all chat history"
    ON chat_history FOR ALL
    TO service_role
    USING (true);

-- RLS Policies for memory_facts
CREATE POLICY "Users can only access their own memory facts"
    ON memory_facts FOR ALL
    USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

CREATE POLICY "Service role can access all memory facts"
    ON memory_facts FOR ALL
    TO service_role
    USING (true);

-- RLS Policies for rag_documents
CREATE POLICY "Users can only access their own RAG documents"
    ON rag_documents FOR ALL
    USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

CREATE POLICY "Service role can access all RAG documents"
    ON rag_documents FOR ALL
    TO service_role
    USING (true);

-- RLS Policies for user_preferences
CREATE POLICY "Users can only access their own preferences"
    ON user_preferences FOR ALL
    USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

CREATE POLICY "Service role can access all user preferences"
    ON user_preferences FOR ALL
    TO service_role
    USING (true);

-- Function per similarity search
CREATE OR REPLACE FUNCTION match_memory_facts(
    query_embedding VECTOR(768),
    match_user_id TEXT,
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    fact TEXT,
    category TEXT,
    importance FLOAT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        mf.id,
        mf.fact,
        mf.category,
        mf.importance,
        1 - (mf.embedding <=> query_embedding) AS similarity
    FROM memory_facts mf
    WHERE mf.user_id = match_user_id
      AND 1 - (mf.embedding <=> query_embedding) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;

-- Function per RAG similarity search
CREATE OR REPLACE FUNCTION match_rag_documents(
    query_embedding VECTOR(768),
    match_user_id TEXT,
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    title TEXT,
    content TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        rd.id,
        rd.title,
        rd.content,
        1 - (rd.embedding <=> query_embedding) AS similarity
    FROM rag_documents rd
    WHERE rd.user_id = match_user_id
      AND 1 - (rd.embedding <=> query_embedding) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;

-- ============================================================
-- TASK QUEUE per proattività e parallelismo
-- ============================================================

CREATE TABLE IF NOT EXISTS task_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,

    -- Task definition
    task_type TEXT NOT NULL,  -- 'reminder', 'scheduled_check', 'long_running'
    payload JSONB NOT NULL DEFAULT '{}',

    -- Scheduling
    scheduled_at TIMESTAMPTZ,  -- NULL = immediate
    priority INT DEFAULT 5,    -- 1=highest, 10=lowest

    -- Execution state
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'claimed', 'running', 'completed', 'failed', 'cancelled')),
    claimed_by TEXT,
    claimed_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Results
    result JSONB,
    error TEXT,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indici per polling efficiente
CREATE INDEX IF NOT EXISTS idx_task_queue_pending ON task_queue(scheduled_at, priority)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_task_queue_user ON task_queue(user_id, status);
CREATE INDEX IF NOT EXISTS idx_task_queue_status ON task_queue(status);

-- RLS per task_queue
ALTER TABLE task_queue ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on task_queue"
    ON task_queue FOR ALL
    TO service_role
    USING (true);

CREATE POLICY "Users can view their own tasks"
    ON task_queue FOR SELECT
    USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

-- RPC per claim atomico (evita race condition)
CREATE OR REPLACE FUNCTION claim_next_task(p_worker_id TEXT)
RETURNS task_queue
LANGUAGE plpgsql
AS $$
DECLARE
    claimed_task task_queue;
BEGIN
    UPDATE task_queue
    SET status = 'claimed',
        claimed_by = p_worker_id,
        claimed_at = NOW(),
        updated_at = NOW()
    WHERE id = (
        SELECT id FROM task_queue
        WHERE status = 'pending'
          AND (scheduled_at IS NULL OR scheduled_at <= NOW())
        ORDER BY priority ASC, scheduled_at ASC NULLS FIRST
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING * INTO claimed_task;
    RETURN claimed_task;
END;
$$;

-- RPC per completare un task
CREATE OR REPLACE FUNCTION complete_task(
    p_task_id UUID,
    p_result JSONB DEFAULT NULL
)
RETURNS task_queue
LANGUAGE plpgsql
AS $$
DECLARE
    updated_task task_queue;
BEGIN
    UPDATE task_queue
    SET status = 'completed',
        result = p_result,
        completed_at = NOW(),
        updated_at = NOW()
    WHERE id = p_task_id
    RETURNING * INTO updated_task;
    RETURN updated_task;
END;
$$;

-- RPC per fallire un task
CREATE OR REPLACE FUNCTION fail_task(
    p_task_id UUID,
    p_error TEXT
)
RETURNS task_queue
LANGUAGE plpgsql
AS $$
DECLARE
    updated_task task_queue;
BEGIN
    UPDATE task_queue
    SET status = CASE
            WHEN retry_count < max_retries THEN 'pending'
            ELSE 'failed'
        END,
        error = p_error,
        retry_count = retry_count + 1,
        updated_at = NOW()
    WHERE id = p_task_id
    RETURNING * INTO updated_task;
    RETURN updated_task;
END;
$$;

-- RPC per cleanup task stale (bloccati)
CREATE OR REPLACE FUNCTION cleanup_stale_tasks(p_timeout_minutes INT DEFAULT 30)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
    affected_count INT;
BEGIN
    UPDATE task_queue
    SET status = 'pending',
        claimed_by = NULL,
        claimed_at = NULL,
        started_at = NULL,
        retry_count = retry_count + 1,
        updated_at = NOW()
    WHERE status IN ('claimed', 'running')
      AND updated_at < NOW() - (p_timeout_minutes || ' minutes')::INTERVAL;
    GET DIAGNOSTICS affected_count = ROW_COUNT;
    RETURN affected_count;
END;
$$;
"""

if __name__ == "__main__":
    print("Esegui questo SQL nel Supabase Dashboard -> SQL Editor:")
    print("=" * 60)
    print(SCHEMA_SQL)
