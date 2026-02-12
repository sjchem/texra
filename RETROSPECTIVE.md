# Retrospective — If I Had to Start Over

## What Worked Well

**The orchestrator-first approach.** Starting with a clean `TranslationOrchestrator` that routes by file type paid off immediately. Adding DOCX, PPTX, and ODT support later was straightforward — each format got its own loader/writer without touching existing code. The orchestrator just needed a new `elif` branch.

**Separating agents from services.** Keeping `TranslatorAgent` and `ValidatorAgent` as thin wrappers around the OpenAI Agents SDK, with all deterministic logic in services, made debugging much easier. When translation broke, I always knew whether the issue was in the LLM response or in my text processing.

**WebSocket for progress.** Choosing WebSocket over HTTP polling for the Streamlit↔FastAPI connection was the right call. Real-time progress updates made the UX feel responsive, even for large documents that take minutes.

**Docker Compose with two services.** Splitting the backend and frontend into separate containers mirrors production patterns and made it possible to restart one without the other during development.

## What Didn't Work

**PDF formatting preservation was over-engineered initially.** I first tried an overlay approach — extracting each text block with its bounding box, translating it, and inserting it back at the exact position. This broke constantly: translated text was longer/shorter than the original, fonts didn't match, and some pages came out blank. I should have started with the simpler "extract all text → translate → write clean justified PDF" approach from day one.

**Too many format-specific edge cases at once.** I tried to handle DOCX images, PPTX tables, PDF layouts, and ODT conversion all in parallel. This spread my attention thin and led to half-working features. A better approach: get one format working end-to-end perfectly, then add the next.

**The chunking threshold was set too conservatively at first.** I started with 15K characters, which triggered large-document mode too often. Tuning it to 40K after testing was easy, but I should have profiled real document sizes earlier.

## What I'd Do Differently

### 1. Start with tests
I'd write integration tests before building features. Even simple ones like "upload a 2-page PDF, get back a translated PDF with non-empty text" would have caught many regressions automatically instead of me clicking through the UI repeatedly.

### 2. Use a message queue instead of direct WebSocket
The current architecture has the Streamlit frontend connecting directly to FastAPI via WebSocket. For production, I'd use Redis or a task queue (Celery/Dramatiq) so that:
- Translation jobs survive server restarts
- Multiple workers can process jobs in parallel
- The frontend can poll for results without holding a connection open

### 3. Build the MCP server first
The MCP server was added after the web UI was complete. In hindsight, building the MCP interface first would have forced a cleaner API design — the orchestrator would have been designed as a library from the start rather than being tightly coupled to the WebSocket handler.

### 4. Use a proper PDF library for formatting
ReportLab works for simple justified text output, but for true layout preservation I'd evaluate `pdfplumber` + `fpdf2` or even a headless LibreOffice approach. The text-overlay method I attempted was fragile. A more pragmatic approach: convert everything through LibreOffice for format fidelity, and only use direct manipulation for simple cases.

### 5. Add streaming translation
Currently, the user waits for the entire document to finish. With streaming, I could show translated chunks as they complete — the first page appears in seconds while the rest continues in the background.

### 6. Better error recovery
Right now, if one chunk fails, the `_clean_translation` function falls back to the original text. A better approach: retry with a different model (e.g., fall back from gpt-4o-mini to gpt-4o for that specific chunk), or let the user see which sections failed and retry selectively.

## Key Lessons

- **Simple wins over clever.** The clean justified PDF output is more useful than a broken layout-preserving one.
- **LLMs are unreliable for structured output.** The validator agent sometimes returns malformed JSON. Always parse defensively.
- **Docker changes everything.** Bugs that work locally can fail in containers (file paths, network names, missing env vars). Test in Docker early and often.
- **Prompt engineering is iterative.** The translator prompt went through several versions before landing on one that consistently avoids commentary and stays faithful to the source text.
