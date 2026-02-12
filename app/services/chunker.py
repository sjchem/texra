"""
Intelligent text chunking for large documents.

Strategies for handling documents that exceed context windows:
1. Smart boundary detection (paragraphs, sections, sentences)
2. Overlap between chunks for context preservation
3. Adaptive chunk sizes based on content type
4. Token-aware chunking (not just character count)
"""
import re
from typing import List, Dict, Any


class SmartChunker:
    """
    Intelligent chunker for large documents.

    Features:
    - Preserves semantic boundaries (paragraphs, sections)
    - Adds overlap between chunks for context
    - Handles various content types appropriately
    - Token-aware sizing
    """

    def __init__(
        self,
        max_tokens: int = 6000,  # Conservative for GPT-4
        overlap_tokens: int = 200,  # Context overlap
        chars_per_token: int = 4   # Rough estimate: 1 token ≈ 4 chars
    ):
        self.max_chars = max_tokens * chars_per_token
        self.overlap_chars = overlap_tokens * chars_per_token
        self.chars_per_token = chars_per_token

    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Chunk text intelligently with metadata.

        Returns:
            List of dicts with:
            - text: chunk content
            - index: chunk number
            - has_overlap: whether this chunk has context from previous
            - boundary_type: what type of boundary (paragraph, sentence, etc.)
        """
        # First, try to split by major sections (double newlines)
        sections = self._split_by_sections(text)

        chunks = []
        current_chunk = ""
        previous_overlap = ""
        chunk_index = 0

        for section in sections:
            # If section fits in current chunk
            if len(current_chunk) + len(section) <= self.max_chars:
                current_chunk += section
            else:
                # Current chunk is full, save it
                if current_chunk:
                    chunks.append({
                        'text': current_chunk,
                        'index': chunk_index,
                        'has_overlap': len(previous_overlap) > 0,
                        'boundary_type': 'section',
                        'previous_context': previous_overlap
                    })

                    # Prepare overlap for next chunk
                    previous_overlap = self._get_overlap(current_chunk)
                    chunk_index += 1

                # If section itself is too large, split it further
                if len(section) > self.max_chars:
                    sub_chunks = self._split_large_section(section)
                    for sub_chunk in sub_chunks:
                        full_chunk = previous_overlap + sub_chunk
                        chunks.append({
                            'text': full_chunk,
                            'index': chunk_index,
                            'has_overlap': len(previous_overlap) > 0,
                            'boundary_type': 'sentence',
                            'previous_context': previous_overlap
                        })
                        previous_overlap = self._get_overlap(sub_chunk)
                        chunk_index += 1
                    current_chunk = ""
                else:
                    # Start new chunk with overlap
                    current_chunk = previous_overlap + section

        # Don't forget the last chunk
        if current_chunk:
            chunks.append({
                'text': current_chunk,
                'index': chunk_index,
                'has_overlap': len(previous_overlap) > 0,
                'boundary_type': 'end',
                'previous_context': previous_overlap
            })

        return chunks

    def _split_by_sections(self, text: str) -> List[str]:
        """Split text by paragraphs/sections (double newlines)."""
        # Split on double newlines but keep the newlines
        sections = re.split(r'(\n\s*\n)', text)

        # Recombine section content with their separators
        result = []
        for i in range(0, len(sections), 2):
            section = sections[i]
            separator = sections[i + 1] if i + 1 < len(sections) else ''
            result.append(section + separator)

        return [s for s in result if s.strip()]

    def _split_large_section(self, section: str) -> List[str]:
        """Split a large section by sentences."""
        # Split by sentence boundaries
        sentences = re.split(r'([.!?]+\s+)', section)

        chunks = []
        current = ""

        # Recombine sentences with their punctuation
        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            punct = sentences[i + 1] if i + 1 < len(sentences) else ''
            full_sentence = sentence + punct

            if len(current) + len(full_sentence) <= self.max_chars:
                current += full_sentence
            else:
                if current:
                    chunks.append(current)
                current = full_sentence

        if current:
            chunks.append(current)

        return chunks

    def _get_overlap(self, text: str) -> str:
        """
        Get the last portion of text to use as context for next chunk.

        Strategy: Take last complete sentence(s) up to overlap_chars
        """
        if len(text) <= self.overlap_chars:
            return text

        # Take the last overlap_chars characters
        overlap_start = len(text) - self.overlap_chars
        overlap_text = text[overlap_start:]

        # Find the first sentence boundary to start from
        sentence_match = re.search(r'[.!?]+\s+', overlap_text)
        if sentence_match:
            # Start from after the first sentence boundary
            return overlap_text[sentence_match.end():]

        # If no sentence boundary, return the whole overlap
        return overlap_text


def chunk_text(text: str, max_chars=4000) -> list[str]:
    """
    Legacy simple chunker for backward compatibility.

    For large documents, use SmartChunker instead.
    Updated to handle larger chunks (4000 chars) for improved coherence.
    """
    chunks, current = [], ""
    for para in text.split("\n\n"):
        if len(current) + len(para) < max_chars:
            current += para + "\n\n"
        else:
            if current:
                chunks.append(current)
            current = para + "\n\n"
    if current:
        chunks.append(current)
    return chunks


def chunk_text_smart(text: str, max_tokens: int = 6000, overlap_tokens: int = 200) -> list[str]:
    """
    Smart chunking with overlap for large documents.

    Args:
        text: Text to chunk
        max_tokens: Maximum tokens per chunk
        overlap_tokens: Tokens to overlap between chunks

    Returns:
        List of text chunks with context preservation
    """
    chunker = SmartChunker(
        max_tokens=max_tokens,
        overlap_tokens=overlap_tokens
    )

    chunk_dicts = chunker.chunk_text(text)

    # Return just the text for backward compatibility
    return [chunk['text'] for chunk in chunk_dicts]


def chunk_text_with_metadata(text: str, max_tokens: int = 6000, overlap_tokens: int = 200) -> List[Dict[str, Any]]:
    """
    Smart chunking that returns full metadata for each chunk.

    Useful for context-aware translation where you need to know
    about chunk boundaries and overlaps.
    """
    chunker = SmartChunker(
        max_tokens=max_tokens,
        overlap_tokens=overlap_tokens
    )

    return chunker.chunk_text(text)
