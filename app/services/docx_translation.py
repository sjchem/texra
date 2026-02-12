"""
DOCX Translation Service - Handles structured translation with formatting preservation
"""
import asyncio
from typing import Dict, Any, List, Callable, Awaitable
from app.services import translation


class DocxTranslationService:
    """
    Translates DOCX content while preserving structure and formatting.
    """

    def __init__(self, max_concurrency: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def translate_document(
        self,
        document_data: Dict[str, Any],
        target_language: str,
        progress_callback: Callable[[int], Awaitable[None]] | None = None
    ) -> Dict[str, Any]:
        """
        Translate all document elements while preserving structure.

        Args:
            document_data: Dict from DocxLoader
            target_language: Target language for translation
            progress_callback: Optional callback for progress updates

        Returns:
            Dict with translated elements
        """
        # Collect all translatable text items
        text_items = []
        item_metadata = []

        elements = document_data.get('elements', [])

        for elem_idx, element in enumerate(elements):
            items = self._collect_text_items(element, elem_idx)
            text_items.extend([item[0] for item in items])
            item_metadata.extend([item[1] for item in items])

        total_items = len(text_items)
        if total_items == 0:
            return document_data

        if progress_callback:
            await progress_callback(10)

        # Translate all text items in parallel
        translation_tasks = [
            self._translate_text_with_progress(
                text,
                target_language,
                idx,
                total_items,
                progress_callback
            )
            for idx, text in enumerate(text_items)
        ]

        translated_texts = await asyncio.gather(*translation_tasks)

        # Build a mapping of translations
        translations_map = {}
        for metadata, translated in zip(item_metadata, translated_texts):
            key = self._make_key(metadata)
            translations_map[key] = translated

        # Apply translations back to the structure
        translated_elements = []
        for elem_idx, element in enumerate(elements):
            translated_element = self._apply_translations(
                element,
                elem_idx,
                translations_map
            )
            translated_elements.append(translated_element)

        if progress_callback:
            await progress_callback(100)

        return {
            'elements': translated_elements,
            'has_images': document_data.get('has_images', False)
        }

    def _collect_text_items(
        self,
        element: Dict[str, Any],
        elem_idx: int
    ) -> List[tuple[str, Dict[str, Any]]]:
        """
        Collect all translatable text items from an element.

        Returns:
            List of (text, metadata) tuples
        """
        items = []
        element_type = element.get('type')

        if element_type == 'paragraph':
            # Collect text from each run
            for run_idx, run in enumerate(element.get('runs', [])):
                text = run.get('text', '').strip()
                if text:
                    metadata = {
                        'elem_idx': elem_idx,
                        'elem_type': 'paragraph',
                        'run_idx': run_idx,
                    }
                    items.append((text, metadata))

        elif element_type == 'table':
            # Collect text from each table cell
            for row_idx, row in enumerate(element.get('rows', [])):
                for col_idx, cell in enumerate(row):
                    for para_idx, para in enumerate(cell.get('paragraphs', [])):
                        for run_idx, run in enumerate(para.get('runs', [])):
                            text = run.get('text', '').strip()
                            if text:
                                metadata = {
                                    'elem_idx': elem_idx,
                                    'elem_type': 'table',
                                    'row_idx': row_idx,
                                    'col_idx': col_idx,
                                    'para_idx': para_idx,
                                    'run_idx': run_idx,
                                }
                                items.append((text, metadata))

        return items

    def _apply_translations(
        self,
        element: Dict[str, Any],
        elem_idx: int,
        translations_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """Apply translations back to the element structure."""
        element_type = element.get('type')
        translated_element = element.copy()

        if element_type == 'paragraph':
            # Apply translations to runs
            translated_runs = []
            for run_idx, run in enumerate(element.get('runs', [])):
                translated_run = run.copy()
                metadata = {
                    'elem_idx': elem_idx,
                    'elem_type': 'paragraph',
                    'run_idx': run_idx,
                }
                key = self._make_key(metadata)

                if key in translations_map:
                    translated_run['text'] = translations_map[key]

                translated_runs.append(translated_run)

            translated_element['runs'] = translated_runs
            # Update paragraph text as well
            translated_element['text'] = ''.join(r['text'] for r in translated_runs)

        elif element_type == 'table':
            # Apply translations to table cells
            translated_rows = []

            for row_idx, row in enumerate(element.get('rows', [])):
                translated_row = []

                for col_idx, cell in enumerate(row):
                    translated_cell = cell.copy()
                    translated_paragraphs = []

                    for para_idx, para in enumerate(cell.get('paragraphs', [])):
                        translated_para = para.copy()
                        translated_runs = []

                        for run_idx, run in enumerate(para.get('runs', [])):
                            translated_run = run.copy()
                            metadata = {
                                'elem_idx': elem_idx,
                                'elem_type': 'table',
                                'row_idx': row_idx,
                                'col_idx': col_idx,
                                'para_idx': para_idx,
                                'run_idx': run_idx,
                            }
                            key = self._make_key(metadata)

                            if key in translations_map:
                                translated_run['text'] = translations_map[key]

                            translated_runs.append(translated_run)

                        translated_para['runs'] = translated_runs
                        translated_para['text'] = ''.join(r['text'] for r in translated_runs)
                        translated_paragraphs.append(translated_para)

                    translated_cell['paragraphs'] = translated_paragraphs
                    # Update combined cell text
                    translated_cell['text'] = '\n'.join(p['text'] for p in translated_paragraphs)
                    translated_row.append(translated_cell)

                translated_rows.append(translated_row)

            translated_element['rows'] = translated_rows

        return translated_element

    def _make_key(self, metadata: Dict[str, Any]) -> str:
        """Create a unique key for a text item."""
        if metadata['elem_type'] == 'paragraph':
            return f"elem_{metadata['elem_idx']}_run_{metadata['run_idx']}"
        elif metadata['elem_type'] == 'table':
            return (
                f"elem_{metadata['elem_idx']}_"
                f"cell_{metadata['row_idx']}_{metadata['col_idx']}_"
                f"para_{metadata['para_idx']}_run_{metadata['run_idx']}"
            )
        return ""

    async def _translate_text_with_progress(
        self,
        text: str,
        target_language: str,
        index: int,
        total: int,
        progress_callback: Callable[[int], Awaitable[None]] | None
    ) -> str:
        """Translate a single text item with progress tracking."""
        async with self.semaphore:
            translated = await translation.translate_text(text, target_language)

            if progress_callback:
                progress = 10 + int((index + 1) / total * 85)
                await progress_callback(progress)

            return translated
