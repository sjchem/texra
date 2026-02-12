"""
DOCX Loader - Preserves document structure, formatting, and metadata
"""
from typing import List, Dict, Any
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.table import Table
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.text.paragraph import Paragraph


class DocxLoader:
    """
    Loads DOCX files and extracts content while preserving:
    - Paragraph formatting and styles
    - Text runs with formatting (bold, italic, font, size)
    - Tables with structure
    - Images (metadata)
    - Lists and numbering
    """

    def load(self, file_path: str) -> Dict[str, Any]:
        """
        Load DOCX and extract structured content.

        Returns:
            Dict containing:
            - elements: List of document elements (paragraphs, tables)
            - metadata: Document metadata
        """
        doc = Document(file_path)

        elements = []

        # Process all body elements (paragraphs and tables)
        for element in doc.element.body:
            if isinstance(element, CT_P):
                # Paragraph
                paragraph = Paragraph(element, doc)
                para_data = self._extract_paragraph_data(paragraph)
                if para_data:
                    elements.append(para_data)
            elif isinstance(element, CT_Tbl):
                # Table
                table = Table(element, doc)
                table_data = self._extract_table_data(table)
                if table_data:
                    elements.append(table_data)

        return {
            'elements': elements,
            'has_images': self._has_images(doc)
        }

    def _extract_paragraph_data(self, paragraph: Paragraph) -> Dict[str, Any] | None:
        """Extract paragraph with formatting metadata."""
        # Skip empty paragraphs
        if not paragraph.text.strip():
            return None

        para_data = {
            'type': 'paragraph',
            'text': paragraph.text,
            'style': paragraph.style.name if paragraph.style else None,
            'alignment': paragraph.alignment,
            'runs': []
        }

        # Extract run-level formatting
        for run in paragraph.runs:
            run_data = {
                'text': run.text,
                'bold': run.bold,
                'italic': run.italic,
                'underline': run.underline,
                'font_name': run.font.name,
                'font_size': run.font.size.pt if run.font.size else None,
                'font_color': self._get_color(run.font.color) if run.font.color else None,
            }
            para_data['runs'].append(run_data)

        return para_data

    def _extract_table_data(self, table: Table) -> Dict[str, Any]:
        """Extract table content with structure."""
        rows_data = []

        for row in table.rows:
            cells_data = []
            for cell in row.cells:
                # Extract text from all paragraphs in the cell
                cell_paragraphs = []
                for para in cell.paragraphs:
                    para_data = self._extract_paragraph_data(para)
                    if para_data:
                        cell_paragraphs.append(para_data)

                cells_data.append({
                    'paragraphs': cell_paragraphs,
                    'text': cell.text  # Combined text for convenience
                })

            rows_data.append(cells_data)

        return {
            'type': 'table',
            'rows': rows_data,
            'num_rows': len(table.rows),
            'num_cols': len(table.columns) if table.rows else 0
        }

    def _get_color(self, color_obj) -> str | None:
        """Extract color from font color object."""
        try:
            if hasattr(color_obj, 'rgb') and color_obj.rgb:
                return str(color_obj.rgb)
        except:
            pass
        return None

    def _has_images(self, doc: Document) -> bool:
        """Check if document contains images."""
        try:
            return len(doc.inline_shapes) > 0
        except:
            return False
