import asyncio
import random
from typing import Callable, Awaitable, List

from app.services.loader import LoaderFactory
from app.services.writer import WriterFactory
from app.services import chunker, translation, validation


# Threshold for using large document translation (characters)
LARGE_DOC_THRESHOLD = 40000  # ~10,000 tokens with 4 chars/token (~20 pages)


class TranslationOrchestrator:
    def __init__(self, max_concurrency: int = 5):
        # Limit parallel LLM calls (VERY important)
        self.semaphore = asyncio.Semaphore(max_concurrency)

        # Progress tracking
        self._completed_chunks = 0
        self._progress_lock = asyncio.Lock()

        # Quality validation tracking
        self.validation_results = []
        self.enable_validation = True  # Toggle quality validation

    async def translate(
        self,
        file_path: str,
        target_language: str,
        progress_callback: Callable[[int], Awaitable[None]] | None = None,
        output_format: str = "PDF",
        enable_validation: bool = True,
    ) -> str:
        """
        Translate a document with optional quality validation.

        Args:
            file_path: Path to source document
            target_language: Target language code
            progress_callback: Optional progress update callback
            output_format: Output format (PDF, PPTX, DOCX)
            enable_validation: Enable quality validation (default: True)

        Returns:
            Path to translated document
        """
        self.enable_validation = enable_validation
        self.validation_results = []  # Reset validation results

        # Route to specialized workflows based on file type
        file_lower = file_path.lower()

        if file_lower.endswith('.pptx'):
            output_path = await self._translate_pptx(file_path, target_language, progress_callback)
            # Convert to PDF if requested
            if output_format.upper() == "PDF":
                from app.services.format_converter import FormatConverter
                return FormatConverter.pptx_to_pdf(output_path)
            return output_path
        elif file_lower.endswith('.pdf'):
            return await self._translate_pdf(file_path, target_language, progress_callback)
        elif file_lower.endswith('.docx'):
            output_path = await self._translate_docx(file_path, target_language, progress_callback)
            # Convert to PDF if requested
            if output_format.upper() == "PDF":
                from app.services.format_converter import FormatConverter
                return FormatConverter.docx_to_pdf(output_path)
            return output_path
        elif file_lower.endswith('.odt'):
            return await self._translate_standard(
                file_path,
                target_language,
                progress_callback,
                output_format=output_format,
            )
        elif file_lower.endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
            # Images go through OCR -> text extraction -> translation -> PDF output
            return await self._translate_standard(
                file_path,
                target_language,
                progress_callback,
                output_format="PDF",
            )
        else:
            # Standard text-based workflow for ODT, TXT - always outputs PDF
            return await self._translate_standard(
                file_path,
                target_language,
                progress_callback,
                output_format=output_format,
            )

    def get_validation_summary(self) -> dict:
        """
        Get a summary of validation results.

        Returns:
            Summary with average scores and issues
        """
        if not self.validation_results:
            return {
                "validation_enabled": self.enable_validation,
                "chunks_validated": 0,
                "message": "No validation performed"
            }

        total_quality = sum(v.get("quality_score", 0) for v in self.validation_results)
        avg_quality = total_quality / len(self.validation_results)

        all_issues = []
        for v in self.validation_results:
            all_issues.extend(v.get("issues", []))

        high_severity_issues = [i for i in all_issues if i.get("severity") == "high"]

        return {
            "validation_enabled": self.enable_validation,
            "chunks_validated": len(self.validation_results),
            "average_quality_score": round(avg_quality, 1),
            "total_issues": len(all_issues),
            "high_severity_issues": len(high_severity_issues),
            "recommendation": "pass" if avg_quality >= 75 else "review" if avg_quality >= 60 else "retranslate",
            "assessment": (
                "Excellent quality" if avg_quality >= 90 else
                "Good quality" if avg_quality >= 75 else
                "Acceptable quality" if avg_quality >= 60 else
                "Poor quality"
            )
        }

    async def _translate_pptx(
        self,
        file_path: str,
        target_language: str,
        progress_callback: Callable[[int], Awaitable[None]] | None = None,
    ) -> str:
        """Specialized translation workflow for PPTX with formatting preservation."""
        from app.services.pptx_loader import PptxLoader
        from app.services.pptx_writer import PptxWriter
        from app.services.pptx_translation import PptxTranslationService

        # 1. Load PPTX with structure preservation
        if progress_callback:
            await progress_callback(5)

        loader = PptxLoader()
        slides_data = loader.load(file_path)

        # 2. Translate with structure preservation
        if progress_callback:
            await progress_callback(10)

        translation_service = PptxTranslationService(max_concurrency=self.semaphore._value)
        translated_slides = await translation_service.translate_slides(
            slides_data,
            target_language,
            progress_callback
        )

        # 3. Write back to PPTX format
        if progress_callback:
            await progress_callback(95)

        writer = PptxWriter()
        output_path = writer.write(translated_slides, file_path)

        # 4. Validate translation if enabled
        if self.enable_validation:
            await self._validate_document(
                file_path,
                output_path,
                target_language,
                progress_callback
            )

        if progress_callback:
            await progress_callback(100)

        return output_path

    async def _translate_pdf(
        self,
        file_path: str,
        target_language: str,
        progress_callback: Callable[[int], Awaitable[None]] | None = None,
    ) -> str:
        """Specialized translation workflow for PDF with formatting preservation."""
        from app.services.pdf_formatter import PdfFormattingService

        # Translate PDF with formatting preservation
        formatter = PdfFormattingService(max_concurrency=self.semaphore._value)
        output_path = await formatter.translate_pdf(
            file_path,
            target_language,
            progress_callback
        )

        # Validate translation if enabled
        if self.enable_validation:
            await self._validate_document(
                file_path,
                output_path,
                target_language,
                progress_callback
            )

        return output_path

    async def _translate_docx(
        self,
        file_path: str,
        target_language: str,
        progress_callback: Callable[[int], Awaitable[None]] | None = None,
    ) -> str:
        """Specialized translation workflow for DOCX with formatting preservation."""
        from app.services.docx_loader import DocxLoader
        from app.services.docx_writer import DocxWriter
        from app.services.docx_translation import DocxTranslationService

        # 1. Load DOCX with structure preservation
        if progress_callback:
            await progress_callback(5)

        loader = DocxLoader()
        document_data = loader.load(file_path)

        # 2. Translate with structure preservation
        translation_service = DocxTranslationService(max_concurrency=self.semaphore._value)
        translated_document = await translation_service.translate_document(
            document_data,
            target_language,
            progress_callback
        )

        # 3. Write back to DOCX format
        if progress_callback:
            await progress_callback(95)

        writer = DocxWriter()
        output_path = writer.write(translated_document, file_path)

        # 4. Validate translation if enabled
        if self.enable_validation:
            await self._validate_document(
                file_path,
                output_path,
                target_language,
                progress_callback
            )

        if progress_callback:
            await progress_callback(100)

        return output_path

    async def _translate_standard(
        self,
        file_path: str,
        target_language: str,
        progress_callback: Callable[[int], Awaitable[None]] | None = None,
        output_format: str = "PDF",
    ) -> str:
        """Standard translation workflow for text-based documents."""
        # 1. Load document
        loader = LoaderFactory.get_loader(file_path)
        pages = loader.load(file_path)

        # Combine all pages to check if this is a large document
        full_text = "\n\n".join(pages)
        total_chars = len(full_text)

        # If document is large, use smart chunking with context preservation
        if total_chars > LARGE_DOC_THRESHOLD:
            return await self._translate_large_document(
                pages,
                target_language,
                file_path,
                progress_callback,
                output_format=output_format,
            )

        # 2. Chunk pages (standard approach for smaller documents)
        page_chunks: List[List[str]] = [chunker.chunk_text(page) for page in pages]
        all_chunks: List[str] = [chunk for page in page_chunks for chunk in page]
        total_chunks = len(all_chunks)

        # 3. Translate chunks (PARALLEL, SAFE)
        translation_tasks = [
            asyncio.create_task(
                self._translate_chunk_with_progress(
                    chunk_text,
                    target_language,
                    total_chunks,
                    progress_callback,
                )
            )
            for i, chunk_text in enumerate(all_chunks)
        ]

        translated_chunks = await asyncio.gather(*translation_tasks)

        # 4. Validation (sampled, PARALLEL, SAFE) - Optional
        if self.enable_validation:
            if progress_callback:
                await progress_callback(95)

            sample_indices = random.sample(
                range(total_chunks),
                k=min(5, total_chunks),
            )

            validation_tasks = [
                asyncio.create_task(
                    self._validate_and_retry_chunk(
                        all_chunks[idx],
                        translated_chunks,
                        target_language,
                        idx,
                    )
                )
                for idx in sample_indices
            ]

            validation_results = await asyncio.gather(*validation_tasks)
            self.validation_results.extend(validation_results)

        # 5. Reassemble pages
        if progress_callback:
            await progress_callback(98)

        translated_pages: List[str] = []
        chunk_idx = 0

        for page in page_chunks:
            page_text = ""
            for _ in page:
                page_text += translated_chunks[chunk_idx]
                chunk_idx += 1
            translated_pages.append(page_text)

        # 6. Write output
        writer = WriterFactory.get_writer(file_path, output_format)
        output_path = writer.write(translated_pages, file_path)

        if progress_callback:
            await progress_callback(100)

        return output_path

    async def _translate_large_document(
        self,
        pages: List[str],
        target_language: str,
        file_path: str,
        progress_callback: Callable[[int], Awaitable[None]] | None = None,
        output_format: str = "PDF",
    ) -> str:
        """
        Translate a large document using smart chunking with context preservation.

        This is triggered when document exceeds LARGE_DOC_THRESHOLD.
        Uses overlapping chunks and context-aware translation for better coherence.
        """
        from app.services.large_doc_translation import translate_large_document
        from app.core.logging import get_logger

        logger = get_logger("Orchestrator")

        # Combine all pages
        full_text = "\n\n".join(pages)

        logger.info(
            f"Large document detected ({len(full_text)} chars). "
            f"Using smart chunking with context preservation."
        )

        if progress_callback:
            await progress_callback(5)

        # Use context-aware translation for better coherence
        # Set use_context=True for better quality, False for faster processing
        translated_text = await translate_large_document(
            full_text,
            target_language,
            progress_callback=progress_callback,
            use_context=True  # Preserve coherence across chunks
        )

        # For now, treat the translated text as a single page for PDF writing
        # Future enhancement: preserve page boundaries
        translated_pages = [translated_text]

        if progress_callback:
            await progress_callback(98)

        # Write output
        writer = WriterFactory.get_writer(file_path, output_format)
        output_path = writer.write(translated_pages, file_path)

        if progress_callback:
            await progress_callback(100)

        logger.info("Large document translation complete")

        return output_path

    # -------------------------------------------------
    # Internal helpers
    # -------------------------------------------------

    async def _translate_chunk_with_progress(
        self,
        chunk_text: str,
        target_language: str,
        total_chunks: int,
        progress_callback: Callable[[int], Awaitable[None]] | None,
    ) -> str:
        async with self.semaphore:
            translated_text = await translation.translate_text(
                chunk_text, target_language
            )

        if progress_callback:
            async with self._progress_lock:
                self._completed_chunks += 1
                progress = int((self._completed_chunks / total_chunks) * 90)
                await progress_callback(progress)

        return translated_text


    async def _validate_and_retry_chunk(
        self,
        source_chunk: str,
        translated_chunks: List[str],
        target_language: str,
        idx: int,
    ) -> dict:
        """
        Validate a translated chunk and retry if quality is too low.

        Returns:
            Validation result dictionary with quality scores
        """
        result = await validation.validate_translation(
            source_chunk,
            translated_chunks[idx],
            target_language,
        )

        quality_score = result.get("quality_score", 0)
        recommendation = result.get("recommendation", "review")

        # Retry if quality is below acceptable threshold (score < 60)
        if quality_score < 60 or recommendation == "retranslate":
            print(
                f"⚠️  Chunk {idx} quality too low (score: {quality_score}). "
                f"Retrying translation..."
            )

            async with self.semaphore:
                new_translation = await translation.translate_text(
                    source_chunk, target_language
                )

            translated_chunks[idx] = new_translation

            # Validate retry
            retry_result = await validation.validate_translation(
                source_chunk,
                new_translation,
                target_language,
            )
            print(
                f"✓ Chunk {idx} retry complete. New score: {retry_result.get('quality_score', 'N/A')}"
            )
            return retry_result

        return result

    async def _validate_document(
        self,
        source_path: str,
        translated_path: str,
        target_language: str,
        progress_callback: Callable[[int], Awaitable[None]] | None = None,
    ) -> None:
        """
        Validate translated document by sampling text from both files.

        Args:
            source_path: Path to source document
            translated_path: Path to translated document
            target_language: Target language code
            progress_callback: Optional progress callback
        """
        from app.services.loader import LoaderFactory
        from app.core.logging import get_logger

        logger = get_logger("Orchestrator")

        try:
            # Extract text from both documents
            source_loader = LoaderFactory.get_loader(source_path)
            source_pages = source_loader.load(source_path)
            source_text = "\n\n".join(source_pages)

            translated_loader = LoaderFactory.get_loader(translated_path)
            translated_pages = translated_loader.load(translated_path)
            translated_text = "\n\n".join(translated_pages)

            # Chunk the text for validation
            from app.services import chunker
            source_chunks = chunker.chunk_text(source_text, max_chars=4000)
            translated_chunks = chunker.chunk_text(translated_text, max_chars=4000)

            # Sample chunks for validation (max 5 samples)
            import random
            num_chunks = min(len(source_chunks), len(translated_chunks))
            sample_size = min(5, num_chunks)

            if num_chunks == 0:
                logger.warning("No text extracted from documents for validation")
                return

            # Use same indices for both source and translated
            sample_indices = random.sample(range(num_chunks), sample_size) if num_chunks > sample_size else list(range(num_chunks))

            logger.info(f"Validating {sample_size} of {num_chunks} chunks from document")

            # Validate sampled chunks
            validation_results = []
            for idx in sample_indices:
                if idx < len(source_chunks) and idx < len(translated_chunks):
                    result = await validation.validate_translation(
                        source_chunks[idx],
                        translated_chunks[idx],
                        target_language,
                    )
                    validation_results.append(result)

            # Store results
            self.validation_results.extend(validation_results)

            # Log summary
            if validation_results:
                avg_quality = sum(v.get("quality_score", 0) for v in validation_results) / len(validation_results)
                logger.info(f"Document validation complete. Average quality: {avg_quality:.1f}")

        except Exception as e:
            logger.error(f"Document validation failed: {e}")
            # Don't fail the entire translation if validation fails
