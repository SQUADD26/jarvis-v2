-- ============================================================
-- RAG v2 Migration: Sources + Chunks + OpenAI 3072 + Full-Text
-- Uses HALFVEC for HNSW compatibility (up to 4000 dim)
-- ============================================================

-- Drop existing tables if they exist (clean slate)
DROP TABLE IF EXISTS rag_chunks CASCADE;
DROP TABLE IF EXISTS rag_sources CASCADE;

-- Drop existing functions
DROP FUNCTION IF EXISTS match_rag_chunks CASCADE;
DROP FUNCTION IF EXISTS search_rag_chunks_fulltext CASCADE;
DROP FUNCTION IF EXISTS search_rag_hybrid CASCADE;
DROP FUNCTION IF EXISTS delete_rag_source CASCADE;
DROP FUNCTION IF EXISTS update_source_chunks_count CASCADE;

-- 1. Create rag_sources table (parent)
CREATE TABLE IF NOT EXISTS rag_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,

    -- Source identification
    title TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('url', 'pdf', 'text', 'file', 'api')),
    source_url TEXT,
    file_name TEXT,
    file_hash TEXT,

    -- Metadata
    domain TEXT,
    content_length INT,
    chunks_count INT DEFAULT 0,
    metadata JSONB DEFAULT '{}',

    -- Status
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'processing', 'failed', 'archived')),
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rag_sources_user_id ON rag_sources(user_id);
CREATE INDEX IF NOT EXISTS idx_rag_sources_source_type ON rag_sources(source_type);
CREATE INDEX IF NOT EXISTS idx_rag_sources_file_hash ON rag_sources(file_hash);
CREATE INDEX IF NOT EXISTS idx_rag_sources_domain ON rag_sources(domain);

-- 2. Create rag_chunks table (children) with OpenAI 3072 dim using HALFVEC
CREATE TABLE IF NOT EXISTS rag_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES rag_sources(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,

    -- Content
    content TEXT NOT NULL,
    chunk_index INT NOT NULL DEFAULT 0,

    -- Embedding (OpenAI text-embedding-3-large = 3072 dim, HALFVEC for HNSW support)
    embedding HALFVEC(3072),

    -- Full-text search
    content_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('italian', content)) STORED,

    -- Metadata
    start_char INT,
    end_char INT,
    metadata JSONB DEFAULT '{}',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for rag_chunks
