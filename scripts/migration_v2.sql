-- Migration V2: Task Queue e ottimizzazioni
-- Eseguire in Supabase Dashboard -> SQL Editor

-- 1. Aggiungere tokens_used a chat_history
ALTER TABLE chat_history
    ADD COLUMN IF NOT EXISTS tokens_used INT;

-- 2. Upgrade indici da IVFFlat a HNSW (migliori performance)
-- NOTA: Richiede ricostruzione, può essere lento su tabelle grandi
DROP INDEX IF EXISTS idx_memory_facts_embedding;
DROP INDEX IF EXISTS idx_rag_documents_embedding;

CREATE INDEX idx_memory_facts_embedding
    ON memory_facts USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_rag_documents_embedding
    ON rag_documents USING hnsw (embedding vector_cosine_ops);

-- 3. Creare tabella task_queue (se non esiste)
CREATE TABLE IF NOT EXISTS task_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    scheduled_at TIMESTAMPTZ,
    priority INT DEFAULT 5,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'claimed', 'running', 'completed', 'failed', 'cancelled')),
    claimed_by TEXT,
    claimed_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result JSONB,
    error TEXT,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Indici per task_queue
CREATE INDEX IF NOT EXISTS idx_task_queue_pending ON task_queue(scheduled_at, priority)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_task_queue_user ON task_queue(user_id, status);
CREATE INDEX IF NOT EXISTS idx_task_queue_status ON task_queue(status);

-- 5. RLS per task_queue
ALTER TABLE task_queue ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'task_queue' AND policyname = 'Service role full access on task_queue'
    ) THEN
        CREATE POLICY "Service role full access on task_queue"
            ON task_queue FOR ALL
            TO service_role
            USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'task_queue' AND policyname = 'Users can view their own tasks'
    ) THEN
        CREATE POLICY "Users can view their own tasks"
            ON task_queue FOR SELECT
            USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');
    END IF;
END $$;

-- 6. Funzioni RPC
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

-- Verifica
SELECT 'Migration V2 completata!' as status;
