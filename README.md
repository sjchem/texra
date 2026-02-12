## Stark Translator — AI-Powered Document Translation
Overview

Stark Translator is an AI-powered document translation service that accepts multiple document formats (PDF, DOCX, ODT, TXT, PPTX, PNG, JPG, etc.) and returns translated documents while preserving structure, formatting, and layout.

The project is designed as a multi-agent system using the OpenAI Agents SDK, with a strong focus on:

clean orchestration

extensibility

observability

performance

thoughtful trade-offs

This repository was built as part of an AI Engineer take-home assignment.

Features

📄 **Multiple document formats:** PDF, DOCX, ODT, TXT, PPTX, PNG, JPG, JPEG, WEBP, GIF

🔍 **OCR Support:**
  - **Image files**: Extract and translate text from images (PNG, JPG, JPEG, WEBP, GIF)
  - **Scanned PDFs**: Automatic detection and OCR processing of image-based PDFs
  - **Powered by OpenAI Vision API (GPT-4o)** for high-quality text extraction with layout preservation

📚 **Large Document Handling:**
  - **Smart chunking** with semantic boundaries (paragraphs, sentences)
  - **Context-aware translation** with 200-token overlap between chunks
  - **Automatic detection** of documents exceeding context window limits (>15K characters)
  - **Coherence preservation** across chunk boundaries

✨ **Comprehensive formatting preservation:**
  - **PDF**: Layout, images, tables, font styles, colors, positioning
  - **DOCX**: Styles, formatting, tables, images, paragraph formatting
  - **PPTX**: Styles, tables, images, slide layouts, text formatting
  - **ODT**: Converted to PDF with formatting
  - **TXT**: Plain text format maintained

📤 **Flexible output formats:**
  - **DOCX** → DOCX (preserve formatting) or PDF
  - **PPTX** → PPTX (preserve formatting) or PDF
  - **PDF** → PDF (formatting always preserved)
  - **Images** → PDF (OCR + Translation)
  - **ODT/TXT** → PDF

🌍 Arbitrary target language selection

🤖 Multi-agent architecture (Orchestrator, Translator, Validator)

⚡ Async parallel translation for performance

✅ Quality validation with retry logic

🔍 Agent-level observability and tracing

🧱 Clean separation of concerns (agents vs services)

🐳 Dockerized for reproducibility

🔌 **MCP Server Integration:**
  - **Model Context Protocol (MCP) support** for AI assistant integration
  - Use STARK Translator directly from **Cursor**, **Claude Desktop**, or any MCP-compatible client
  - **3 MCP Tools**: `translate_document`, `translate_text`, `validate_translation_quality`
  - **2 MCP Resources**: `stark://supported-languages`, `stark://service-info`
  - Full AI orchestration accessible via protocol-based tooling
  - See [MCP_SETUP.md](MCP_SETUP.md) for configuration guide

### MCP (Model Context Protocol) Integration

STARK Translator includes a complete **MCP server** implementation, allowing you to use the translation service directly from AI coding assistants like **Cursor** or **Claude Desktop**.

#### What is MCP?

Model Context Protocol (MCP) is a standard that enables AI assistants to connect to external tools and data sources. With STARK's MCP server, you can:

- **Translate documents directly from Cursor** while coding
- **Access translation tools** from Claude Desktop
- **Validate translation quality** using AI assessment
- **Batch process files** using MCP clients

#### Available MCP Tools

1. **`translate_document`** - Translate any supported document format (PDF, DOCX, PPTX, images)
2. **`translate_text`** - Quick text-only translation for snippets and paragraphs
3. **`validate_translation_quality`** - AI-powered quality assessment with detailed scoring

#### Available MCP Resources

1. **`stark://supported-languages`** - List of supported languages and formats
2. **`stark://service-info`** - Service capabilities, limits, and performance metrics

#### Quick Start with MCP

**Step 1: Run the MCP Server**
```bash
python -m app.mcp_server
```

**Step 2: Configure in Cursor/Claude Desktop**

Add to your MCP configuration file:
```json
{
  "mcpServers": {
    "stark-translator": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "cwd": "/path/to/stark-translator",
      "env": {
        "OPENAI_API_KEY": "your-key-here"
      }
    }
  }
}
```

**Step 3: Start Using**

From Cursor or Claude Desktop:
```
"Translate my document.pdf to Spanish using stark-translator"
```

For complete MCP setup instructions, configuration examples, and usage guides, see **[MCP_SETUP.md](MCP_SETUP.md)**.

### Architecture
Client (Browser / API)
        │
        ▼
