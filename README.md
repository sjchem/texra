# ⭕ STARK TRANSLATOR

AI-powered document translation service built with **FastAPI**, **OpenAI Agents SDK**, and **Streamlit**.

---

## Quick Start

```bash
git clone <repo-url> && cd stark-translator
cp .env.example .env        # Add your OPENAI_API_KEY
docker compose up --build
```

Open **http://localhost:8501** in your browser.

---

## Architecture

```
Browser (Streamlit :8501)
    │  WebSocket
    ▼
FastAPI Backend (:8000)
    │
    ▼
TranslationOrchestrator
    ├── Format Routing
    │   ├── PDF  → PdfFormattingService (layout-preserving)
    │   ├── DOCX → DocxTranslationService (style-preserving)
    │   ├── PPTX → PptxTranslationService (slide-preserving)
    │   ├── Images → OCR (GPT-4o Vision) → PDF
    │   └── ODT/TXT → Standard workflow → PDF
    │
    ├── Size Detection (threshold: 40K chars)
    │   ├── Small docs → parallel chunk translation
    │   └── Large docs → smart chunking + context overlap
    │
    ├── TranslatorAgent (gpt-4o-mini) — faithful translation
    ├── ValidatorAgent  (gpt-4o-mini) — quality scoring
    └── Format-specific Writers → output file
```

### Why This Architecture?

| Decision | Reasoning |
|----------|-----------|
| **Multi-agent** (Translator + Validator) | Single-responsibility: one agent translates, another validates. Clean handoff, independent prompt tuning. |
| **Orchestrator pattern** | Deterministic routing stays in Python (no LLM needed to pick a file format). LLMs only do what requires reasoning. |
| **Format-specific loaders/writers** | Each format (DOCX, PPTX, PDF) has unique structure. Dedicated handlers preserve formatting without cross-format complexity. |
| **Async parallel translation** | Chunks translate concurrently via `asyncio.gather` with semaphore-bounded concurrency (5). Preserves order, avoids rate limits. |
| **Smart chunking with overlap** | 200-token overlap between chunks prevents coherence loss at boundaries. Semantic splitting never breaks mid-sentence. |
| **gpt-4o-mini** | Cost-effective for translation tasks. Sufficient quality for most languages; budget-conscious per assessment guidance. |

---

## Features

| Feature | Details |
|---------|---------|
| **Supported formats** | PDF, DOCX, PPTX, ODT, TXT, PNG, JPG, JPEG, WEBP, GIF |
| **Formatting preservation** | PDF (layout, images, fonts, colors), DOCX (styles, tables, images), PPTX (slides, shapes, formatting) |
| **OCR** | Scanned PDFs and images via GPT-4o Vision |
| **Large documents** | Smart chunking with context overlap — no practical size limit |
| **Output format choice** | DOCX→DOCX/PDF, PPTX→PPTX/PDF, PDF→PDF |
| **8 target languages** | Spanish, French, English, Portuguese, Italian, German, Chinese, Japanese |
| **Quality validation** | Sample-based scoring (Accuracy, Completeness, Fluency, Terminology) with retry |
| **Real-time progress** | WebSocket-based progress bar with percentage updates |
| **Side-by-side preview** | Original and translated documents displayed together |
| **MCP server** | Use from Cursor/Claude Desktop — translate files, text, or validate quality |
| **Observability** | Trace IDs, per-agent timing, chunk-level metrics |

---

## Testing Guide

### 1. PDF Translation (Core Feature)
1. Upload any PDF → select target language → click **TRANSLATE**
2. Verify: progress bar updates, translated PDF appears in preview, download works
3. Check translated PDF has justified text and readable formatting

### 2. DOCX Translation with Image Preservation
1. Upload a DOCX containing images and formatted text
2. Select output format: **DOCX (preserve formatting)** or **PDF**
3. Verify: images are preserved, styles maintained, download in chosen format

### 3. PPTX Translation
1. Upload a PowerPoint file
2. Select output format: **PPTX** or **PDF**
3. Verify: slide layouts and text formatting preserved

### 4. Image OCR + Translation
1. Upload a PNG/JPG with text content
2. Verify: text is extracted via OCR and translated to PDF

### 5. Large Document Handling
1. Upload a document > 20 pages
2. Verify: progress updates incrementally, translation completes without timeout

### 6. Quality Validation
1. After any translation completes, check the **Quality Validation Report** below the preview
2. Verify: quality score, issue count, and recommendation (pass/review/retranslate) displayed

### 7. Side-by-Side Preview
1. After translation, verify both **Original** and **Translated** panels render correctly

### 8. MCP Server (Optional)
```bash
python -m app.mcp_server
```
Configure in Cursor/Claude Desktop per [MCP_SETUP.md](MCP_SETUP.md). Test: *"Translate my document to Spanish using stark-translator"*

---

## Project Structure

```
app/
├── main.py              # FastAPI + WebSocket endpoint
├── orchestrator.py      # Central routing & workflow control
├── mcp_server.py        # MCP server (3 tools, 2 resources)
├── agents/
│   ├── translator.py    # TranslatorAgent (gpt-4o-mini)
│   └── validator.py     # ValidatorAgent (gpt-4o-mini)
├── services/
│   ├── pdf_formatter.py # PDF translation with layout preservation
│   ├── docx_*.py        # DOCX loader/writer/translation
│   ├── pptx_*.py        # PPTX loader/writer/translation
│   ├── chunker.py       # Smart chunking with overlap
│   ├── large_doc_translation.py
│   ├── ocr.py           # GPT-4o Vision OCR
│   ├── writer.py        # PDF/DOCX output writers
│   └── validation.py    # Quality validation adapter
├── core/
│   ├── logging.py       # Structured logging with trace IDs
│   └── exceptions.py    # Custom exceptions
└── models/              # Request/response models
streamlit_app.py         # Streamlit frontend
```

---

## Running Locally (Without Docker)

```bash
cp .env.example .env     # Add OPENAI_API_KEY
pip install -r requirements.txt

# Terminal 1: Backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
streamlit run streamlit_app.py --server.port 8501
```

---

## Key Files

| File | Purpose |
|------|---------|
| [PROMPTS.md](PROMPTS.md) | All AI prompts used during development |
| [RETROSPECTIVE.md](RETROSPECTIVE.md) | What I'd do differently |
| [MCP_SETUP.md](MCP_SETUP.md) | MCP server configuration guide |
| [QUESTIONS_TO_CONSIDER.md](QUESTIONS_TO_CONSIDER.md) | Architecture decision rationale |
| [.env.example](.env.example) | Environment variable template |
