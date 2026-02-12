"""
OCR Service - Extract text from images and scanned PDFs
Uses OpenAI Vision API for high-quality text extraction
"""
import base64
import fitz  # PyMuPDF
from typing import List, Optional
from openai import OpenAI
import os
from app.core.logging import get_logger

logger = get_logger("OCRService")


class OCRService:
    """
    Extract text from images and scanned PDFs using OpenAI Vision API.

    Supports:
    - Image files (PNG, JPG, JPEG, WEBP)
    - Scanned PDFs (image-based PDFs)
    - Mixed PDFs (detect scanned pages)
    """

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def is_pdf_scanned(self, pdf_path: str) -> bool:
        """
        Detect if a PDF is scanned (image-based) or has extractable text.

        Returns True if the PDF appears to be scanned (no/minimal text).
        """
        try:
            doc = fitz.open(pdf_path)

            # Check first few pages
            pages_to_check = min(3, len(doc))
            text_chars = 0

            for page_num in range(pages_to_check):
                page = doc[page_num]
                text = page.get_text().strip()
                text_chars += len(text)

            doc.close()

            # If very little text found, likely a scanned PDF
            # Threshold: < 50 characters per checked page suggests scanned
            avg_chars_per_page = text_chars / pages_to_check if pages_to_check > 0 else 0

            is_scanned = avg_chars_per_page < 50

            if is_scanned:
                logger.info(f"PDF detected as scanned (avg {avg_chars_per_page:.1f} chars/page)")

            return is_scanned

        except Exception as e:
            logger.error(f"Error checking if PDF is scanned: {e}")
            return False

    def extract_text_from_image(self, image_path: str) -> str:
        """
        Extract text from an image file using OpenAI Vision API.

        Args:
            image_path: Path to image file (PNG, JPG, etc.)

        Returns:
            Extracted text
        """
        try:
            # Read and encode image
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')

            # Determine image type from extension
            ext = image_path.lower().split('.')[-1]
            mime_type = f"image/{ext}" if ext in ['png', 'jpg', 'jpeg', 'webp', 'gif'] else "image/png"

            # Use Vision API to extract text
            response = self.client.chat.completions.create(
                model="gpt-4o",  # or gpt-4-vision-preview
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Extract ALL text from this image. "
                                    "Preserve the original formatting, structure, and layout as much as possible. "
                                    "Return only the extracted text, nothing else. "
                                    "If there are tables, preserve their structure. "
                                    "If there are multiple columns, indicate them clearly."
                                )
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=4096
            )

            extracted_text = response.choices[0].message.content

            logger.info(f"Extracted {len(extracted_text)} characters from image")

            return extracted_text

        except Exception as e:
            logger.error(f"Error extracting text from image: {e}")
            raise

    def extract_text_from_scanned_pdf(self, pdf_path: str) -> List[str]:
        """
        Extract text from a scanned PDF by converting pages to images
        and using OCR.

        Args:
            pdf_path: Path to scanned PDF file

        Returns:
            List of extracted text (one per page)
        """
        try:
            doc = fitz.open(pdf_path)
            pages_text = []

            logger.info(f"Processing scanned PDF: {len(doc)} pages")

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Convert page to image
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality

                # Convert to PNG bytes
                img_bytes = pix.tobytes("png")

                # Encode to base64
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')

                # Extract text using Vision API
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "Extract ALL text from this PDF page image. "
                                        "Preserve the original formatting, structure, and layout. "
                                        "Return only the extracted text, nothing else. "
                                        "If there are tables, preserve their structure."
                                    )
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{img_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=4096
                )

                page_text = response.choices[0].message.content
                pages_text.append(page_text)

                logger.info(f"Extracted {len(page_text)} chars from page {page_num + 1}")

            doc.close()

            return pages_text

        except Exception as e:
            logger.error(f"Error extracting text from scanned PDF: {e}")
            raise

    def extract_text(self, file_path: str) -> List[str]:
        """
        Smart text extraction that handles both images and PDFs.

        Args:
            file_path: Path to file (image or PDF)

        Returns:
            List of extracted text (pages for PDF, single item for images)
        """
        file_lower = file_path.lower()

        # Handle image files
        if any(file_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']):
            text = self.extract_text_from_image(file_path)
            return [text]

        # Handle PDFs
        elif file_lower.endswith('.pdf'):
            # Check if scanned
            if self.is_pdf_scanned(file_path):
                return self.extract_text_from_scanned_pdf(file_path)
            else:
                # Not scanned, use regular text extraction
                # Return None to indicate regular PDF processing should be used
                return None

        else:
            raise ValueError(f"Unsupported file type for OCR: {file_path}")


# Singleton instance
_ocr_service = None

def get_ocr_service() -> OCRService:
    """Get or create OCR service singleton."""
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service
