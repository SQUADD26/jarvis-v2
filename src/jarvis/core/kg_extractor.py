"""
Knowledge Graph Extractor

Estrae entità e relazioni dalle conversazioni usando Gemini.
Processa in background per non bloccare le risposte.
"""

import asyncio
import json
import re
from typing import Optional

from jarvis.core.kg_types import (
    EntityType,
    RelationshipType,
    ExtractedEntity,
    ExtractedRelationship,
    KGExtractionResult,
)
from jarvis.db.kg_repository import (
    KGEntityRepository,
    KGRelationshipRepository,
    KGAliasRepository,
)
from jarvis.integrations.gemini import gemini
from jarvis.integrations.openai_embeddings import openai_embeddings
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# EXTRACTION PROMPT
# =============================================================================

KG_EXTRACTION_PROMPT = """Sei un estrattore di entità per un Knowledge Graph personale.

## TIPOLOGIE ENTITÀ (USA SOLO QUESTE)
- `person`: Persone fisiche (es: Marco Rossi, il CEO, mia sorella)
- `organization`: Aziende, enti, istituzioni (es: Acme Corp, INPS, Google)
- `project`: Progetti, iniziative con nome (es: Progetto Phoenix, App Mobile)
- `location`: Luoghi fisici (es: Milano, Ufficio Roma, sede centrale)
- `event`: Eventi con data (es: Conferenza AI 2025, meeting Q1)

## TIPOLOGIE RELAZIONI (USA SOLO QUESTE)
Persona-Persona:
- `reports_to`: A è subordinato di B
- `collaborates_with`: A lavora con B (peer)
- `knows`: A conosce B
- `is_family_of`: A è parente di B

Persona-Organizzazione:
- `works_for`: A lavora per B
- `is_client_of`: A è cliente di B
- `is_partner_of`: A è partner di B
- `owns`: A possiede B

Persona-Progetto:
- `leads`: A guida il progetto B
- `works_on`: A lavora sul progetto B
- `created`: A ha creato B

Qualsiasi-Location:
- `located_in`: A si trova in B
- `lives_in`: A vive in B

Persona-Evento:
- `attended`: A ha partecipato a B
- `organized`: A ha organizzato B

Organizzazione-Organizzazione:
- `subsidiary_of`: A è sussidiaria di B
- `competes_with`: A compete con B

Fallback:
- `related_to`: Relazione generica (usa solo se nessun'altra è adatta)

## OUTPUT FORMAT (JSON STRICT)
Rispondi SOLO con un oggetto JSON valido, senza markdown o altro testo:
{
    "entities": [
        {
            "name": "Nome Canonico",
            "type": "person|organization|project|location|event",
            "properties": {"role": "...", "email": "..."},
            "confidence": 0.0-1.0
        }
    ],
    "relationships": [
        {
            "source": "Nome Entità A",
            "target": "Nome Entità B",
            "type": "works_for|reports_to|...",
            "properties": {},
            "confidence": 0.0-1.0
        }
    ]
}

## REGOLE CRITICHE
1. USA SOLO le tipologie elencate sopra - NON INVENTARE NUOVE TIPOLOGIE
2. Se non sei sicuro del tipo, usa confidence bassa (< 0.5)
3. Nomi propri in forma canonica ("Marco Rossi", non "marco")
4. NON estrarre pronomi generici ("lui", "quella persona", "l'azienda")
5. NON estrarre entità vaghe senza nome proprio
6. Se nessuna entità rilevante è presente, ritorna {"entities": [], "relationships": []}
7. Estrai SOLO informazioni ESPLICITAMENTE menzionate, NON inferire

## MESSAGGIO DA ANALIZZARE
{message}

## CONTESTO CONVERSAZIONE (se disponibile)
{context}"""


# =============================================================================
# ALIAS MAPPING (Fallback per errori LLM)
# =============================================================================

ENTITY_TYPE_ALIASES = {
    # Italiano
    "persona": "person",
    "azienda": "organization",
    "società": "organization",
    "impresa": "organization",
    "ditta": "organization",
    "progetto": "project",
    "luogo": "location",
    "città": "location",
    "paese": "location",
    "evento": "event",
    "meeting": "event",
    "riunione": "event",
    # Inglese varianti
    "company": "organization",
    "firm": "organization",
    "corp": "organization",
    "corporation": "organization",
    "individual": "person",
    "place": "location",
    "city": "location",
    "country": "location",
}

