"""
STARK TRANSLATOR - MCP Server

Model Context Protocol server enabling AI assistants (like Cursor, Claude Desktop)
to translate documents using STARK's translation engine.

Usage in Cursor/Claude Desktop:
1. Add this server to your MCP configuration
2. Use tools like "translate_document" or "translate_text"
3. Get instant translations with quality validation

Supported formats: PDF, DOCX, PPTX, TXT, Images (OCR), ODT
"""
import os
import tempfile
import json
from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP
from app.orchestrator import TranslationOrchestrator
from app.core.logging import get_logger

logger = get_logger("MCPServer")

mcp = FastMCP(
    "stark-translator",
    description="Professional document translation service powered by STARK AI"
)


# =================================================
# RESOURCES - Static information about the service
# =================================================

@mcp.resource("stark://supported-languages")
def get_supported_languages() -> str:
    """
    Get list of supported languages for translation.

    Returns:
        JSON string with supported languages and their codes
    """
    languages = {
        "major_languages": [
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
            {"code": "it", "name": "Italian"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "ru", "name": "Russian"},
            {"code": "zh", "name": "Chinese"},
            {"code": "ja", "name": "Japanese"},
            {"code": "ko", "name": "Korean"},
            {"code": "ar", "name": "Arabic"},
            {"code": "hi", "name": "Hindi"},
            {"code": "nl", "name": "Dutch"},
            {"code": "pl", "name": "Polish"},
            {"code": "tr", "name": "Turkish"},
        ],
        "supported_formats": [
            "PDF (.pdf)",
            "Word (.docx)",
            "PowerPoint (.pptx)",
            "Text (.txt)",
            "OpenDocument (.odt)",
            "Images (.png, .jpg, .jpeg, .webp) - with OCR"
        ],
        "features": [
            "Format preservation",
            "Quality validation",
            "Large document support (up to 200MB)",
            "Parallel processing for speed",
            "Auto-retry on errors"
        ]
    }
    return json.dumps(languages, indent=2)


@mcp.resource("stark://service-info")
def get_service_info() -> str:
    """
    Get information about STARK Translator service capabilities.

    Returns:
        JSON string with service information
    """
    info = {
        "service": "STARK Translator",
        "version": "1.0.0",
        "description": "AI-powered document translation with formatting preservation",
        "capabilities": {
            "max_file_size": "200MB",
            "max_pages": "200 pages",
            "concurrent_translations": 5,
            "quality_validation": True,
            "format_preservation": True,
            "ocr_support": True
        },
        "performance": {
            "avg_translation_time": "5-30 seconds for standard documents",
            "large_document_time": "1-5 minutes for 50+ pages",
            "concurrent_processing": "Parallel chunk translation for speed"
        }
    }
    return json.dumps(info, indent=2)


# =================================================
# TOOLS - Translation capabilities
# =================================================

