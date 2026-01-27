"""
Test intensivi per il Knowledge Graph.

Verifica:
1. Estrazione entità corretta senza invenzioni
2. Validazione tipi entity/relationship
3. No allucinazioni LLM
4. Ingestion e persistenza
5. Entity resolution e deduplicazione
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock

from jarvis.core.kg_types import (
    EntityType,
    RelationshipType,
    ExtractedEntity,
    ExtractedRelationship,
    KGExtractionResult,
)
from jarvis.core.kg_extractor import (
    KGExtractor,
    normalize_entity_type,
    normalize_relationship_type,
    is_generic_reference,
    has_proper_name,
    ENTITY_TYPE_ALIASES,
    RELATIONSHIP_TYPE_ALIASES,
)
from jarvis.core.knowledge_graph import (
    KnowledgeGraphManager,
    VALID_ENTITY_TYPES,
    VALID_RELATIONSHIP_TYPES,
)


# =============================================================================
# TEST: Type Normalization
# =============================================================================

class TestTypeNormalization:
    """Test normalizzazione tipi entità e relazioni."""

    def test_valid_entity_types(self):
        """Tutti i tipi validi devono essere normalizzati correttamente."""
        for etype in ["person", "organization", "project", "location", "event"]:
            result = normalize_entity_type(etype)
            assert result is not None
            assert result.value == etype

    def test_entity_type_aliases_italian(self):
        """Alias italiani devono mappare correttamente."""
        assert normalize_entity_type("persona") == EntityType.person
        assert normalize_entity_type("azienda") == EntityType.organization
        assert normalize_entity_type("società") == EntityType.organization
        assert normalize_entity_type("progetto") == EntityType.project
        assert normalize_entity_type("luogo") == EntityType.location
        assert normalize_entity_type("evento") == EntityType.event

    def test_entity_type_aliases_english(self):
        """Alias inglesi varianti devono mappare correttamente."""
        assert normalize_entity_type("company") == EntityType.organization
        assert normalize_entity_type("firm") == EntityType.organization
        assert normalize_entity_type("corp") == EntityType.organization
        assert normalize_entity_type("individual") == EntityType.person
        assert normalize_entity_type("place") == EntityType.location
        assert normalize_entity_type("city") == EntityType.location

    def test_invalid_entity_type_returns_none(self):
        """Tipi invalidi devono ritornare None."""
        assert normalize_entity_type("invalid_type") is None
        assert normalize_entity_type("xyz123") is None
        assert normalize_entity_type("") is None
        assert normalize_entity_type(None) is None

    def test_valid_relationship_types(self):
        """Tutti i tipi relazione validi."""
        valid_types = [
            "reports_to", "collaborates_with", "knows", "is_family_of",
            "works_for", "is_client_of", "is_partner_of", "owns",
            "leads", "works_on", "created",
            "located_in", "lives_in",
            "attended", "organized",
            "subsidiary_of", "competes_with",
            "related_to"
        ]
        for rtype in valid_types:
            result = normalize_relationship_type(rtype)
            assert result is not None
            assert result.value == rtype

    def test_relationship_type_aliases(self):
        """Alias relazioni devono mappare correttamente."""
        assert normalize_relationship_type("lavora_per") == RelationshipType.works_for
        assert normalize_relationship_type("lavora_con") == RelationshipType.collaborates_with
        assert normalize_relationship_type("conosce") == RelationshipType.knows
        assert normalize_relationship_type("employed_by") == RelationshipType.works_for
        assert normalize_relationship_type("works_at") == RelationshipType.works_for

    def test_invalid_relationship_falls_back_to_related_to(self):
        """Tipi relazione invalidi devono fallback a related_to."""
        result = normalize_relationship_type("unknown_relation")
        assert result == RelationshipType.related_to


# =============================================================================
# TEST: Generic Reference Detection
# =============================================================================

class TestGenericReferenceDetection:
    """Test rilevamento riferimenti generici (da scartare)."""

    def test_pronouns_are_generic(self):
        """Pronomi italiani sono generici."""
        assert is_generic_reference("lui") is True
        assert is_generic_reference("lei") is True
        assert is_generic_reference("loro") is True

    def test_generic_italian_references(self):
        """Riferimenti generici italiani."""
        assert is_generic_reference("il tipo") is True
        assert is_generic_reference("la persona") is True
        assert is_generic_reference("un amico") is True
        assert is_generic_reference("quella persona") is True

    def test_english_generic_references(self):
        """Riferimenti generici inglesi."""
        assert is_generic_reference("he") is True
        assert is_generic_reference("she") is True
        assert is_generic_reference("someone") is True
        assert is_generic_reference("the person") is True

    def test_short_names_are_generic(self):
        """Nomi troppo corti sono generici."""
        assert is_generic_reference("a") is True
        assert is_generic_reference("io") is True

    def test_proper_names_are_not_generic(self):
        """Nomi propri NON sono generici."""
        assert is_generic_reference("Marco Rossi") is False
        assert is_generic_reference("Acme Corp") is False
        assert is_generic_reference("Progetto Phoenix") is False
        assert is_generic_reference("Milano") is False


# =============================================================================
# TEST: Proper Name Detection
# =============================================================================

class TestProperNameDetection:
    """Test rilevamento nomi propri."""

    def test_capitalized_names(self):
        """Nomi con maiuscole sono propri."""
        assert has_proper_name("Marco") is True
        assert has_proper_name("Marco Rossi") is True
        assert has_proper_name("ACME") is True
        assert has_proper_name("Google") is True

    def test_multi_word_names(self):
        """Nomi multi-parola sono propri."""
        assert has_proper_name("progetto alpha") is True  # Multi-word
        assert has_proper_name("acme corporation") is True

    def test_single_lowercase_not_proper(self):
        """Singole parole minuscole non sono proprie."""
        assert has_proper_name("marco") is False
        assert has_proper_name("azienda") is False


# =============================================================================
# TEST: Entity Validation
# =============================================================================

class TestEntityValidation:
    """Test validazione entità estratte."""

    def test_extractor_filters_low_confidence(self):
        """Entità con bassa confidence vengono filtrate."""
        extractor = KGExtractor()
        extractor.min_confidence = 0.4

        # Entity con confidence bassa
        raw = {
            "name": "Marco Rossi",
            "type": "person",
            "confidence": 0.2,
            "properties": {}
        }

        result = extractor._validate_entity(raw)
        assert result is None

    def test_extractor_filters_generic_references(self):
        """Riferimenti generici vengono filtrati."""
        extractor = KGExtractor()

        raw = {
            "name": "lui",
            "type": "person",
            "confidence": 0.9,
            "properties": {}
        }

        result = extractor._validate_entity(raw)
        assert result is None

    def test_extractor_accepts_valid_entity(self):
        """Entità valide vengono accettate."""
        extractor = KGExtractor()

        raw = {
            "name": "Marco Rossi",
            "type": "person",
            "confidence": 0.8,
            "properties": {"role": "manager"}
        }

        result = extractor._validate_entity(raw)
        assert result is not None
        assert result.name == "Marco Rossi"
        assert result.type == EntityType.person


# =============================================================================
# TEST: No Hallucination - Extraction
# =============================================================================

class TestNoHallucination:
    """Test che il sistema non inventi dati."""

    @pytest.mark.asyncio
    async def test_empty_message_returns_empty(self):
        """Messaggio vuoto non produce entità."""
        extractor = KGExtractor()

        result = await extractor.process(
            user_id="test_user",
            message="",
            context=""
        )

        assert len(result.entities) == 0
        assert len(result.relationships) == 0

    @pytest.mark.asyncio
    async def test_short_message_returns_empty(self):
        """Messaggio troppo corto non produce entità."""
        extractor = KGExtractor()

        result = await extractor.process(
            user_id="test_user",
            message="ciao",
            context=""
        )

        assert len(result.entities) == 0
        assert len(result.relationships) == 0

    def test_validation_rejects_invalid_types(self):
        """Tipi inventati dall'LLM vengono rifiutati."""
        kg = KnowledgeGraphManager()

        # Entity con tipo inventato
        entity = {
            "canonical_name": "Test Entity",
            "entity_type": "invented_type",  # Tipo non valido
            "confidence": 0.9
        }

        result = kg._validate_entity(entity)
        assert result is False

    def test_validation_rejects_invalid_relationship_types(self):
        """Relazioni con tipi inventati vengono rifiutate."""
        kg = KnowledgeGraphManager()

        rel = {
            "source": "Marco Rossi",
            "target": "Acme Corp",
            "relationship_type": "invented_relationship"  # Tipo non valido
        }

        valid_names = {"marco rossi", "acme corp"}
        result = kg._validate_relationship(rel, valid_names)
        assert result is False