CREATE INDEX IF NOT EXISTS idx_rag_chunks_source_id ON rag_chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_user_id ON rag_chunks(user_id);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding ON rag_chunks USING hnsw (embedding halfvec_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_tsv ON rag_chunks USING GIN (content_tsv);

-- 3. RLS Policies
ALTER TABLE rag_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE rag_chunks ENABLE ROW LEVEL SECURITY;

-- rag_sources policies
CREATE POLICY "Service role full access on rag_sources"
    ON rag_sources FOR ALL TO service_role USING (true);

CREATE POLICY "Users can access their own sources"
    ON rag_sources FOR ALL
    USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

-- rag_chunks policies
CREATE POLICY "Service role full access on rag_chunks"
    ON rag_chunks FOR ALL TO service_role USING (true);

CREATE POLICY "Users can access their own chunks"
    ON rag_chunks FOR ALL
    USING (user_id = current_setting('request.jwt.claims', true)::json->>'sub');

-- 4. Semantic search function (3072 dim with HALFVEC)
CREATE OR REPLACE FUNCTION match_rag_chunks(
    query_embedding HALFVEC(3072),
    match_user_id TEXT,
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    source_id UUID,
    content TEXT,
    chunk_index INT,
    metadata JSONB,
    title TEXT,
    source_type TEXT,
    source_url TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.source_id,
        c.content,
        c.chunk_index,
        c.metadata,
        s.title,
        s.source_type,
        s.source_url,
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM rag_chunks c
    JOIN rag_sources s ON c.source_id = s.id
    WHERE c.user_id = match_user_id
      AND s.status = 'active'
      AND 1 - (c.embedding <=> query_embedding) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;

-- 5. Full-text search function
CREATE OR REPLACE FUNCTION search_rag_chunks_fulltext(
    search_query TEXT,
    match_user_id TEXT,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    source_id UUID,
    content TEXT,
    chunk_index INT,
    metadata JSONB,
    title TEXT,
    source_type TEXT,
    source_url TEXT,
    rank FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.source_id,
        c.content,
        c.chunk_index,
        c.metadata,
        s.title,
        s.source_type,
        s.source_url,
        ts_rank(c.content_tsv, plainto_tsquery('italian', search_query)) AS rank
    FROM rag_chunks c
    JOIN rag_sources s ON c.source_id = s.id
    WHERE c.user_id = match_user_id
      AND s.status = 'active'
      AND c.content_tsv @@ plainto_tsquery('italian', search_query)
    ORDER BY rank DESC
    LIMIT match_count;
END;
$$;

-- 6. Hybrid search function (combines semantic + full-text)
CREATE OR REPLACE FUNCTION search_rag_hybrid(
    query_embedding HALFVEC(3072),
    search_query TEXT,
    match_user_id TEXT,
    semantic_weight FLOAT DEFAULT 0.7,
    fulltext_weight FLOAT DEFAULT 0.3,
    match_threshold FLOAT DEFAULT 0.3,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    source_id UUID,
    content TEXT,
    chunk_index INT,
    metadata JSONB,
    title TEXT,
    source_type TEXT,
    source_url TEXT,
    semantic_score FLOAT,
    fulltext_score FLOAT,
    combined_score FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH semantic AS (
        SELECT
            c.id,
            1 - (c.embedding <=> query_embedding) AS score
        FROM rag_chunks c
        JOIN rag_sources s ON c.source_id = s.id
        WHERE c.user_id = match_user_id
          AND s.status = 'active'
          AND 1 - (c.embedding <=> query_embedding) > match_threshold
    ),
    fulltext AS (
        SELECT
            c.id,
            ts_rank(c.content_tsv, plainto_tsquery('italian', search_query)) AS score
        FROM rag_chunks c
        JOIN rag_sources s ON c.source_id = s.id
        WHERE c.user_id = match_user_id
          AND s.status = 'active'
          AND c.content_tsv @@ plainto_tsquery('italian', search_query)
    ),
    combined AS (
        SELECT
            COALESCE(sem.id, ft.id) AS chunk_id,
            COALESCE(sem.score, 0) AS sem_score,
            COALESCE(ft.score, 0) AS ft_score,
            (COALESCE(sem.score, 0) * semantic_weight + COALESCE(ft.score, 0) * fulltext_weight) AS total_score
        FROM semantic sem
        FULL OUTER JOIN fulltext ft ON sem.id = ft.id
    )
    SELECT
        c.id,
        c.source_id,
        c.content,
        c.chunk_index,
        c.metadata,
        s.title,
        s.source_type,
        s.source_url,
        comb.sem_score,
        comb.ft_score,
        comb.total_score
    FROM combined comb
    JOIN rag_chunks c ON comb.chunk_id = c.id
    JOIN rag_sources s ON c.source_id = s.id
    ORDER BY comb.total_score DESC
    LIMIT match_count;
END;
$$;

-- 7. Update chunks_count trigger
CREATE OR REPLACE FUNCTION update_source_chunks_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE rag_sources
        SET chunks_count = chunks_count + 1,
            updated_at = NOW()
        WHERE id = NEW.source_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE rag_sources
        SET chunks_count = chunks_count - 1,
            updated_at = NOW()
        WHERE id = OLD.source_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_chunks_count ON rag_chunks;
CREATE TRIGGER trigger_update_chunks_count
    AFTER INSERT OR DELETE ON rag_chunks
    FOR EACH ROW EXECUTE FUNCTION update_source_chunks_count();

-- 8. Helper function to delete source and all chunks
CREATE OR REPLACE FUNCTION delete_rag_source(p_source_id UUID, p_user_id TEXT)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM rag_sources
    WHERE id = p_source_id AND user_id = p_user_id;
    RETURN FOUND;
END;
$$;