@mcp.tool()
async def translate_document(
    file_bytes: bytes,
    target_language: str,
    filename: str = "document.pdf",
    enable_validation: bool = True,
    output_format: Optional[str] = None
) -> Dict[str, Any]:
    """
    Translate any supported document format with quality validation.

    Supports: PDF, DOCX, PPTX, TXT, ODT, Images (with OCR)
    Preserves formatting, styles, images, and layout.

    Args:
        file_bytes: The document file content as bytes
        target_language: Target language (e.g., 'Spanish', 'French', 'German', 'Chinese')
        filename: Original filename including extension (e.g., 'report.pdf', 'presentation.pptx')
        enable_validation: Enable AI quality validation (default: True)
        output_format: Force output format - 'PDF', 'DOCX', or 'PPTX' (default: same as input)

    Returns:
        Dictionary containing:
        - translated_bytes: The translated document as bytes
        - validation_summary: Quality validation results (if enabled)
        - original_filename: Input filename
        - output_filename: Output filename
        - file_size_kb: Size of translated file in KB

    Example:
        result = await translate_document(
            file_bytes=pdf_content,
            target_language="Spanish",
            filename="contract.pdf"
        )
        # Access: result['translated_bytes'], result['validation_summary']
    """
    logger.info(f"MCP translate_document: {filename} → {target_language}")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Write input bytes to temporary file
            input_path = os.path.join(tmpdir, filename)
            with open(input_path, "wb") as f:
                f.write(file_bytes)

            # Determine output format
            if output_format is None:
                # Default: keep same format
                if filename.lower().endswith('.docx'):
                    output_format = 'DOCX'
                elif filename.lower().endswith('.pptx'):
                    output_format = 'PPTX'
                else:
                    output_format = 'PDF'

            # Translate using orchestrator
            orchestrator = TranslationOrchestrator()
            output_path = await orchestrator.translate(
                input_path,
                target_language,
                output_format=output_format,
                enable_validation=enable_validation
            )

            # Get validation summary
            validation_summary = orchestrator.get_validation_summary()

            # Read translated file
            with open(output_path, "rb") as f:
                translated_bytes = f.read()

            # Generate output filename
            base_name = os.path.splitext(filename)[0]
            ext_map = {"PDF": "pdf", "DOCX": "docx", "PPTX": "pptx"}
            ext = ext_map.get(output_format, "pdf")
            output_filename = f"translated_{base_name}.{ext}"

            logger.info(
                f"MCP translation complete: {len(translated_bytes)/1024:.1f}KB, "
                f"Quality: {validation_summary.get('average_quality_score', 'N/A')}"
            )

            return {
                "translated_bytes": translated_bytes,
                "validation_summary": validation_summary,
                "original_filename": filename,
                "output_filename": output_filename,
                "file_size_kb": round(len(translated_bytes) / 1024, 1),
                "target_language": target_language,
                "output_format": output_format
            }

        except Exception as e:
            logger.error(f"MCP translation failed: {e}")
            return {
                "error": str(e),
                "original_filename": filename,
                "target_language": target_language,
                "success": False
            }


@mcp.tool()
async def translate_text(
    text: str,
    target_language: str,
    source_language: str = "auto"
) -> Dict[str, str]:
    """
    Translate plain text without file handling.

    Fast and simple text-only translation for snippets, paragraphs, or documents.

    Args:
        text: The text to translate
        target_language: Target language (e.g., 'Spanish', 'French', 'German')
        source_language: Source language (default: 'auto' for auto-detection)

    Returns:
        Dictionary with translated_text and metadata

    Example:
        result = await translate_text(
            text="Hello, how are you?",
            target_language="Spanish"
        )
        # Access: result['translated_text']
    """
    logger.info(f"MCP translate_text: {len(text)} chars → {target_language}")

    try:
        from app.services import translation

        translated = await translation.translate_text(text, target_language)

        return {
            "translated_text": translated,
            "source_language": source_language,
            "target_language": target_language,
            "character_count": len(text),
            "translated_character_count": len(translated),
            "success": True
        }
    except Exception as e:
        logger.error(f"MCP text translation failed: {e}")
        return {
            "error": str(e),
            "target_language": target_language,
            "success": False
        }


@mcp.tool()
async def validate_translation_quality(
    source_text: str,
    translated_text: str,
    target_language: str
) -> Dict[str, Any]:
    """
    Validate the quality of a translation using AI quality assessment.

    Evaluates: Accuracy, Completeness, Fluency, Terminology
    Returns detailed quality scores and recommendations.

    Args:
        source_text: Original text
        translated_text: Translated text to validate
        target_language: Target language code

    Returns:
        Dictionary with quality scores, issues, and recommendations

    Example:
        result = await validate_translation_quality(
            source_text="Hello world",
            translated_text="Hola mundo",
            target_language="Spanish"
        )
        # Access: result['quality_score'], result['issues'], result['recommendation']
    """
    logger.info(f"MCP validate_translation_quality: {len(source_text)} chars")

    try:
        from app.services import validation

        result = await validation.validate_translation(
            source_text=source_text,
            translated_text=translated_text,
            target_language=target_language
        )

        logger.info(f"Validation complete: Quality score {result.get('quality_score', 'N/A')}")
        return result

    except Exception as e:
        logger.error(f"MCP validation failed: {e}")
        return {
            "error": str(e),
            "success": False
        }


# =================================================
# SERVER ENTRYPOINT
# =================================================

if __name__ == "__main__":
    logger.info("🚀 Starting STARK Translator MCP Server")
    logger.info("Available tools: translate_document, translate_text, validate_translation_quality")
    logger.info("Available resources: stark://supported-languages, stark://service-info")
    mcp.run()
