-- Fix: Cambia embedding a halfvec(3072) per OpenAI text-embedding-3-large
-- halfvec usa float16, supporta fino a 4000 dim con HNSW
-- Version: 1.0.1
-- Applied: 2025-01-26

-- 1. Drop indice esistente
DROP INDEX IF EXISTS idx_kg_entities_embedding;

-- 2. Cambia tipo colonna a halfvec(3072)
ALTER TABLE kg_entities
ALTER COLUMN embedding TYPE halfvec(3072);

-- 3. Ricrea indice HNSW con halfvec
CREATE INDEX idx_kg_entities_embedding ON kg_entities
    USING hnsw (embedding halfvec_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 4. Aggiorna funzione RPC match_kg_entities per halfvec
CREATE OR REPLACE FUNCTION match_kg_entities(
    query_embedding halfvec(3072),
    match_user_id TEXT,
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5,
    filter_entity_type entity_type DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    canonical_name TEXT,
    entity_type entity_type,
    properties JSONB,
    confidence FLOAT,
    mention_count INT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.canonical_name,
        e.entity_type,
        e.properties,
        e.confidence,
        e.mention_count,
        1 - (e.embedding <=> query_embedding) AS similarity
    FROM kg_entities e
    WHERE e.user_id = match_user_id
      AND e.embedding IS NOT NULL
      AND (filter_entity_type IS NULL OR e.entity_type = filter_entity_type)
      AND 1 - (e.embedding <=> query_embedding) > match_threshold
    ORDER BY e.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