RELATIONSHIP_TYPE_ALIASES = {
    # Italiano
    "lavora_per": "works_for",
    "lavora_con": "collaborates_with",
    "conosce": "knows",
    "guida": "leads",
    "vive_a": "lives_in",
    "vive_in": "lives_in",
    "si_trova_a": "located_in",
    "famiglia": "is_family_of",
    # Varianti inglesi
    "employed_by": "works_for",
    "works_at": "works_for",
    "manages": "leads",
    "member_of": "works_for",
    "belongs_to": "works_for",
    "part_of": "subsidiary_of",
    "located_at": "located_in",
    "based_in": "located_in",
}


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def normalize_entity_type(raw_type: str) -> Optional[EntityType]:
    """Normalizza tipo entità al valore DB."""
    if not raw_type:
        return None

    normalized = raw_type.lower().strip()

    # Già valido?
    try:
        return EntityType(normalized)
    except ValueError:
        pass

    # Alias?
    if normalized in ENTITY_TYPE_ALIASES:
        return EntityType(ENTITY_TYPE_ALIASES[normalized])

    # Sconosciuto
    logger.warning(f"Unknown entity type: {raw_type}")
    return None


def normalize_relationship_type(raw_type: str) -> Optional[RelationshipType]:
    """Normalizza tipo relazione al valore DB."""
    if not raw_type:
        return None

    normalized = raw_type.lower().strip()

    # Già valido?
    try:
        return RelationshipType(normalized)
    except ValueError:
        pass

    # Alias?
    if normalized in RELATIONSHIP_TYPE_ALIASES:
        return RelationshipType(RELATIONSHIP_TYPE_ALIASES[normalized])

    # Fallback generico
    logger.warning(f"Unknown relationship type: {raw_type}, using 'related_to'")
    return RelationshipType.related_to


def is_generic_reference(name: str) -> bool:
    """Verifica se un nome è un riferimento generico (da scartare)."""
    generic_patterns = [
        r"^(lui|lei|esso|essa|loro)$",
        r"^(il|la|lo|l'|i|gli|le)\s+(tipo|tizio|persona|azienda|ditta|società)$",
        r"^(quello|quella|quelli|quelle)$",
        r"^(quello|quella|quelli|quelle)\s+(tipo|tizio|persona|azienda|ditta|uomo|donna)$",
        r"^(qualcuno|qualcosa|qualcheduno)$",
        r"^(un|una|uno)\s+(amico|collega|persona|tizio)$",
        r"^(this|that|he|she|it|they|them|someone|somebody)$",
        r"^(the|a|an)\s+(person|company|guy|thing)$",
    ]

    name_lower = name.lower().strip()
    for pattern in generic_patterns:
        if re.match(pattern, name_lower):
            return True

    # Troppo corto (probabilmente un pronome)
    if len(name_lower) <= 2:
        return True

    return False


def has_proper_name(name: str) -> bool:
    """Verifica se il nome sembra un nome proprio."""
    # Deve avere almeno una lettera maiuscola o essere tutto maiuscolo
    if any(c.isupper() for c in name):
        return True

    # Oppure contenere più parole
    if len(name.split()) >= 2:
        return True

    return False


# =============================================================================
# MAIN EXTRACTOR CLASS
# =============================================================================

