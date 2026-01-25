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
CREATE INDEX IF NOT EXISTS idx_memory_facts_embedding ON memory_facts USING ivfflat (embedding vector_cosine_ops);

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
CREATE INDEX IF NOT EXISTS idx_rag_documents_embedding ON rag_documents USING ivfflat (embedding vector_cosine_ops);

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
"""

if __name__ == "__main__":
    print("Esegui questo SQL nel Supabase Dashboard -> SQL Editor:")
    print("=" * 60)
    print(SCHEMA_SQL)
