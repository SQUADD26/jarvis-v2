"""
Knowledge Graph Types and Models

Enum e Pydantic models per il Knowledge Graph.
I valori degli Enum DEVONO corrispondere esattamente ai tipi nel database PostgreSQL.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Tipi di entità - DEVE corrispondere a entity_type nel DB"""
    person = "person"
    organization = "organization"
    project = "project"
    location = "location"
    event = "event"


class RelationshipType(str, Enum):
    """Tipi di relazione - DEVE corrispondere a relationship_type nel DB"""
    # Person-Person
    reports_to = "reports_to"
    collaborates_with = "collaborates_with"
    knows = "knows"
    is_family_of = "is_family_of"

    # Person-Organization
    works_for = "works_for"
    is_client_of = "is_client_of"
    is_partner_of = "is_partner_of"
    owns = "owns"

    # Person-Project
    leads = "leads"
    works_on = "works_on"
    created = "created"

    # Any-Location
    located_in = "located_in"
    lives_in = "lives_in"

    # Person-Event
    attended = "attended"
    organized = "organized"

    # Organization-Organization
    subsidiary_of = "subsidiary_of"
    competes_with = "competes_with"

    # Generic fallback
    related_to = "related_to"


class ExtractedEntity(BaseModel):
    """Entità estratta dal LLM"""
    name: str = Field(..., description="Nome canonico dell'entità")
    type: EntityType = Field(..., description="Tipo dell'entità")
    properties: dict[str, Any] = Field(default_factory=dict, description="Proprietà aggiuntive")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence dell'estrazione")


class ExtractedRelationship(BaseModel):
    """Relazione estratta dal LLM"""
    source: str = Field(..., description="Nome entità sorgente")
    target: str = Field(..., description="Nome entità target")
    type: RelationshipType = Field(..., description="Tipo della relazione")
    properties: dict[str, Any] = Field(default_factory=dict, description="Proprietà aggiuntive")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence dell'estrazione")


class KGExtractionResult(BaseModel):
    """Risultato completo dell'estrazione KG"""
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)


class KGEntity(BaseModel):
    """Entità nel Knowledge Graph (dal DB)"""
    id: str
    user_id: str
    canonical_name: str
    entity_type: EntityType
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.5
    mention_count: int = 1
    first_mentioned_at: str | None = None
    last_mentioned_at: str | None = None
    source_type: str = "conversation"
    source_id: str | None = None


class KGRelationship(BaseModel):
    """Relazione nel Knowledge Graph (dal DB)"""
    id: str
    user_id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: RelationshipType
    properties: dict[str, Any] = Field(default_factory=dict)
    is_current: bool = True
    started_at: str | None = None
    ended_at: str | None = None
    confidence: float = 0.5
    source_type: str = "conversation"
    source_id: str | None = None


class KGEntityWithRelationships(BaseModel):
    """Entità con le sue relazioni (per context injection)"""
    entity: KGEntity
    relationships: list[dict[str, Any]] = Field(default_factory=list)
