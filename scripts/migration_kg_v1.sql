-- Knowledge Graph Schema for Jarvis Executive Assistant
-- Version: 1.0
-- Created: 2025-01-26

-- Enable required extensions (if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Entity Types enum (for type safety)
CREATE TYPE entity_type AS ENUM ('person', 'organization', 'project', 'location', 'event');

-- Relationship Types enum
CREATE TYPE relationship_type AS ENUM (
    -- Person-Person
    'reports_to',        -- A reports to B (manager relationship)
    'collaborates_with', -- A works with B (peer relationship)
    'knows',             -- A knows B (personal connection)
    'is_family_of',      -- A is family member of B

    -- Person-Organization
    'works_for',         -- A works for B
    'is_client_of',      -- A is client of B
    'is_partner_of',     -- A partners with B
    'owns',              -- A owns B

    -- Person-Project
    'leads',             -- A leads project B
    'works_on',          -- A works on project B
    'created',           -- A created project B

    -- Any-Location
    'located_in',        -- A is located in B
    'lives_in',          -- A lives in B

    -- Person-Event
    'attended',          -- A attended event B
    'organized',         -- A organized event B

    -- Organization-Organization
    'subsidiary_of',     -- A is subsidiary of B
    'competes_with',     -- A competes with B

    -- Generic
    'related_to'         -- Generic fallback relationship
);

-- Main entities table
CREATE TABLE IF NOT EXISTS kg_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,

    -- Core fields
    canonical_name TEXT NOT NULL,
    entity_type entity_type NOT NULL,

    -- Flexible properties (role, email, phone, industry, etc.)
    properties JSONB DEFAULT '{}',

    -- Vector embedding for semantic search (3072-dim for OpenAI text-embedding-3-large)
    embedding HALFVEC(3072),

    -- Metadata
    confidence FLOAT DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    mention_count INT DEFAULT 1,
    first_mentioned_at TIMESTAMPTZ DEFAULT now(),
    last_mentioned_at TIMESTAMPTZ DEFAULT now(),

    -- Source tracking
    source_type TEXT DEFAULT 'conversation', -- conversation, calendar, email
    source_id TEXT,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Unique constraint per user: one canonical entity per name+type
    UNIQUE(user_id, canonical_name, entity_type)
);

-- Entity aliases for resolution ("Marco" -> "Marco Rossi")
CREATE TABLE IF NOT EXISTS kg_entity_aliases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
    alias TEXT NOT NULL,

    -- How reliable is this alias mapping?
    confidence FLOAT DEFAULT 0.8 CHECK (confidence >= 0 AND confidence <= 1),

    created_at TIMESTAMPTZ DEFAULT now(),

    -- Unique alias per entity
    UNIQUE(entity_id, alias)
);

-- Relationships between entities
CREATE TABLE IF NOT EXISTS kg_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,

    -- Directional relationship: source --[relationship]--> target
    source_entity_id UUID NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES kg_entities(id) ON DELETE CASCADE,
    relationship_type relationship_type NOT NULL,

    -- Optional properties for the relationship
    properties JSONB DEFAULT '{}',

    -- Temporal aspects
    is_current BOOLEAN DEFAULT true,
    started_at DATE,
    ended_at DATE,

    -- Confidence and provenance
    confidence FLOAT DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    source_type TEXT DEFAULT 'conversation',
    source_id TEXT,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Prevent duplicate relationships
    UNIQUE(user_id, source_entity_id, target_entity_id, relationship_type)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Entity indexes
CREATE INDEX IF NOT EXISTS idx_kg_entities_user ON kg_entities(user_id);
CREATE INDEX IF NOT EXISTS idx_kg_entities_type ON kg_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_kg_entities_name ON kg_entities(canonical_name);
CREATE INDEX IF NOT EXISTS idx_kg_entities_name_lower ON kg_entities(lower(canonical_name));
CREATE INDEX IF NOT EXISTS idx_kg_entities_updated ON kg_entities(last_mentioned_at DESC);

