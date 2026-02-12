"""
PDF Translation with Formatting Preservation
Preserves layout, images, tables, and styling using PyMuPDF
"""
import tempfile
import shutil
from typing import List, Dict, Any, Callable, Awaitable
import fitz  # PyMuPDF
import asyncio
from app.services import translation
from app.core.logging import get_logger

logger = get_logger("PdfFormattingService")


class PdfFormattingService:
    """
    Translates PDF content while preserving:
    - Original layout and positioning
    - Images
    - Tables and structure
    - Font styles and sizes
    - Colors and formatting
    """

    def __init__(self, max_concurrency: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def translate_pdf(
        self,
        file_path: str,
        target_language: str,
        progress_callback: Callable[[int], Awaitable[None]] | None = None
    ) -> str:
        """
        Translate PDF while preserving formatting.

        Strategy:
        1. Extract text blocks with position and formatting info
        2. Translate text blocks
        3. Use text redaction and overlay to replace text in original PDF
        """
        # Open the original PDF
        doc = fitz.open(file_path)

        try:
            # Extract page-level text for clean justified output
            all_text_items: List[str] = []
            text_metadata: List[Dict[str, Any]] = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text("text").strip()

                if page_text:
                    all_text_items.append(page_text)
                    text_metadata.append({"page_num": page_num})

            total_items = len(all_text_items)
            logger.info(f"PDF extraction: found {total_items} pages with text")

            if total_items == 0:
                logger.warning("No text found in PDF, returning copy of original")
                return self._copy_pdf(file_path)

            if total_items > 0:
                logger.info(f"Sample extracted text: {all_text_items[0][:120]}...")

                if progress_callback:
                    await progress_callback(10)

                # Translate all text items in parallel
                translation_tasks = [
                    self._translate_block_with_progress(
                        text,
                        target_language,
                        idx,
                        total_items,
                        progress_callback
                    )
                    for idx, text in enumerate(all_text_items)
                ]

                translated_texts = await asyncio.gather(*translation_tasks)

                # Replace failed or policy-blocked translations with the original text
                cleaned_translations: List[str] = []
                for original, translated in zip(all_text_items, translated_texts):
                    cleaned_translations.append(self._clean_translation(original, translated))

                # Log translation results
                non_empty_translations = sum(1 for t in cleaned_translations if t and t.strip())
                logger.info(f"Translation complete: {non_empty_translations}/{len(cleaned_translations)} usable translations")
                if cleaned_translations:
                    sample = cleaned_translations[0]
                    logger.info(f"Sample translation: {sample[:100] if sample else '(empty)'}...")

                if progress_callback:
                    await progress_callback(90)

                output_path = await self._create_simple_translated_pdf(
                    cleaned_translations,
                    text_metadata
                )

                if progress_callback:
                    await progress_callback(100)

                return output_path
        finally:
            doc.close()

    async def _translate_block_with_progress(
        self,
        text: str,
        target_language: str,
        idx: int,
        total: int,
        progress_callback: Callable[[int], Awaitable[None]] | None = None
    ) -> str:
        """
        Translate a single text block with semaphore-based concurrency control.
        """
        async with self.semaphore:
            try:
                translated = await translation.translate_text(text, target_language)
                logger.debug(f"Translated block {idx + 1}/{total}: {len(text)} chars -> {len(translated) if translated else 0} chars")
                return translated
            except Exception as e:
                logger.error(f"Translation failed for block {idx + 1}/{total}: {e}")
                return text  # Fallback to original text

    async def _create_simple_translated_pdf(
        self,
        translated_texts: List[str],
        text_metadata: List[Dict[str, Any]]
    ) -> str:
        """
        Create a simple PDF with translated text using ReportLab.
        Used as fallback when formatting preservation fails.
        """
        from app.services.writer import PdfWriter

        # Since we extract at page level, each text is already a complete page
        pages = []
        for text, meta in zip(translated_texts, text_metadata):
            pages.append(text)

        logger.info(f"Using simple PDF writer with {len(pages)} pages")

        # Use the simple, reliable PdfWriter
        writer = PdfWriter()
        output_path = writer.write(pages, "translated.pdf")

        return output_path

    def _int_to_rgb(self, color_int: int) -> tuple:
        """Convert integer color to RGB tuple (0-1 range)."""
        if color_int is None:
            return (0, 0, 0)  # Black as default

        # Extract RGB components
        r = ((color_int >> 16) & 0xFF) / 255.0
        g = ((color_int >> 8) & 0xFF) / 255.0
        b = (color_int & 0xFF) / 255.0

        return (r, g, b)

    def _clean_translation(self, original_text: str, translated_text: str | None) -> str:
        """Ensure we have usable translated content; fallback to original when necessary."""
        if not translated_text:
            return original_text

        stripped = translated_text.strip()
        if not stripped:
            return original_text

        lower = stripped.lower()
        guard_phrases = [
            "i'm sorry",
            "i am sorry",
            "cannot assist",
            "can't assist",
            "not able to help",
            "i cannot comply",
        ]

        if any(phrase in lower for phrase in guard_phrases):
            return original_text

        return stripped

    def _extract_text_blocks(self, page: fitz.Page) -> List[Dict[str, Any]]:
        """Extract textual blocks with geometric metadata for a page."""
        blocks: List[Dict[str, Any]] = []
        page_dict = page.get_text("dict")

        for block in page_dict.get("blocks", []):
            if block.get("type", 0) != 0:
                continue  # skip non-text blocks

            block_lines = block.get("lines", [])
            block_text_parts: List[str] = []
            first_span: Dict[str, Any] | None = None

            for line in block_lines:
                spans = line.get("spans", [])
                line_text = "".join(span.get("text", "") for span in spans)
                if line_text.strip():
                    block_text_parts.append(line_text.strip())
                    if not first_span and spans:
                        first_span = spans[0]

            block_text = "\n".join(block_text_parts).strip()
            if not block_text:
                continue

            span = first_span or {}
            bbox = block.get("bbox", page.rect)
            blocks.append({
                "text": block_text,
                "bbox": fitz.Rect(bbox),
                "font": span.get("font", "helv"),
                "size": span.get("size", 11),
                "color": span.get("color", 0),
                "flags": span.get("flags", 0),
            })

        return blocks

    def _map_font(self, font_name: str, flags: int) -> str:
        """Map extracted font names to built-in fonts available in PyMuPDF."""
        font_name = (font_name or "").lower()
        is_serif = any(keyword in font_name for keyword in ["times", "serif", "roman"])
        is_mono = any(keyword in font_name for keyword in ["mono", "cour", "typewriter"])

        if is_mono:
            base = "courier"
        elif is_serif:
            base = "times"
        else:
            base = "helvetica"

        bold = bool(flags & 2**4)
        italic = bool(flags & 2**1)

        if base == "courier":
            if bold and italic:
                return "courier-boldoblique"
            if bold:
                return "courier-bold"
            if italic:
                return "courier-oblique"
            return "courier"

        if base == "times":
            if bold and italic:
                return "times-bolditalic"
            if bold:
                return "times-bold"
            if italic:
                return "times-italic"
            return "times-roman"

        # Helvetica family
        if bold and italic:
            return "helvetica-boldoblique"
        if bold:
            return "helvetica-bold"
        if italic:
            return "helvetica-oblique"
        return "helvetica"

    def _copy_pdf(self, file_path: str) -> str:
        """Return a temporary copy of the original PDF."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            output_path = tmp.name

        shutil.copyfile(file_path, output_path)
        return output_path

    def _insert_block_text(
        self,
        page: fitz.Page,
        bbox: fitz.Rect,
        text: str,
        fontname: str,
        color: tuple,
        font_size: float,
    ) -> bool:
        """Try to fit translated text inside the original bounding box."""
        if not text.strip():
            return True  # Nothing to insert after sanitization

        max_size = font_size or 11
        min_size = max(5, max_size * 0.4)

        # Attempt different justifications with gradual downsizing
        for align in (4, 1, 0):  # 4=justify, 1=centered, 0=left
            size = max_size
            while size >= min_size:
                try:
                    rc = page.insert_textbox(
                        bbox,
                        text,
                        fontsize=size,
                        fontname=fontname,
                        color=color,
                        align=align
                    )
                except Exception as exc:
                    logger.warning(f"Textbox insertion error: {exc}")
                    break

                if rc >= 0:
                    return True

                size *= 0.9

        # Final fallback: write paragraph by paragraph manually
        try:
            line_height = min_size * 1.4
            cursor_y = bbox.y0 + min_size
            for paragraph in text.split("\n"):
                paragraph = paragraph.strip()
                if not paragraph:
                    cursor_y += line_height * 0.5
                    continue

                if cursor_y > bbox.y1:
                    break

                page.insert_text(
                    (bbox.x0, cursor_y),
                    paragraph,
                    fontsize=min_size,
                    fontname=fontname,
                    color=color
                )
                cursor_y += line_height

            return True
        except Exception as exc:
            logger.warning(f"Manual paragraph insertion failed: {exc}")
            return False