class KGExtractor:
    """
    Estrattore Knowledge Graph.

    Processa messaggi in background per estrarre entità e relazioni.
    """

    def __init__(self):
        self.min_confidence = 0.4  # Soglia minima per salvare
        self.extraction_model = "gemini-2.5-flash"  # Modello veloce per estrazione

    async def process(
        self,
        user_id: str,
        message: str,
        context: str = "",
        source_id: str = None
    ) -> KGExtractionResult:
        """
        Processa un messaggio ed estrae entità/relazioni.

        Args:
            user_id: ID utente
            message: Messaggio da analizzare
            context: Contesto conversazione (opzionale)
            source_id: ID sorgente per tracking (opzionale)

        Returns:
            KGExtractionResult con entità e relazioni estratte
        """
        # Skip messaggi troppo corti o vuoti
        if not message or len(message.strip()) < 10:
            return KGExtractionResult()

        try:
            # 1. Estrai candidati con LLM
            raw_result = await self._extract_with_llm(message, context)

            if not raw_result:
                return KGExtractionResult()

            # 2. Valida e normalizza
            validated = self._validate_extraction(raw_result)

            if not validated.entities and not validated.relationships:
                return KGExtractionResult()

            # 3. Persisti nel database
            await self._persist(user_id, validated, source_id)

            return validated

        except Exception as e:
            logger.error(f"KG extraction failed: {e}")
            return KGExtractionResult()

    async def _extract_with_llm(
        self,
        message: str,
        context: str = ""
    ) -> Optional[dict]:
        """Estrae entità usando Gemini."""
        prompt = KG_EXTRACTION_PROMPT.format(
            message=message,
            context=context or "Nessun contesto aggiuntivo."
        )

        try:
            response = await gemini.generate(
                prompt=prompt,
                model=self.extraction_model,
                temperature=0.1,  # Bassa per consistenza
                max_tokens=2048
            )

            # Parse JSON dalla risposta
            return self._parse_json_response(response)

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return None

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """Parse JSON dalla risposta LLM (con fallback)."""
        if not response:
            return None

        # Rimuovi markdown code blocks se presenti
        response = response.strip()
        if response.startswith("```"):
            # Trova il contenuto tra i backticks
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
            if match:
                response = match.group(1)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Prova a trovare JSON nel testo
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass

            logger.warning(f"Failed to parse JSON response: {response[:200]}...")
            return None

    def _validate_extraction(self, raw: dict) -> KGExtractionResult:
        """Valida e normalizza l'estrazione."""
        entities = []
        relationships = []

        # Valida entità
        for e in raw.get("entities", []):
            validated = self._validate_entity(e)
            if validated:
                entities.append(validated)

        # Valida relazioni (solo se entrambe le entità esistono)
        entity_names = {e.name.lower() for e in entities}
        for r in raw.get("relationships", []):
            validated = self._validate_relationship(r, entity_names)
            if validated:
                relationships.append(validated)

        return KGExtractionResult(entities=entities, relationships=relationships)

    def _validate_entity(self, raw: dict) -> Optional[ExtractedEntity]:
        """Valida una singola entità."""
        name = raw.get("name", "").strip()
        raw_type = raw.get("type", "")
        confidence = float(raw.get("confidence", 0.5))
        properties = raw.get("properties", {})

        # Filtri
        if not name:
            return None

        if is_generic_reference(name):
            logger.debug(f"Skipping generic reference: {name}")
            return None

        if confidence < self.min_confidence:
            logger.debug(f"Skipping low confidence entity: {name} ({confidence})")
            return None

        # Normalizza tipo
        entity_type = normalize_entity_type(raw_type)
        if not entity_type:
            return None

        # Per persone, verifica che abbia un nome proprio
        if entity_type == EntityType.person and not has_proper_name(name):
            logger.debug(f"Skipping person without proper name: {name}")
            return None

        return ExtractedEntity(
            name=name,
            type=entity_type,
            properties=properties if isinstance(properties, dict) else {},
            confidence=confidence
        )

    def _validate_relationship(
        self,
        raw: dict,
        valid_entity_names: set[str]
    ) -> Optional[ExtractedRelationship]:
        """Valida una singola relazione."""
        source = raw.get("source", "").strip()
        target = raw.get("target", "").strip()
        raw_type = raw.get("type", "")
        confidence = float(raw.get("confidence", 0.5))
        properties = raw.get("properties", {})

        # Verifica che source e target siano entità valide
        if source.lower() not in valid_entity_names:
            return None
        if target.lower() not in valid_entity_names:
            return None

        if confidence < self.min_confidence:
            return None

        # Normalizza tipo
        rel_type = normalize_relationship_type(raw_type)
        if not rel_type:
            return None

        return ExtractedRelationship(
            source=source,
            target=target,
            type=rel_type,
            properties=properties if isinstance(properties, dict) else {},
            confidence=confidence
        )

    async def _persist(
        self,
        user_id: str,
        result: KGExtractionResult,
        source_id: str = None
    ) -> None:
        """Persiste entità e relazioni nel database."""
        entity_id_map = {}  # name -> entity_id

        # 1. Crea/aggiorna entità
        for entity in result.entities:
            try:
                # Genera embedding per l'entità
                embed_text = f"{entity.name} ({entity.type.value})"
                if entity.properties:
                    embed_text += f" - {json.dumps(entity.properties)}"

                embedding = await openai_embeddings.embed(embed_text)

                # Cerca se esiste già
                existing = await KGEntityRepository.get_entity_by_name(
                    user_id=user_id,
                    canonical_name=entity.name,
                    entity_type=entity.type.value
                )

                if existing:
                    # Aggiorna mention count
                    await KGEntityRepository.update_mention(existing["id"])

                    # Merge properties se ci sono nuove info
                    if entity.properties:
                        await KGEntityRepository.merge_properties(
                            existing["id"],
                            entity.properties
                        )

                    entity_id_map[entity.name.lower()] = existing["id"]
                    logger.debug(f"Updated existing entity: {entity.name}")

                else:
                    # Crea nuova entità
                    new_entity = await KGEntityRepository.create_entity(
                        user_id=user_id,
                        canonical_name=entity.name,
                        entity_type=entity.type.value,
                        properties=entity.properties,
                        embedding=embedding,
                        confidence=entity.confidence,
                        source_type="conversation",
                        source_id=source_id
                    )

                    if new_entity:
                        entity_id_map[entity.name.lower()] = new_entity["id"]
                        logger.debug(f"Created new entity: {entity.name}")

            except Exception as e:
                logger.error(f"Failed to persist entity {entity.name}: {e}")

        # 2. Crea relazioni
        for rel in result.relationships:
            try:
                source_id_db = entity_id_map.get(rel.source.lower())
                target_id_db = entity_id_map.get(rel.target.lower())

                if not source_id_db or not target_id_db:
                    logger.debug(f"Skipping relationship - missing entity: {rel.source} -> {rel.target}")
                    continue

                # Verifica se esiste già
                existing = await KGRelationshipRepository.find_relationship(
                    user_id=user_id,
                    source_entity_id=source_id_db,
                    target_entity_id=target_id_db,
                    relationship_type=rel.type.value
                )

                if existing:
                    # Aggiorna confidence se maggiore
                    if rel.confidence > existing.get("confidence", 0):
                        await KGRelationshipRepository.update_relationship(
                            existing["id"],
                            {"confidence": rel.confidence}
                        )
                    logger.debug(f"Relationship already exists: {rel.source} --[{rel.type.value}]--> {rel.target}")

                else:
                    # Crea nuova relazione
                    await KGRelationshipRepository.create_relationship(
                        user_id=user_id,
                        source_entity_id=source_id_db,
                        target_entity_id=target_id_db,
                        relationship_type=rel.type.value,
                        properties=rel.properties,
                        confidence=rel.confidence,
                        source_type="conversation",
                        source_id=source_id
                    )
                    logger.debug(f"Created relationship: {rel.source} --[{rel.type.value}]--> {rel.target}")

            except Exception as e:
                logger.error(f"Failed to persist relationship {rel.source} -> {rel.target}: {e}")


# =============================================================================
# BACKGROUND PROCESSOR
# =============================================================================

class KGBackgroundProcessor:
    """
    Processore background per estrazione KG.

    Gestisce una coda di messaggi da processare senza bloccare le risposte.
    """

    def __init__(self):
        self.extractor = KGExtractor()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Avvia il processore background."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("KG background processor started")

    async def stop(self):
        """Ferma il processore background."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("KG background processor stopped")

    async def enqueue(
        self,
        user_id: str,
        message: str,
        context: str = "",
        source_id: str = None
    ):
        """Aggiunge un messaggio alla coda di processing."""
        await self._queue.put({
            "user_id": user_id,
            "message": message,
            "context": context,
            "source_id": source_id
        })

    async def _process_loop(self):
        """Loop principale di processing."""
        while self._running:
            try:
                # Attendi con timeout per permettere shutdown graceful
                item = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0
                )

                # Processa
                await self.extractor.process(
                    user_id=item["user_id"],
                    message=item["message"],
                    context=item["context"],
                    source_id=item["source_id"]
                )

                self._queue.task_done()

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"KG processing error: {e}")


# =============================================================================
# SINGLETONS
# =============================================================================

kg_extractor = KGExtractor()
kg_processor = KGBackgroundProcessor()