FastAPI (app/main.py)
        │
        ▼
OrchestratorAgent
        │
        ├── Format Detection & Routing
        │   ├── PDF → PDF Formatter (preserves layout, images, tables)
        │   ├── DOCX → DOCX Translator (preserves styles, formatting)
        │   ├── PPTX → PPTX Translator (preserves slides, layouts)
        │   └── ODT/TXT → Standard workflow
        │       │
        │       ├── Size Detection
        │       │   ├── Small (< 15K chars) → Standard chunking + parallel translation
        │       │   └── Large (≥ 15K chars) → Smart chunking + context-aware translation
        │       │
        │       └── LargeDocumentTranslator (for large docs)
        │           ├── SmartChunker (overlap + semantic boundaries)
        │           ├── Context preservation between chunks
        │           └── Batch processing with coherence
        │
        ├── TranslatorAgent → OpenAI Agents SDK
        ├── ValidatorAgent → Quality check + retry
        └── Format-specific Writers

Key Design Principles

Agents decide what to do

Services implement how to do it

Deterministic tasks stay non-LLM

LLMs are used only where reasoning adds value

## Formatting Preservation

The system uses format-specific translation workflows to preserve document structure and styling:

### PDF Format
- ✅ Original page layout and positioning
- ✅ Images (preserved in place)
- ✅ Tables and structure
- ✅ Font styles (bold, italic)
- ✅ Font sizes
- ✅ Colors and formatting
- ✅ Graphics and shapes

### DOCX Format
- ✅ Paragraph styles and formatting
- ✅ Text runs with formatting (bold, italic, underline)
- ✅ Font names, sizes, and colors
- ✅ Tables with structure
- ✅ Images (preserved in place)
- ✅ Lists and numbering
- ✅ Document structure

### PPTX Format
- ✅ Slide layouts and positioning
- ✅ Text formatting (bold, italic, underline, fonts, sizes)
- ✅ Tables with structure
- ✅ Images (preserved in place)
- ✅ Shapes and groups
- ✅ Paragraph alignment and indentation
- ✅ Master slide formatting

### ODT Format
- Converted to PDF with formatting preserved

### TXT Format
- Plain text maintained (no formatting to preserve)

Agents
OrchestratorAgent

The Orchestrator is the central “brain” of the system.

Responsibilities:

Controls the end-to-end translation workflow

Splits documents into pages and chunks

Executes translation asynchronously in parallel

Triggers validation and retries when needed

Emits structured logs with trace IDs

This agent makes the system:

debuggable

observable

easy to extend with new steps or agents

TranslatorAgent (OpenAI Agents SDK)

A dedicated LLM-powered agent responsible only for translation.

Characteristics:

Stateless

Single responsibility

Prompted with strict instructions to avoid hallucinations

Invoked concurrently for multiple chunks

Using an agent instead of raw API calls enables:

clean agent handoffs

prompt transparency

tracing and observability

future MCP integration

ValidatorAgent

The ValidatorAgent performs sample-based quality validation.

Strategy:

Randomly samples 1–2 chunks per page

Compares source and translated text

Detects omissions or hallucinations

Retries failed chunks once

This balances:

translation quality

latency

cost

The validator acts as a safety net, not a perfection engine.

Services

Services contain deterministic, non-LLM logic:

**Format-Preserving Translation:**
- pdf_formatter.py — translate PDFs preserving layout, images, tables, fonts, colors
- docx_loader.py + docx_writer.py + docx_translation.py — DOCX with full formatting preservation
- pptx_loader.py + pptx_writer.py + pptx_translation.py — PowerPoint with slide structure preservation

**General Document Processing:**
- pdf_loader.py — extract text from PDFs
- loader.py — factory for loading multiple document formats
- writer.py — factory for writing output documents
- chunker.py — smart text chunking with overlap for large documents
- large_doc_translation.py — context-aware translation for documents exceeding context limits
- pdf_writer.py — rebuild translated PDFs
- translation.py — adapter for running TranslatorAgent
- validation.py — adapter for running ValidatorAgent

This separation ensures:

easy testing

low coupling

predictable behavior

extensibility for new formats

Async & Performance Strategy

Translation is parallelized at the chunk level

Pages are processed sequentially for memory safety

Concurrency is capped using an asyncio semaphore

asyncio.gather preserves output order

This significantly improves throughput for large documents while avoiding rate-limit issues.

## Large Document Handling

**Challenge:** Documents exceeding context window limits (typically 8K-128K tokens depending on model)

**Solution:** Multi-layered approach for handling documents of any size

