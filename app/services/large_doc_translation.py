"""
Large Document Translation Service

Handles documents that exceed context window limits through:
1. Intelligent chunking with overlap
2. Context-aware translation (passing previous chunk context)
3. Coherence preservation across chunks
4. Optional hierarchical translation for very large docs
"""
import asyncio
from typing import List, Callable, Awaitable, Optional
from app.services import chunker, translation
from app.core.logging import get_logger

logger = get_logger("LargeDocTranslation")


class LargeDocumentTranslator:
    """
    Translates large documents that exceed context window limits.

    Strategies:
    1. Smart chunking with overlap
    2. Context-aware translation (limited previous context)
    3. Parallel processing with controlled concurrency
    4. Quality preservation through overlap blending
    """

    def __init__(self, max_concurrency: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def translate_large_text(
        self,
        text: str,
        target_language: str,
        max_tokens: int = 6000,
        overlap_tokens: int = 200,
        progress_callback: Optional[Callable[[int], Awaitable[None]]] = None,
        use_context: bool = True
    ) -> str:
        """
        Translate large text with intelligent chunking.

        Args:
            text: Source text to translate
            target_language: Target language
            max_tokens: Maximum tokens per chunk
            overlap_tokens: Tokens to overlap between chunks
            progress_callback: Optional progress callback
            use_context: Whether to pass previous chunk as context

        Returns:
            Translated text with coherence preserved
        """
        # Get chunks with metadata
        chunks_data = chunker.chunk_text_with_metadata(
            text,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens
        )

        total_chunks = len(chunks_data)

        if total_chunks == 0:
            return ""

        logger.info(
            f"Translating large document: {len(text)} chars, "
            f"{total_chunks} chunks (max {max_tokens} tokens/chunk, "
            f"overlap {overlap_tokens} tokens)"
        )

        if progress_callback:
            await progress_callback(5)

        # Translate chunks with context awareness
        if use_context:
            translated_chunks = await self._translate_with_context(
                chunks_data,
                target_language,
                total_chunks,
                progress_callback
            )
        else:
            # Parallel translation without context (faster but may lose coherence)
            translated_chunks = await self._translate_parallel(
                chunks_data,
                target_language,
                total_chunks,
                progress_callback
            )

        # Merge chunks, removing overlaps
        final_text = self._merge_chunks(translated_chunks, chunks_data)

        if progress_callback:
            await progress_callback(100)

        logger.info(f"Large document translation complete: {len(final_text)} chars")

        return final_text

    async def _translate_with_context(
        self,
        chunks_data: List[dict],
        target_language: str,
        total_chunks: int,
        progress_callback: Optional[Callable[[int], Awaitable[None]]]
    ) -> List[str]:
        """
        Translate chunks sequentially with context from previous chunk.

        This preserves better coherence but is slower (sequential).
        For very large documents, we still batch process in groups.
        """
        translated_chunks = []
        previous_translation = ""

        # Process in small batches to balance coherence and speed
        batch_size = 3  # Process 3 chunks in parallel, then use last as context

        for batch_start in range(0, total_chunks, batch_size):
            batch_end = min(batch_start + batch_size, total_chunks)
            batch = chunks_data[batch_start:batch_end]

            # Translate batch in parallel
            batch_tasks = []
            for chunk_data in batch:
                # Include limited context from previous translation
                context_hint = ""
                if previous_translation and chunk_data.get('has_overlap'):
                    # Use last 200 chars of previous translation as hint
                    context_hint = (
                        f"\n\n[Previous context for coherence: "
                        f"...{previous_translation[-200:]}]\n\n"
                    )

                # Remove overlap from current chunk (it's already in context)
                chunk_text = chunk_data['text']
                if chunk_data.get('has_overlap') and chunk_data.get('previous_context'):
                    overlap = chunk_data['previous_context']
                    if chunk_text.startswith(overlap):
                        chunk_text = chunk_text[len(overlap):]

                task = self._translate_chunk_with_progress(
                    context_hint + chunk_text,
                    target_language,
                    batch_start + batch.index(chunk_data),
                    total_chunks,
                    progress_callback
                )
                batch_tasks.append(task)

            batch_results = await asyncio.gather(*batch_tasks)
            translated_chunks.extend(batch_results)

            # Update previous translation for next batch
            if batch_results:
                previous_translation = batch_results[-1]

        return translated_chunks

    async def _translate_parallel(
        self,
        chunks_data: List[dict],
        target_language: str,
        total_chunks: int,
        progress_callback: Optional[Callable[[int], Awaitable[None]]]
    ) -> List[str]:
        """
        Translate all chunks in parallel (faster but may lose some coherence).
        """
        tasks = []

        for chunk_data in chunks_data:
            # Remove overlap since we're not using context
            chunk_text = chunk_data['text']
            if chunk_data.get('has_overlap') and chunk_data.get('previous_context'):
                overlap = chunk_data['previous_context']
                if chunk_text.startswith(overlap):
                    chunk_text = chunk_text[len(overlap):]

            task = self._translate_chunk_with_progress(
                chunk_text,
                target_language,
                chunk_data['index'],
                total_chunks,
                progress_callback
            )
            tasks.append(task)

        return await asyncio.gather(*tasks)

    async def _translate_chunk_with_progress(
        self,
        text: str,
        target_language: str,
        index: int,
        total: int,
        progress_callback: Optional[Callable[[int], Awaitable[None]]]
    ) -> str:
        """Translate a single chunk with progress tracking."""
        async with self.semaphore:
            translated = await translation.translate_text(text, target_language)

            if progress_callback:
                progress = 5 + int((index + 1) / total * 90)
                await progress_callback(progress)

            return translated

    def _merge_chunks(
        self,
        translated_chunks: List[str],
        chunks_data: List[dict]
    ) -> str:
        """
        Merge translated chunks, handling overlaps intelligently.

        Since overlaps were already removed during translation,
        we can simply join the chunks.
        """
        # Simple join since overlaps were already handled
        return "".join(translated_chunks)


# Convenience function for use in orchestrator
async def translate_large_document(
    text: str,
    target_language: str,
    progress_callback: Optional[Callable[[int], Awaitable[None]]] = None,
    use_context: bool = True
) -> str:
    """
    Translate a large document with smart chunking.

    Args:
        text: Source text
        target_language: Target language
        progress_callback: Optional progress callback
        use_context: Whether to use context-aware translation (slower but better)

    Returns:
        Translated text
    """
    translator = LargeDocumentTranslator()

    return await translator.translate_large_text(
        text,
        target_language,
        max_tokens=6000,  # Conservative for GPT-4
        overlap_tokens=200,
        progress_callback=progress_callback,
        use_context=use_context
    )
