"""Smart document chunking."""

import re
from dataclasses import dataclass
from jarvis.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Chunk:
    """A document chunk with metadata."""
    content: str
    index: int
    start_char: int
    end_char: int
    metadata: dict


class DocumentChunker:
    """Smart document chunking with overlap."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_text(
        self,
        text: str,
        metadata: dict = None
    ) -> list[Chunk]:
        """
        Chunk text into overlapping pieces, respecting sentence boundaries.

        Args:
            text: The text to chunk
            metadata: Optional metadata to attach to each chunk

        Returns:
            List of Chunk objects
        """
        if not text or len(text) < self.min_chunk_size:
            return [Chunk(
                content=text,
                index=0,
                start_char=0,
                end_char=len(text),
                metadata=metadata or {}
            )] if text else []

        # Clean text
        text = self._clean_text(text)

        # Split into sentences
        sentences = self._split_sentences(text)

        chunks = []
        current_chunk = []
        current_length = 0
        chunk_start = 0
        char_position = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            # If adding this sentence exceeds chunk size
            if current_length + sentence_length > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = " ".join(current_chunk)
                chunks.append(Chunk(
                    content=chunk_text,
                    index=len(chunks),
                    start_char=chunk_start,
                    end_char=char_position,
                    metadata=metadata or {}
                ))

                # Calculate overlap - keep last sentences that fit in overlap
                overlap_text = ""
                overlap_sentences = []
                for s in reversed(current_chunk):
                    if len(overlap_text) + len(s) < self.chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_text = " ".join(overlap_sentences)
                    else:
                        break

                current_chunk = overlap_sentences
                current_length = len(overlap_text)
                chunk_start = char_position - len(overlap_text)

            current_chunk.append(sentence)
            current_length += sentence_length + 1  # +1 for space
            char_position += sentence_length + 1

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            if len(chunk_text) >= self.min_chunk_size:
                chunks.append(Chunk(
                    content=chunk_text,
                    index=len(chunks),
                    start_char=chunk_start,
                    end_char=char_position,
                    metadata=metadata or {}
                ))

        logger.info(f"Chunked text into {len(chunks)} chunks")
        return chunks

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting - handles most cases
        # Split on . ! ? followed by space and capital letter or end of string
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])|(?<=[.!?])$', text)
        return [s.strip() for s in sentences if s.strip()]


# Singleton with default config
chunker = DocumentChunker()
