-- Fix search_rag_hybrid function return type mismatch
-- The HALFVEC operations return 'real' but function declared 'FLOAT' (double precision)
-- Fix: Cast computed values to DOUBLE PRECISION

DROP FUNCTION IF EXISTS search_rag_hybrid CASCADE;

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
    semantic_score DOUBLE PRECISION,
    fulltext_score DOUBLE PRECISION,
    combined_score DOUBLE PRECISION
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH semantic AS (
        SELECT
            c.id,
            (1 - (c.embedding <=> query_embedding))::DOUBLE PRECISION AS score
        FROM rag_chunks c
        JOIN rag_sources s ON c.source_id = s.id
        WHERE c.user_id = match_user_id
          AND s.status = 'active'
          AND 1 - (c.embedding <=> query_embedding) > match_threshold
    ),
    fulltext AS (
        SELECT
            c.id,
            ts_rank(c.content_tsv, plainto_tsquery('italian', search_query))::DOUBLE PRECISION AS score
        FROM rag_chunks c
        JOIN rag_sources s ON c.source_id = s.id
        WHERE c.user_id = match_user_id
          AND s.status = 'active'
          AND c.content_tsv @@ plainto_tsquery('italian', search_query)
    ),
    combined AS (
        SELECT
            COALESCE(sem.id, ft.id) AS chunk_id,
            COALESCE(sem.score, 0::DOUBLE PRECISION) AS sem_score,
            COALESCE(ft.score, 0::DOUBLE PRECISION) AS ft_score,
            (COALESCE(sem.score, 0::DOUBLE PRECISION) * semantic_weight + COALESCE(ft.score, 0::DOUBLE PRECISION) * fulltext_weight)::DOUBLE PRECISION AS total_score
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

-- Also fix match_rag_chunks function for consistency
DROP FUNCTION IF EXISTS match_rag_chunks CASCADE;

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
    similarity DOUBLE PRECISION
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
        (1 - (c.embedding <=> query_embedding))::DOUBLE PRECISION AS similarity
    FROM rag_chunks c
    JOIN rag_sources s ON c.source_id = s.id
    WHERE c.user_id = match_user_id
      AND s.status = 'active'
      AND 1 - (c.embedding <=> query_embedding) > match_threshold
    ORDER BY similarity DESC
    LIMIT match_count;
END;
$$;

-- Also fix search_rag_chunks_fulltext for consistency
DROP FUNCTION IF EXISTS search_rag_chunks_fulltext CASCADE;

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
    rank DOUBLE PRECISION
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
        ts_rank(c.content_tsv, plainto_tsquery('italian', search_query))::DOUBLE PRECISION AS rank
    FROM rag_chunks c
    JOIN rag_sources s ON c.source_id = s.id
    WHERE c.user_id = match_user_id
      AND s.status = 'active'
      AND c.content_tsv @@ plainto_tsquery('italian', search_query)
    ORDER BY rank DESC
    LIMIT match_count;
END;
$$;