# =============================================================================
# TEST: Entity Resolution
# =============================================================================

class TestEntityResolution:
    """Test entity resolution e deduplicazione."""

    def test_validation_result_structure(self):
        """Risultato validazione ha struttura corretta."""
        extractor = KGExtractor()

        raw = {
            "entities": [
                {"name": "Marco Rossi", "type": "person", "confidence": 0.9, "properties": {}},
                {"name": "Acme Corp", "type": "organization", "confidence": 0.85, "properties": {}}
            ],
            "relationships": [
                {"source": "Marco Rossi", "target": "Acme Corp", "type": "works_for", "confidence": 0.8, "properties": {}}
            ]
        }

        result = extractor._validate_extraction(raw)

        assert isinstance(result, KGExtractionResult)
        assert len(result.entities) == 2
        assert len(result.relationships) == 1

    def test_relationship_requires_valid_entities(self):
        """Relazioni richiedono che entrambe le entità esistano."""
        extractor = KGExtractor()

        raw = {
            "entities": [
                {"name": "Marco Rossi", "type": "person", "confidence": 0.9, "properties": {}}
                # Manca Acme Corp
            ],
            "relationships": [
                {"source": "Marco Rossi", "target": "Acme Corp", "type": "works_for", "confidence": 0.8, "properties": {}}
            ]
        }

        result = extractor._validate_extraction(raw)

        # La relazione deve essere scartata perché Acme Corp non esiste
        assert len(result.relationships) == 0