-- Vector index for semantic search (HNSW for fast approximate nearest neighbor)
CREATE INDEX IF NOT EXISTS idx_kg_entities_embedding ON kg_entities
    USING hnsw (embedding halfvec_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Alias indexes
CREATE INDEX IF NOT EXISTS idx_kg_aliases_entity ON kg_entity_aliases(entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_aliases_alias ON kg_entity_aliases(lower(alias));

-- Relationship indexes
CREATE INDEX IF NOT EXISTS idx_kg_rel_user ON kg_relationships(user_id);
CREATE INDEX IF NOT EXISTS idx_kg_rel_source ON kg_relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_rel_target ON kg_relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_rel_type ON kg_relationships(relationship_type);
CREATE INDEX IF NOT EXISTS idx_kg_rel_current ON kg_relationships(is_current) WHERE is_current = true;

-- ============================================================================
-- RPC FUNCTIONS
-- ============================================================================

-- Vector similarity search for entities
CREATE OR REPLACE FUNCTION match_kg_entities(
    query_embedding HALFVEC(3072),
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

-- Get entity with all its relationships (1-hop graph traversal)
CREATE OR REPLACE FUNCTION get_entity_relationships(
    p_entity_id UUID,
    p_include_inactive BOOLEAN DEFAULT false
)
RETURNS TABLE (
    entity_id UUID,
    entity_name TEXT,
    entity_type entity_type,
    entity_properties JSONB,
    direction TEXT,
    rel_type relationship_type,
    rel_properties JSONB,
    related_entity_id UUID,
    related_entity_name TEXT,
    related_entity_type entity_type,
    related_entity_properties JSONB,
    is_current BOOLEAN
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    -- Outgoing relationships (this entity is source)
    SELECT
        e.id AS entity_id,
        e.canonical_name AS entity_name,
        e.entity_type,
        e.properties AS entity_properties,
        'outgoing'::TEXT AS direction,
        r.relationship_type AS rel_type,
        r.properties AS rel_properties,
        t.id AS related_entity_id,
        t.canonical_name AS related_entity_name,
        t.entity_type AS related_entity_type,
        t.properties AS related_entity_properties,
        r.is_current
    FROM kg_entities e
    JOIN kg_relationships r ON e.id = r.source_entity_id
    JOIN kg_entities t ON r.target_entity_id = t.id
    WHERE e.id = p_entity_id
      AND (p_include_inactive OR r.is_current = true)

    UNION ALL

    -- Incoming relationships (this entity is target)
    SELECT
        e.id AS entity_id,
        e.canonical_name AS entity_name,
        e.entity_type,
        e.properties AS entity_properties,
        'incoming'::TEXT AS direction,
        r.relationship_type AS rel_type,
        r.properties AS rel_properties,
        s.id AS related_entity_id,
        s.canonical_name AS related_entity_name,
        s.entity_type AS related_entity_type,
        s.properties AS related_entity_properties,
        r.is_current
    FROM kg_entities e
    JOIN kg_relationships r ON e.id = r.target_entity_id
    JOIN kg_entities s ON r.source_entity_id = s.id
    WHERE e.id = p_entity_id
      AND (p_include_inactive OR r.is_current = true);
END;
$$;

-- Find colleagues (people who work for the same organization as someone)
CREATE OR REPLACE FUNCTION find_colleagues(
    p_user_id TEXT,
    p_person_entity_id UUID
)
RETURNS TABLE (
    colleague_id UUID,
    colleague_name TEXT,
    colleague_properties JSONB,
    shared_org_id UUID,
    shared_org_name TEXT,
    relationship_to_org relationship_type
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH person_orgs AS (
        -- Organizations the person works for
        SELECT
            r.target_entity_id AS org_id,
            o.canonical_name AS org_name
        FROM kg_relationships r
        JOIN kg_entities o ON r.target_entity_id = o.id
        WHERE r.user_id = p_user_id
          AND r.source_entity_id = p_person_entity_id
          AND r.relationship_type = 'works_for'
          AND r.is_current = true
          AND o.entity_type = 'organization'
    )
    SELECT DISTINCT
        p.id AS colleague_id,
        p.canonical_name AS colleague_name,
        p.properties AS colleague_properties,
        po.org_id AS shared_org_id,
        po.org_name AS shared_org_name,
        r.relationship_type AS relationship_to_org
    FROM person_orgs po
    JOIN kg_relationships r ON r.target_entity_id = po.org_id
    JOIN kg_entities p ON r.source_entity_id = p.id
    WHERE r.user_id = p_user_id
      AND r.relationship_type = 'works_for'
      AND r.is_current = true
      AND p.entity_type = 'person'
      AND p.id != p_person_entity_id;
END;
$$;

-- Search entities by name or alias (exact and fuzzy)
CREATE OR REPLACE FUNCTION search_kg_entities(
    p_user_id TEXT,
    p_query TEXT,
    p_entity_type entity_type DEFAULT NULL,
    p_limit INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    canonical_name TEXT,
    entity_type entity_type,
    properties JSONB,
    confidence FLOAT,
    match_type TEXT,
    matched_alias TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    query_lower TEXT := lower(p_query);
BEGIN
    RETURN QUERY
    -- Exact match on canonical name
    SELECT
        e.id,
        e.canonical_name,
        e.entity_type,
        e.properties,
        e.confidence,
        'exact_name'::TEXT AS match_type,
        e.canonical_name AS matched_alias
    FROM kg_entities e
    WHERE e.user_id = p_user_id
      AND lower(e.canonical_name) = query_lower
      AND (p_entity_type IS NULL OR e.entity_type = p_entity_type)

    UNION ALL

    -- Exact match on alias
    SELECT
        e.id,
        e.canonical_name,
        e.entity_type,
        e.properties,
        e.confidence,
        'exact_alias'::TEXT AS match_type,
        a.alias AS matched_alias
    FROM kg_entities e
    JOIN kg_entity_aliases a ON e.id = a.entity_id
    WHERE e.user_id = p_user_id
      AND lower(a.alias) = query_lower
      AND (p_entity_type IS NULL OR e.entity_type = p_entity_type)

    UNION ALL

    -- Partial match on canonical name (contains)
    SELECT
        e.id,
        e.canonical_name,
        e.entity_type,
        e.properties,
        e.confidence * 0.8,  -- Lower confidence for partial matches
        'partial_name'::TEXT AS match_type,
        e.canonical_name AS matched_alias
    FROM kg_entities e
    WHERE e.user_id = p_user_id
      AND lower(e.canonical_name) LIKE '%' || query_lower || '%'
      AND lower(e.canonical_name) != query_lower  -- Exclude exact matches
      AND (p_entity_type IS NULL OR e.entity_type = p_entity_type)

    UNION ALL

    -- Partial match on alias (contains)
    SELECT
        e.id,
        e.canonical_name,
        e.entity_type,
        e.properties,
        e.confidence * 0.8,
        'partial_alias'::TEXT AS match_type,
        a.alias AS matched_alias
    FROM kg_entities e
    JOIN kg_entity_aliases a ON e.id = a.entity_id
    WHERE e.user_id = p_user_id
      AND lower(a.alias) LIKE '%' || query_lower || '%'
      AND lower(a.alias) != query_lower
      AND (p_entity_type IS NULL OR e.entity_type = p_entity_type)

    ORDER BY
        CASE match_type
            WHEN 'exact_name' THEN 1
            WHEN 'exact_alias' THEN 2
            WHEN 'partial_name' THEN 3
            WHEN 'partial_alias' THEN 4
        END,
        confidence DESC
    LIMIT p_limit;
END;
$$;

-- Update entity mention stats
CREATE OR REPLACE FUNCTION update_entity_mention(
    p_entity_id UUID
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE kg_entities
    SET
        mention_count = mention_count + 1,
        last_mentioned_at = now(),
        updated_at = now()
    WHERE id = p_entity_id;
END;
$$;

-- Get entities with relationships for context injection
CREATE OR REPLACE FUNCTION get_entities_with_context(
    p_user_id TEXT,
    p_entity_ids UUID[],
    p_max_relationships INT DEFAULT 3
)
RETURNS TABLE (
    entity_id UUID,
    canonical_name TEXT,
    entity_type entity_type,
    properties JSONB,
    relationships JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id AS entity_id,
        e.canonical_name,
        e.entity_type,
        e.properties,
        COALESCE(
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'direction', rel.direction,
                        'type', rel.rel_type,
                        'related_name', rel.related_entity_name,
                        'related_type', rel.related_entity_type
                    )
                )
                FROM (
                    SELECT * FROM get_entity_relationships(e.id, false)
                    LIMIT p_max_relationships
                ) rel
            ),
            '[]'::JSONB
        ) AS relationships
    FROM kg_entities e
    WHERE e.id = ANY(p_entity_ids)
      AND e.user_id = p_user_id;
END;
$$;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_kg_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_kg_entities_updated
    BEFORE UPDATE ON kg_entities
    FOR EACH ROW
    EXECUTE FUNCTION update_kg_timestamp();

CREATE TRIGGER trigger_kg_relationships_updated
    BEFORE UPDATE ON kg_relationships
    FOR EACH ROW
    EXECUTE FUNCTION update_kg_timestamp();

-- ============================================================================
-- GRANTS (adjust based on your Supabase setup)
-- ============================================================================

-- Enable RLS
ALTER TABLE kg_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE kg_entity_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE kg_relationships ENABLE ROW LEVEL SECURITY;

-- RLS Policies for kg_entities
CREATE POLICY "Users can view their own entities" ON kg_entities
    FOR SELECT USING (auth.uid()::TEXT = user_id OR user_id = 'default');

CREATE POLICY "Users can insert their own entities" ON kg_entities
    FOR INSERT WITH CHECK (auth.uid()::TEXT = user_id OR user_id = 'default');

CREATE POLICY "Users can update their own entities" ON kg_entities
    FOR UPDATE USING (auth.uid()::TEXT = user_id OR user_id = 'default');

CREATE POLICY "Users can delete their own entities" ON kg_entities
    FOR DELETE USING (auth.uid()::TEXT = user_id OR user_id = 'default');

-- RLS Policies for kg_entity_aliases (linked to entities)
CREATE POLICY "Users can view aliases for their entities" ON kg_entity_aliases
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM kg_entities e
            WHERE e.id = entity_id
            AND (e.user_id = auth.uid()::TEXT OR e.user_id = 'default')
        )
    );

CREATE POLICY "Users can insert aliases for their entities" ON kg_entity_aliases
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM kg_entities e
            WHERE e.id = entity_id
            AND (e.user_id = auth.uid()::TEXT OR e.user_id = 'default')
        )
    );

CREATE POLICY "Users can delete aliases for their entities" ON kg_entity_aliases
    FOR DELETE USING (
        EXISTS (
            SELECT 1 FROM kg_entities e
            WHERE e.id = entity_id
            AND (e.user_id = auth.uid()::TEXT OR e.user_id = 'default')
        )
    );

-- RLS Policies for kg_relationships
CREATE POLICY "Users can view their own relationships" ON kg_relationships
    FOR SELECT USING (auth.uid()::TEXT = user_id OR user_id = 'default');

CREATE POLICY "Users can insert their own relationships" ON kg_relationships
    FOR INSERT WITH CHECK (auth.uid()::TEXT = user_id OR user_id = 'default');

CREATE POLICY "Users can update their own relationships" ON kg_relationships
    FOR UPDATE USING (auth.uid()::TEXT = user_id OR user_id = 'default');

CREATE POLICY "Users can delete their own relationships" ON kg_relationships
    FOR DELETE USING (auth.uid()::TEXT = user_id OR user_id = 'default');

-- Service role bypass for server-side operations
CREATE POLICY "Service role full access entities" ON kg_entities
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "Service role full access aliases" ON kg_entity_aliases
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');

CREATE POLICY "Service role full access relationships" ON kg_relationships
    FOR ALL USING (auth.jwt() ->> 'role' = 'service_role');