### Smart Chunking Strategy

The system automatically detects document size and applies appropriate strategies:

**For documents > 15,000 characters (~3,750 tokens):**

1. **Intelligent Boundary Detection**
   - Splits at semantic boundaries (sections, paragraphs, sentences)
   - Never breaks mid-sentence or mid-paragraph
   - Preserves document structure

2. **Context Overlap**
   - Adds 200-token overlap between chunks
   - Previous chunk's ending provides context for next chunk
   - Prevents coherence loss at chunk boundaries

3. **Context-Aware Translation**
   - Passes limited context from previous chunk
   - LLM sees: `[Previous context: ...] + Current chunk`
   - Maintains narrative flow and terminology consistency

4. **Adaptive Batch Processing**
   - Processes 3 chunks in parallel, then uses last as context
   - Balances speed with coherence
   - Configurable: `use_context=True` for quality, `False` for speed

### Implementation Details

**Chunker** (`app/services/chunker.py`):
- `SmartChunker`: Intelligent chunking with metadata
- Token-aware sizing (not just character count)
- Returns chunk metadata: index, overlap info, boundary type

**Large Document Translator** (`app/services/large_doc_translation.py`):
- `LargeDocumentTranslator`: Orchestrates translation of large docs
- Two modes:
  - Context-aware (slower, better quality)
  - Parallel (faster, may lose some coherence)
- Automatic overlap removal to prevent duplication

**Thresholds:**
- Standard workflow: < 15,000 chars
- Large document workflow: ≥ 15,000 chars
- Max chunk size: 6,000 tokens (conservative for GPT-4)
- Overlap: 200 tokens

### Benefits

✅ **Handles unlimited document size** - No practical limit on document length

✅ **Preserves coherence** - Context overlap maintains narrative flow

✅ **Maintains terminology** - Consistent translation of repeated terms

✅ **Optimized performance** - Parallel processing where possible

✅ **Automatic detection** - No user configuration needed

### Example

For a 100-page document:
1. System detects size > threshold
2. Splits into ~30 chunks with 200-token overlap
3. Processes in batches of 3 chunks
4. Each batch sees context from previous batch
5. Merges translated chunks, removing duplicated overlap
6. Returns coherent translated document

Observability & Tracing

The system includes built-in observability:

Per-request trace IDs

Per-agent timing logs

Chunk-level translation metrics

OpenAI Agents SDK trace export

API Usage
Endpoint
POST /translate (via WebSocket)

Parameters

file — Document file (PDF, DOCX, ODT, TXT, or PPTX)

target_language — target language (string)

output_format — desired output format (string, optional)
  - "PDF" (default)
  - "DOCX" (only for DOCX input)
  - "PPTX" (only for PPTX input)

Response

Translated document file in the requested format:
- **PDF** → PDF (with formatting, images, tables preserved)
- **DOCX** → DOCX or PDF (user choice, formatting preserved)
- **PPTX** → PPTX or PDF (user choice, slides/layouts preserved)
- **ODT** → PDF (with formatting preserved)
- **TXT** → PDF

## User Interface

The Streamlit frontend provides:

- **Dynamic output format selector**: Choose output format based on input type
  - DOCX files: Option to output as DOCX or PDF
  - PPTX files: Option to output as PPTX or PDF
  - PDF files: Always output as PDF with formatting preserved
  - ODT/TXT files: Always output as PDF

- **Real-time progress tracking**: Visual progress bar with percentage
- **File preview**: PDF viewer for translated documents
- **Download button**: Download translated file in chosen format
- **Branded UI**: Stark-themed interface with gold accents

Swagger UI is available at:

http://localhost:8000/docs

Running Locally
Requirements

Python 3.11+

OpenAI API key

Setup
cp .env.example .env
export OPENAI_API_KEY=your_key_here
pip install -r requirements.txt
uvicorn app.main:app --reload

Running with Docker
docker compose up --build


Then open:

http://localhost:8000/docs

PROMPTS.md

All prompts used during development (including failed or iterated versions) are documented in PROMPTS.md.

This includes:

TranslatorAgent instructions

ValidatorAgent instructions

Prompt evolution notes

Retrospective

See RETROSPECTIVE.md for a reflection on:

what worked

what didn’t

what I would do differently if starting over
## Architecture

The application is composed of two main services:

-   **Streamlit Frontend:** A web interface built with Streamlit that allows users to upload documents and select a target language.
-   **FastAPI Backend:** A Python backend powered by FastAPI that handles the core translation logic using an agentic workflow.