# =============================================================================
# TEST: JSON Parsing Robustness
# =============================================================================

class TestJSONParsing:
    """Test parsing JSON robusto da LLM."""

    def test_parse_clean_json(self):
        """Parse JSON pulito."""
        kg = KnowledgeGraphManager()
        response = '[{"canonical_name": "Test", "entity_type": "person"}]'
        result = kg._parse_json_response(response)
        assert result is not None
        assert len(result) == 1

    def test_parse_json_with_markdown(self):
        """Parse JSON con markdown code block."""
        kg = KnowledgeGraphManager()
        response = '```json\n[{"canonical_name": "Test", "entity_type": "person"}]\n```'
        result = kg._parse_json_response(response)
        assert result is not None
        assert len(result) == 1

    def test_parse_json_with_extra_text(self):
        """Parse JSON con testo extra."""
        kg = KnowledgeGraphManager()
        response = 'Here are the entities: [{"canonical_name": "Test", "entity_type": "person"}]'
        result = kg._parse_json_response(response)
        assert result is not None
        assert len(result) == 1

    def test_parse_invalid_json_returns_none(self):
        """JSON invalido ritorna None."""
        kg = KnowledgeGraphManager()
        response = "This is not JSON at all"
        result = kg._parse_json_response(response)
        assert result is None


# =============================================================================
# TEST: Integration - Full Pipeline
# =============================================================================

class TestFullPipeline:
    """Test pipeline completa di estrazione."""

    @pytest.mark.asyncio
    async def test_extraction_with_mock_llm(self):
        """Test estrazione con LLM mockato."""
        extractor = KGExtractor()

        # Mock della risposta LLM
        mock_llm_response = json.dumps({
            "entities": [
                {
                    "name": "Marco Rossi",
                    "type": "person",
                    "properties": {"role": "CEO"},
                    "confidence": 0.9
                },
                {
                    "name": "Acme Corporation",
                    "type": "organization",
                    "properties": {"industry": "tech"},
                    "confidence": 0.85
                }
            ],
            "relationships": [
                {
                    "source": "Marco Rossi",
                    "target": "Acme Corporation",
                    "type": "works_for",
                    "properties": {},
                    "confidence": 0.8
                }
            ]
        })

        with patch.object(extractor, '_extract_with_llm', return_value=json.loads(mock_llm_response)):
            with patch.object(extractor, '_persist', return_value=None):
                result = await extractor.process(
                    user_id="test_user",
                    message="Ho parlato con Marco Rossi, CEO di Acme Corporation",
                    context=""
                )

                assert len(result.entities) == 2
                assert len(result.relationships) == 1

                # Verifica entità
                person = next(e for e in result.entities if e.type == EntityType.person)
                assert person.name == "Marco Rossi"
                assert person.properties.get("role") == "CEO"

                org = next(e for e in result.entities if e.type == EntityType.organization)
                assert org.name == "Acme Corporation"

                # Verifica relazione
                rel = result.relationships[0]
                assert rel.source == "Marco Rossi"
                assert rel.target == "Acme Corporation"
                assert rel.type == RelationshipType.works_for


# =============================================================================
# TEST: Constants Consistency
# =============================================================================

class TestConstantsConsistency:
    """Test che le costanti siano consistenti tra moduli."""

    def test_entity_types_match(self):
        """EntityType enum deve matchare VALID_ENTITY_TYPES."""
        enum_values = {e.value for e in EntityType}
        assert enum_values == VALID_ENTITY_TYPES

    def test_relationship_types_match(self):
        """RelationshipType enum deve matchare VALID_RELATIONSHIP_TYPES."""
        enum_values = {r.value for r in RelationshipType}
        assert enum_values == VALID_RELATIONSHIP_TYPES

    def test_aliases_map_to_valid_types(self):
        """Tutti gli alias devono mappare a tipi validi."""
        for alias, target in ENTITY_TYPE_ALIASES.items():
            assert target in VALID_ENTITY_TYPES, f"Alias '{alias}' maps to invalid type '{target}'"

        for alias, target in RELATIONSHIP_TYPE_ALIASES.items():
            assert target in VALID_RELATIONSHIP_TYPES, f"Alias '{alias}' maps to invalid type '{target}'"
