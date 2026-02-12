
from abc import ABC, abstractmethod
import fitz  # PyMuPDF

class Loader(ABC):
    @abstractmethod
    def load(self, file_path: str) -> list[str]:
        pass

class PdfLoader(Loader):
    def load(self, file_path: str) -> list[str]:
        doc = fitz.open(file_path)
        pages = []
        for page in doc:
            pages.append(page.get_text())
        return pages

class DocxLoader(Loader):
    def load(self, file_path: str) -> list[str]:
        try:
            from docx import Document
        except ImportError:
            raise ImportError("python-docx is required for DOCX files. Install it with: pip install python-docx")

        doc = Document(file_path)
        # Extract all paragraphs as a single page
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return [text] if text else [""]

class OdtLoader(Loader):
    def load(self, file_path: str) -> list[str]:
        try:
            from odf import text as odf_text
            from odf.opendocument import load as odf_load
        except ImportError:
            raise ImportError("odfpy is required for ODT files. Install it with: pip install odfpy")

        doc = odf_load(file_path)
        paragraphs = doc.getElementsByType(odf_text.P)
        text = "\n".join([str(p) for p in paragraphs])
        # Clean up XML tags
        import re
        text = re.sub(r'<[^>]+>', '', text)
        return [text] if text else [""]

class TextLoader(Loader):
    def load(self, file_path: str) -> list[str]:
        with open(file_path, "r", encoding="utf-8") as f:
            # For a text file, we can consider the entire file as a single page
            return [f.read()]

class PptxLoader(Loader):
    def load(self, file_path: str) -> list[str]:
        # Import the specialized PPTX loader
        from app.services.pptx_loader import PptxLoader as StructuredPptxLoader

        # For compatibility with text-based flow, extract all text
        # Note: This is a fallback - the orchestrator should use the structured loader directly
        loader = StructuredPptxLoader()
        slides_data = loader.load(file_path)

        # Flatten to text pages
        pages = []
        for slide_data in slides_data:
            slide_text = []
            for shape in slide_data.get('shapes', []):
                slide_text.append(self._extract_text_from_shape(shape))
            pages.append('\n'.join(slide_text))

        return pages

    def _extract_text_from_shape(self, shape_data: dict) -> str:
        """Extract plain text from shape (recursive for groups)."""
        shape_type = shape_data.get('type')

        if shape_type == 'text':
            paragraphs = shape_data.get('paragraphs', [])
            return '\n'.join(p.get('text', '') for p in paragraphs)
        elif shape_type == 'table':
            table_data = shape_data.get('table_data', {})
            rows = table_data.get('rows', [])
            return '\n'.join(
                '\t'.join(cell.get('text', '') for cell in row)
                for row in rows
            )
        elif shape_type == 'group':
            sub_shapes = shape_data.get('shapes', [])
            return '\n'.join(self._extract_text_from_shape(s) for s in sub_shapes)

        return ''


class ImageLoader(Loader):
    """Load images and scanned PDFs using OCR."""
    def load(self, file_path: str) -> list[str]:
        from app.services.ocr import get_ocr_service

        ocr_service = get_ocr_service()

        # OCR service returns list of pages
        pages = ocr_service.extract_text(file_path)

        # If it's a regular PDF (not scanned), OCR returns None
        if pages is None:
            # Fall back to regular PDF loading
            return PdfLoader().load(file_path)

        return pages


class LoaderFactory:
    @staticmethod
    def get_loader(file_path: str) -> Loader:
        file_path_lower = file_path.lower()

        # Check for image files first
        if any(file_path_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']):
            return ImageLoader()
        elif file_path_lower.endswith(".pdf"):
            # Check if it's a scanned PDF
            from app.services.ocr import get_ocr_service
            ocr_service = get_ocr_service()
            if ocr_service.is_pdf_scanned(file_path):
                return ImageLoader()
            else:
                return PdfLoader()
        elif file_path_lower.endswith(".docx"):
            return DocxLoader()
        elif file_path_lower.endswith(".odt"):
            return OdtLoader()
        elif file_path_lower.endswith(".txt"):
            return TextLoader()
        elif file_path_lower.endswith(".pptx"):
            return PptxLoader()
        else:
            raise ValueError(f"Unsupported file type: {file_path}. Supported formats: PDF, DOCX, ODT, TXT, PPTX, PNG, JPG, JPEG, WEBP, GIF")
