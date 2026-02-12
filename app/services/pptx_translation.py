"""
PPTX Translation Service - Handles structured translation with formatting preservation
"""
import asyncio
from typing import Dict, Any, List, Callable, Awaitable
from app.services import translation


class PptxTranslationService:
    """
    Translates PPTX content while preserving structure and formatting.
    """

    def __init__(self, max_concurrency: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def translate_slides(
        self,
        slides_data: List[Dict[str, Any]],
        target_language: str,
        progress_callback: Callable[[int], Awaitable[None]] | None = None
    ) -> List[Dict[str, Any]]:
        """
        Translate all slides while preserving structure.

        Args:
            slides_data: List of slide dicts from PptxLoader
            target_language: Target language for translation
            progress_callback: Optional callback for progress updates

        Returns:
            List of slide dicts with translated text
        """
        # Collect all translatable text items
        text_items = []
        item_metadata = []  # Track where each text item belongs

        for slide_data in slides_data:
            for shape in slide_data['shapes']:
                items = self._collect_text_items(
                    shape,
                    slide_data['slide_index']
                )
                text_items.extend([item[0] for item in items])
                item_metadata.extend([item[1] for item in items])

        total_items = len(text_items)
        if total_items == 0:
            return slides_data

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
        translated_slides = []
        for slide_data in slides_data:
            translated_slide = {
                'slide_index': slide_data['slide_index'],
                'shapes': []
            }

            for shape in slide_data['shapes']:
                translated_shape = self._apply_translations(
                    shape,
                    slide_data['slide_index'],
                    translations_map
                )
                translated_slide['shapes'].append(translated_shape)

            translated_slides.append(translated_slide)

        if progress_callback:
            await progress_callback(100)

        return translated_slides

    def _collect_text_items(
        self,
        shape_data: Dict[str, Any],
        slide_idx: int,
        shape_path: List[int] = None
    ) -> List[tuple[str, Dict[str, Any]]]:
        """
        Recursively collect all translatable text items.

        Returns:
            List of (text, metadata) tuples
        """
        if shape_path is None:
            shape_path = []

        items = []
        shape_type = shape_data.get('type')
        current_path = shape_path + [shape_data['shape_index']]

        if shape_type == 'text':
            # Collect text from each run in each paragraph
            for para_idx, para in enumerate(shape_data.get('paragraphs', [])):
                for run_idx, run in enumerate(para.get('runs', [])):
                    text = run.get('text', '').strip()
                    if text:
                        metadata = {
                            'slide_idx': slide_idx,
                            'shape_path': current_path.copy(),
                            'para_idx': para_idx,
                            'run_idx': run_idx,
                            'type': 'run'
                        }
                        items.append((text, metadata))

        elif shape_type == 'table':
            # Collect text from each table cell
            table_data = shape_data.get('table_data', {})
            for row_idx, row in enumerate(table_data.get('rows', [])):
                for col_idx, cell in enumerate(row):
                    text = cell.get('text', '').strip()
                    if text:
                        metadata = {
                            'slide_idx': slide_idx,
                            'shape_path': current_path.copy(),
                            'row_idx': row_idx,
                            'col_idx': col_idx,
                            'type': 'table_cell'
                        }
                        items.append((text, metadata))

        elif shape_type == 'group':
            # Recursively collect from grouped shapes
            for sub_shape in shape_data.get('shapes', []):
                sub_items = self._collect_text_items(
                    sub_shape,
                    slide_idx,
                    current_path
                )
                items.extend(sub_items)

        return items

    def _apply_translations(
        self,
        shape_data: Dict[str, Any],
        slide_idx: int,
        translations_map: Dict[str, str],
        shape_path: List[int] = None
    ) -> Dict[str, Any]:
        """Apply translations back to the structure."""
        if shape_path is None:
            shape_path = []

        # Create a copy of the shape data
        translated_shape = shape_data.copy()
        shape_type = shape_data.get('type')
        current_path = shape_path + [shape_data['shape_index']]

        if shape_type == 'text':
            # Apply translations to runs
            translated_paragraphs = []
            for para_idx, para in enumerate(shape_data.get('paragraphs', [])):
                translated_para = para.copy()
                translated_runs = []

                for run_idx, run in enumerate(para.get('runs', [])):
                    translated_run = run.copy()
                    metadata = {
                        'slide_idx': slide_idx,
                        'shape_path': current_path.copy(),
                        'para_idx': para_idx,
                        'run_idx': run_idx,
                        'type': 'run'
                    }
                    key = self._make_key(metadata)

                    if key in translations_map:
                        translated_run['text'] = translations_map[key]

                    translated_runs.append(translated_run)

                translated_para['runs'] = translated_runs
                # Update paragraph text as well
                translated_para['text'] = ''.join(r['text'] for r in translated_runs)
                translated_paragraphs.append(translated_para)

            translated_shape['paragraphs'] = translated_paragraphs

        elif shape_type == 'table':
            # Apply translations to table cells
            table_data = shape_data.get('table_data', {})
            translated_rows = []

            for row_idx, row in enumerate(table_data.get('rows', [])):
                translated_row = []
                for col_idx, cell in enumerate(row):
                    translated_cell = cell.copy()
                    metadata = {
                        'slide_idx': slide_idx,
                        'shape_path': current_path.copy(),
                        'row_idx': row_idx,
                        'col_idx': col_idx,
                        'type': 'table_cell'
                    }
                    key = self._make_key(metadata)

                    if key in translations_map:
                        translated_cell['text'] = translations_map[key]

                    translated_row.append(translated_cell)

                translated_rows.append(translated_row)

            translated_table_data = table_data.copy()
            translated_table_data['rows'] = translated_rows
            translated_shape['table_data'] = translated_table_data

        elif shape_type == 'group':
            # Recursively translate grouped shapes
            translated_sub_shapes = []
            for sub_shape in shape_data.get('shapes', []):
                translated_sub = self._apply_translations(
                    sub_shape,
                    slide_idx,
                    translations_map,
                    current_path
                )
                translated_sub_shapes.append(translated_sub)

            translated_shape['shapes'] = translated_sub_shapes

        return translated_shape

    def _make_key(self, metadata: Dict[str, Any]) -> str:
        """Create a unique key for a text item."""
        if metadata['type'] == 'run':
            return (
                f"slide_{metadata['slide_idx']}_"
                f"shape_{'_'.join(map(str, metadata['shape_path']))}_"
                f"para_{metadata['para_idx']}_"
                f"run_{metadata['run_idx']}"
            )
        elif metadata['type'] == 'table_cell':
            return (
                f"slide_{metadata['slide_idx']}_"
                f"shape_{'_'.join(map(str, metadata['shape_path']))}_"
                f"cell_{metadata['row_idx']}_{metadata['col_idx']}"
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
                progress = int((index + 1) / total * 90)  # 0-90%
                await progress_callback(progress)

            return translated
