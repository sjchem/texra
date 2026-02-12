
_Log of all AI prompts used during development_

This document logs **all prompts and agent instructions** used during the development of the Stark Translator project.
It intentionally includes early, naive prompts as well as evolved agent instructions to show how the system design matured over time.

---

## Phase 1 – Baseline Translation Prompt (No Agents)

**Context**
Initial proof-of-concept to validate an end-to-end pipeline:
PDF → extract text → translate → rebuild PDF.

At this stage, the system used direct OpenAI API calls with no agent abstraction.

**Prompt**
Translate the following text to {language}:
{text}


**Observations**
- Translation quality was generally good
- Formatting degraded on long paragraphs
- No hallucinations observed
- Lacked guardrails (occasionally rephrased content)

**Limitations**
- No separation of concerns
- No retry or validation strategy
- No observability
- Hard to extend or reason about behavior

**Decision**
Move translation logic into a dedicated Translation Agent.

---

## Translator Agent – v1 (OpenAI Agents SDK)

**Context**
Migrated translation into a dedicated agent using the OpenAI Agents SDK.

**Agent Instructions**
You are a professional document translator.

Rules:

Translate the text faithfully into the target language

Do NOT add explanations, notes, or commentary

Do NOT omit any content

Preserve tone and meaning

Return ONLY the translated text


**Why an Agent**
- Clear separation of concerns
- Enables orchestration and handoffs
- Easier retries and validation
- Improves observability and tracing
- Scales to batch and multi-language translation

**Observations**
- Output became more consistent
- Reduced stylistic drift
- Slight latency increase (acceptable trade-off)
- Translation became a reusable capability

---

## Migration from Direct API Calls to Agents

**Change**
- Removed all direct `OpenAI()` client usage
- Routed all translation through `TranslatorAgent`

**Reason**
- Avoid mixing paradigms (raw API vs agents)
- Centralize translation behavior
- Prepare system for validation and orchestration

**Outcome**
- Behavior preserved
- Architecture simplified
- Translation isolated behind an agent boundary

---

## Parallel Translation Upgrade

**Context**
Sequential chunk translation caused unnecessary latency for multi-page documents.

**Change**
- Introduced async parallel execution using `asyncio.gather`

**Design**
- Parallelize at chunk level
- Pages processed sequentially
- Concurrency capped via semaphore

**Why**
- Faster translation for large documents
- Better utilization of network-bound LLM calls
- Prevents rate-limit spikes

**Outcome**
- Significant performance improvement
- Output order preserved
- No loss of correctness

---

## Validator Agent – v1 (Quality Assurance)

**Context**
Added a validation step to detect hallucinations or missing content.

**Agent Instructions**
You are a translation quality validator.

You will be given:

Original text

Translated text

Target language

Your task:

Check if the translation is faithful

Ensure no content is missing or added

Ignore stylistic differences

Respond with ONLY valid JSON in this format:

{
"is_valid": true | false,
"reason": "short explanation"
}

**Design Decisions**
- Sample-based validation (1–2 chunks per page)
- Retry failed chunks once
- Validator acts as a safety net, not a perfection engine

**Why**
- Balances quality, latency, and cost
- Avoids validating entire documents
- Protects against rare hallucinations

**Observations**
- Validator rarely fails, but is valuable when it does
- Retry logic increases robustness
- JSON-only output simplifies parsing

---

## Orchestrator Agent (Control Logic)

**Context**
Centralized workflow control into a single orchestration layer.

**Responsibilities**
- Page-level processing
- Chunking coordination
- Async parallel translation
- Validator invocation and retries
- Final document assembly

**Prompting Strategy**
- Orchestrator is non-LLM
- Uses agents as tools
- Emphasizes determinism and traceability

**Outcome**
- Clean, debuggable execution flow
- Single source of truth
- Easy to extend with new agents or steps

---

## Observability & Tracing

**Context**
Added observability to understand agent behavior and system performance.

**Instrumentation Strategy**
- Per-request trace IDs
- Per-agent timing logs
- Chunk-level translation metrics
- OpenAI Agents SDK trace export

**Observations**
- Enabled full end-to-end request tracing
- Simplified debugging of async agent workflows
- Confirmed concurrency behavior under load

---

## Streamlit UI Integration (Non-LLM)

**Context**
Built a Streamlit frontend to demonstrate a complete, user-facing product.

**Supported Formats**
- PDF
- DOCX
- ODT
- TXT

**Design Notes**
- UI contains no prompts
- Acts purely as a client of the FastAPI backend
- All AI logic remains server-side

**Outcome**
- Significantly improved usability
- Demonstrates real-world application readiness
- No duplication of AI logic

---

## MCP Server Integration

**Context**
Explored Model Context Protocol (MCP) to expose translation as a reusable tool.

**Design**
- MCP server wraps the OrchestratorAgent
- No translation logic duplicated
- FastAPI and MCP coexist cleanly

**Example Tool**
```python
translate_pdf(file_bytes, target_language) -> translated_pdf
```

