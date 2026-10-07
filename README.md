# Texra

**AI-powered document translation for teams.**

Texra is an early-stage SaaS platform for translating business documents while preserving their structure, layout, and visual identity. The product is being built for teams that need dependable multilingual content without rebuilding every PDF, Word document, or presentation by hand.

> Texra is currently in active development. This repository contains the working product prototype and is not yet a production-ready hosted service.

## What Texra does

Texra combines document parsing, AI translation, quality validation, and format-aware output generation in one workflow:

- Translates PDF, DOCX, PPTX, ODT, TXT, and image files
- Preserves document formatting, images, styles, tables, and slide layouts where supported
- Extracts and translates text from scans and images with OCR
- Processes large documents with context-aware chunking and bounded concurrency
- Validates translation quality for accuracy, completeness, fluency, and terminology
- Shows live translation progress and side-by-side document previews
- Produces downloadable PDF, DOCX, or PPTX output, depending on the source format
- Exposes translation capabilities through an optional MCP server

The current web interface supports translation into Spanish, French, English, Portuguese, Italian, German, Chinese, and Japanese.

## Product vision

Texra is evolving from a translation prototype into a multi-tenant SaaS product. The goal is to give companies a secure workspace where they can translate, review, manage, and reuse multilingual documents at scale.

Planned product areas include:

- User accounts, organizations, and team workspaces
- Subscription plans, usage limits, and billing
- Secure cloud storage and translation history
- Shared terminology, glossaries, and brand-language rules
- Human review and approval workflows
- Usage analytics, audit logs, and administrative controls
- Public API access and third-party integrations
- Production-grade job queues, monitoring, and deployment

## How it works

```text
Browser (Streamlit)
        |
        | WebSocket
        v
FastAPI backend
        |
        v
Translation orchestrator
        |-- Detects and routes the document format
        |-- Extracts text and document structure
        |-- Translates chunks concurrently
        |-- Validates translation quality
        `-- Rebuilds the requested output file
```

Texra uses format-specific services for PDF, DOCX, PPTX, text, and image workflows. This keeps document handling deterministic while reserving AI models for translation, OCR, and quality evaluation.

## Technology

- Python
- FastAPI and WebSockets
- Streamlit
- OpenAI Agents SDK and OpenAI models
- PyMuPDF and ReportLab
- python-docx, python-pptx, and odfpy
- Docker and Docker Compose
- Model Context Protocol (MCP)

## Run with Docker

### Requirements

- Docker with Docker Compose
- An OpenAI API key

### Setup

```bash
git clone <repository-url>
cd texra
cp .env.example .env
```

Add your API key to `.env`:

```env
OPENAI_API_KEY=your_openai_api_key
```

Build and start the application:

```bash
docker compose up --build
```

Open [http://localhost:8501](http://localhost:8501) to use the web application. The API health endpoint is available at [http://localhost:8000/health](http://localhost:8000/health).

## Run locally

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

After adding `OPENAI_API_KEY` to `.env`, start the backend:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In another terminal, start the frontend:

```bash
streamlit run streamlit_app.py --server.port 8501
```

## MCP server

Texra also includes an MCP server for document translation, text translation, and translation-quality validation:

```bash
python -m app.mcp_server
```

See [MCP_SETUP.md](MCP_SETUP.md) for configuration details.

## Project structure

```text
app/
|-- agents/                 # Translation and validation agents
|-- core/                   # Configuration, logging, and exceptions
|-- models/                 # Request and response models
|-- services/               # Format processing, OCR, translation, and output
|-- main.py                 # FastAPI and WebSocket backend
|-- mcp_server.py           # MCP tools and resources
`-- orchestrator.py         # Translation workflow and format routing

streamlit_app.py            # Web interface
docker-compose.yml          # Local multi-service environment
Dockerfile                  # Application image
requirements.txt            # Python dependencies
```

## Development status

The repository currently represents Texra's application prototype. Before operating it as a public SaaS platform, the project still needs production authentication, tenant isolation, billing, persistent storage, background job infrastructure, rate limiting, security hardening, observability, and deployment automation.

## Contributing

Texra is under active development. If you want to contribute, open an issue describing the proposed change before submitting a pull request.

## License

No license has been added yet. Until one is provided, all rights are reserved.