---

## MCP Server Debug & Fix

**Context**
User reported that the MCP server implementation had critical bugs preventing it from working.

**Prompt**
> "I have created mcp_server.py can you check it works perfect or not?"

**Issues Found**
1. Wrong import path: `from app.agents.orchestrator import OrchestratorAgent` (doesn't exist)
2. Wrong class name: `OrchestratorAgent` instead of `TranslationOrchestrator`
3. Non-existent method: `run()` instead of `translate()`
4. Type mismatch: orchestrator expects file paths, not raw bytes
5. Missing file handling: no bytes-to-file conversion

**Failed Approach**
Initial implementation tried to pass bytes directly to orchestrator:
```python
orchestrator = OrchestratorAgent()
return await orchestrator.run(file_bytes, target_language)
```

**Why It Failed**
- `OrchestratorAgent` class doesn't exist
- `TranslationOrchestrator.translate()` requires a file path
- No `run()` method exists

**Working Solution**
```python
import os
import tempfile
from app.orchestrator import TranslationOrchestrator

with tempfile.TemporaryDirectory() as tmpdir:
    input_path = os.path.join(tmpdir, filename)
    with open(input_path, "wb") as f:
        f.write(file_bytes)

    orchestrator = TranslationOrchestrator()
    output_path = await orchestrator.translate(input_path, target_language)

    with open(output_path, "rb") as f:
        return f.read()
```

**Lessons Learned**
- Always verify class names and import paths
- Check method signatures before calling
- Handle type conversions (bytes ↔ files) explicitly
- Use temporary files for orchestrator integration

---

## PDF Text Alignment Fix

**Context**
User uploaded comparison showing English PDF had justified text (evenly distributed between margins) but Spanish translation was left-aligned.

**Prompt**
> "You can see the uploaded english one justify mode means distribute text evenly between margin, but translated one is not I also want translated one should show same"

**Root Cause**
PDF writer was using `TA_LEFT` alignment instead of `TA_JUSTIFY`.

**Fix**
```python
# Changed in app/services/writer.py
from reportlab.lib.enums import TA_JUSTIFY  # was TA_LEFT

body_style = ParagraphStyle(
    alignment=TA_JUSTIFY,  # was TA_LEFT
    ...
)
```

**Outcome**
- Translated PDFs now match source formatting
- Text properly justified on both margins
- Professional document appearance maintained

---

## Streamlit UI Redesign: Split-Pane Dashboard

**Context**
User wanted a better layout with sidebar for inputs and main area for results.

**Prompt**
> "I like to keep the 'upload a pdf document' on the left side, translate key right side, so after translate it can show pdf viewer too and download also."

**Design Requirements**
- Left sidebar: file upload + language selector
- Right main area: translate button + PDF viewer + download
- Split-pane layout (fixed sidebar, scrollable main area)
- One-screen sidebar (no scrolling needed)

**Implementation**
```python
# Wide layout for split pane
st.set_page_config(layout="wide")

# Sidebar (left)
with st.sidebar:
    uploaded_file = st.file_uploader(...)
    target_language = st.selectbox(...)

# Main area (right)
st.button("🔄 TRANSLATE DOCUMENT")
# PDF viewer with base64 encoding
st.markdown(f'<iframe src="data:application/pdf;base64,{base64_pdf}">')
st.download_button(...)
```

**Outcome**
- Improved UX with logical grouping
- Better screen space utilization
- Professional dashboard appearance
- PDF preview before download

---

## Sidebar Space Optimization

**Context**
Sidebar elements required scrolling to see all controls.

**Prompt**
> "Reduce the space from each part like from STARK Translator to upload document reduce gap...also the logo can be more above so in one page sidebar all can be shown, no need to scroll"

**Changes Made**
1. **Logo**: 100px → 70px, margin 20px → 10px
2. **Title**: 32px → 24px, letter-spacing 4px → 3px
3. **Spacing**: Removed `st.markdown("---")` dividers
4. **Padding**: File uploader 20px → 15px
5. **Info messages**: Made more compact
   - "✓ File loaded: filename" → "✓ filename"
   - "📊 Size: XX KB" → "📊 XX KB"

**CSS Adjustments**
```css
[data-testid="stSidebar"] {
    padding-top: 1rem;
}
[data-testid="stSidebar"] .element-container {
    margin-bottom: 0.5rem;
}
```

**Outcome**
- All sidebar controls visible without scrolling
- Cleaner, more compact interface
- Better mobile/small screen support

---

## UI Polish: Remove Unnecessary Elements

**Prompt**
> "After translation no need to appear [success message] as it is unnecessary, remove it, also make closer"

**Changes**
- Removed "✅ Translation completed successfully!" banner
- Removed horizontal dividers (`st.markdown("---")`)
- Tightened spacing between sections

**Outcome**
- Cleaner, more streamlined interface
- PDF viewer appears immediately after translation
- Better screen space utilization
- Less visual clutter

---

## Multi-Format Document Support

**Context**
User wanted to support more than just PDF files.

**Prompt**
> "As it only upload pdf, I like to make it you can upload any document, like pdf, docx, odt txt also other possible"

**Implementation Strategy**

**1. Added Dependencies**
```pip-requirements
python-docx  # for Microsoft Word
odfpy        # for OpenDocument Text
```

**2. Created New Loaders**
```python
class DocxLoader(Loader):
    def load(self, file_path: str) -> list[str]:
        from docx import Document
        doc = Document(file_path)
        text = "\n".join([p.text for p in doc.paragraphs])
        return [text]

class OdtLoader(Loader):
    def load(self, file_path: str) -> list[str]:
        from odf import text as odf_text
        from odf.opendocument import load as odf_load
        doc = odf_load(file_path)
        paragraphs = doc.getElementsByType(odf_text.P)
        text = "\n".join([str(p) for p in paragraphs])
        return [re.sub(r'<[^>]+>', '', text)]  # Clean XML tags
```

**3. Updated LoaderFactory**
```python
@staticmethod
def get_loader(file_path: str) -> Loader:
    file_path_lower = file_path.lower()
    if file_path_lower.endswith(".pdf"): return PdfLoader()
    elif file_path_lower.endswith(".docx"): return DocxLoader()
    elif file_path_lower.endswith(".odt"): return OdtLoader()
    elif file_path_lower.endswith(".txt"): return TextLoader()
    else: raise ValueError(f"Unsupported file type")
```

**4. Updated File Uploader**
```python
st.file_uploader(
    "📄 Upload Document",
    type=["pdf", "docx", "odt", "txt"],
    help="Select a document to translate"
)
```

**Outcome**
- Expanded from 1 to 4 supported formats
- All formats translate to PDF output
- Maintained justified text formatting
- Clean abstraction via LoaderFactory

---

## DOCX WriterFactory Bug Fix

**Context**
User reported error when uploading DOCX files.

**Error**
```
Error: Unsupported file type: /tmp/tmppis81red/Simple rule to remember.docx
```

**Root Cause**
WriterFactory only accepted `.pdf` extension, rejecting other input formats even though they should all output to PDF.

**Failed Code**
```python
class WriterFactory:
    @staticmethod
    def get_writer(file_path: str) -> Writer:
        if file_path.endswith(".pdf"):
            return PdfWriter()
        else:
            raise ValueError(f"Unsupported file type: {file_path}")
```

**Why It Failed**
- WriterFactory checked input file extension
- Should check output format intent, not input
- All documents output to PDF regardless of input type

**Working Solution**
```python
class WriterFactory:
    @staticmethod
    def get_writer(file_path: str) -> Writer:
        # Always return PdfWriter - all documents are translated to PDF
        # regardless of input format (pdf, docx, odt, txt)
        return PdfWriter()
```

**Lesson Learned**
- Loader → reads input format
- Writer → creates output format (always PDF)
- Factory pattern must understand data flow direction
- Input extension ≠ Output extension

---

## Summary of Key Design Decisions

### Agent Architecture
- **TranslatorAgent**: Handles all translation logic
- **ValidatorAgent**: Sample-based quality checks
- **Orchestrator**: Coordinates workflow (non-LLM)

### Performance Optimizations
- Parallel chunk translation with semaphore
- Sample-based validation (not full document)
- Async/await throughout

### Multi-Format Support
- **Input**: PDF, DOCX, ODT, TXT
- **Output**: Always PDF (justified, formatted)
- Loader/Writer factories for extensibility

### UI/UX
- Split-pane dashboard (sidebar + main)
- Embedded PDF viewer with base64 encoding
- Compact, no-scroll sidebar design
- Real-time progress tracking

### MCP Integration
- Exposes translation as reusable tool
- Handles bytes ↔ file conversions
- Coexists with FastAPI backend

---

## Failed Attempts & Lessons

### 1. Direct Byte Passing to Orchestrator
**Failed**: Tried passing bytes directly to `TranslationOrchestrator`
**Why**: Orchestrator needs file paths for loader/writer factories
**Solution**: Use temporary files for conversion

### 2. Full Document Validation
**Failed**: Validating every chunk was too slow and expensive
**Why**: Diminishing returns, high latency
**Solution**: Sample-based validation (5 chunks max)

### 3. Sequential Translation
**Failed**: Processing chunks one-by-one took too long
**Why**: Network-bound LLM calls not parallelized
**Solution**: `asyncio.gather` with semaphore rate limiting

### 4. Extension-Based Output Factory
**Failed**: WriterFactory rejected non-PDF input extensions
**Why**: Confused input format with output format
**Solution**: Always return PdfWriter (format conversion is the point)

### 5. Centered Streamlit Layout
**Failed**: Original centered layout wasted screen space
**Why**: Didn't accommodate PDF viewer + controls together
**Solution**: Wide layout with split-pane design

---

_End of prompts log. All AI interactions documented above, including mistakes and iterations._
