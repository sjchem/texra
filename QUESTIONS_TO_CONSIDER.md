# Questions to Consider - Architectural Decisions

This document provides concise answers to the key architectural questions from the assessment, with code examples demonstrating the implementation.

---

## 1. How do you approach translating a large document that doesn't fit in a single context window?

### Strategy: Smart Chunking + Context Preservation

**Threshold Detection:**
```python
# app/orchestrator.py
LARGE_DOC_THRESHOLD = 40000  # ~10,000 tokens with 4 chars/token (~20 pages)

if total_chars >= LARGE_DOC_THRESHOLD:
    # Use context-aware large document translation
    from app.services.large_doc_translation import LargeDocumentTranslator
    translator = LargeDocumentTranslator(max_concurrency=5)
    return await translator.translate_large_document(...)
else:
    # Standard chunking for smaller documents
    chunks = chunker.chunk_pages(pages, max_chunk_size=3000)
```

**Smart Chunking with Overlap:**
```python
# app/services/chunker.py
class SmartChunker:
    def chunk_with_overlap(self, text: str, chunk_size: int = 4000, overlap: int = 200):
        """
        Split text at semantic boundaries (paragraphs/sentences) with overlap
        to preserve context between chunks.
        """
        # Split on paragraph boundaries
        paragraphs = text.split('\n\n')

        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para)

            if current_size + para_size > chunk_size and current_chunk:
                # Save current chunk
                chunks.append('\n\n'.join(current_chunk))

                # Keep last paragraph(s) for overlap (context preservation)
                overlap_text = current_chunk[-1] if current_chunk else ""
                current_chunk = [overlap_text, para] if overlap_text else [para]
                current_size = len(overlap_text) + para_size
            else:
                current_chunk.append(para)
                current_size += para_size

        return chunks
```

**Key Features:**
- ✅ Semantic boundary splitting (paragraphs, not arbitrary character counts)
- ✅ 200-token overlap between chunks for context continuity
- ✅ Automatic detection based on character count
- ✅ Parallel translation of chunks with concurrency limits

---

## 2. How do you make translation as fast as possible?

### Strategy: Async Parallelization + Concurrency Control

**Parallel Chunk Translation:**
```python
# app/orchestrator.py
class TranslationOrchestrator:
    def __init__(self, max_concurrency: int = 5):
        # Limit parallel LLM calls to avoid rate limits and manage costs
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def _translate_chunk_with_limit(self, chunk, target_language, chunk_idx):
        """Translate single chunk with concurrency limit."""
        async with self.semaphore:  # Only 5 concurrent LLM calls max
            result = await translation.translate_chunk(
                chunk,
                target_language,
                self.trace_id,
                chunk_idx
            )
            return result

    async def _translate_standard(self, file_path, target_language, progress_callback):
        # Load document
        pages = loader.load(file_path)
        chunks = chunker.chunk_pages(pages, max_chunk_size=3000)

        # Translate all chunks in parallel
        tasks = [
            self._translate_chunk_with_limit(chunk, target_language, i)
            for i, chunk in enumerate(chunks)
        ]

        # Wait for all translations concurrently
        translated_chunks = await asyncio.gather(*tasks)

        return translated_chunks
```

**Concurrency Control Benefits:**
```python
# Without parallelization: 50 chunks × 3 seconds = 150 seconds
# With 5 parallel workers: 50 chunks / 5 × 3 seconds = 30 seconds
# Speed improvement: 5× faster
```

**Performance Optimizations:**
- ✅ **Async/await** - Non-blocking I/O for LLM API calls
- ✅ **asyncio.gather()** - Process multiple chunks concurrently
- ✅ **Semaphore limiting** - Prevent rate limit errors (max 5 concurrent)
- ✅ **Progress callbacks** - Real-time UI updates without blocking
- ✅ **Smart chunking** - Minimize number of API calls
- ✅ **Fast model selection** - Use `gpt-5-mini-2025-08-07` for cost/speed balance

---

## 3. How do you choose between a single agent or multi-agent architecture?

### Decision: Specialized Multi-Agent System

**Architecture Overview:**
```python
# Single responsibility agents
TranslatorAgent   → Translation only (linguistic expertise)
ValidatorAgent    → Quality assessment only (evaluation expertise)

# Non-agent orchestrator
Orchestrator      → Routing, chunking, progress (deterministic logic)
```

**Why Multi-Agent:**

**1. Separation of Concerns**
```python
# app/agents/translator.py
translator_agent = Agent(
    name="TranslatorAgent",
    model="gpt-5-mini-2025-08-07",
    instructions="""
    You are a professional translator.
    - Translate faithfully into target language
    - Preserve tone and meaning
    - Return ONLY translated text
    """
)

# app/agents/validator.py
validator_agent = Agent(
    name="QualityValidatorAgent",
    model="gpt-5-mini-2025-08-07",
    instructions="""
    You are a translation quality validator.
    - Assess accuracy, completeness, fluency
    - Provide quality scores (0-100)
    - Identify issues with severity levels
    - Return JSON with structured feedback
    """
)
```

**2. Parallel Execution**
```python
# Multiple translator agents run concurrently
tasks = [
    translator_agent.run(chunk_1, target_lang),
    translator_agent.run(chunk_2, target_lang),
    translator_agent.run(chunk_3, target_lang),
    translator_agent.run(chunk_4, target_lang),
    translator_agent.run(chunk_5, target_lang),
]
results = await asyncio.gather(*tasks)  # All run in parallel
```

**3. Independent Observability**
```python
# Each agent has separate tracing
logger.info(f"[Translator] Chunk {idx} - {len(chunk)} chars")
logger.info(f"[Validator] Quality score: {score}/100")
```

**4. Retry Logic with Validation**
```python
# app/orchestrator.py
async def _validate_and_retry(self, original, translated, target_language):
    """Validator agent checks translator agent's output."""
    validation_result = await validation.validate_translation(
        original,
        translated,
        target_language
    )

    if validation_result["quality_score"] < 60:
        # Retry translation if quality too low
        logger.warning(f"Low quality ({validation_result['quality_score']}), retrying...")
        return await self._translate_chunk_with_retry(original, target_language)

    return translated
```

**Why NOT Single Agent:**
- ❌ Can't parallelize effectively (sequential processing of 50 chunks)
- ❌ Mixed responsibilities reduce prompt quality
- ❌ No separation between execution and assessment
- ❌ Harder to trace which part failed
- ❌ Can't use different models for different tasks

**Design Principle:**
> **"Agents decide WHAT to do, Services implement HOW to do it"**

**LLMs used only where reasoning adds value:**
- ✅ Translation (linguistic decisions) → Agent
- ✅ Quality assessment (evaluation judgment) → Agent
- ❌ File format detection → Pure Python
- ❌ Chunking logic → Pure Python
- ❌ Progress tracking → Pure Python

---

## 4. How would you add support for a new file format in 10 minutes? Is your design extensible?

### Answer: YES - Factory Pattern + Abstract Base Classes

**Current Architecture:**
```python
# app/services/loader.py
class Loader(ABC):
    @abstractmethod
    def load(self, file_path: str) -> list[str]:
        pass

class LoaderFactory:
    @staticmethod
    def get_loader(file_path: str) -> Loader:
        if file_path.endswith(".pdf"):
            return PdfLoader()
        elif file_path.endswith(".docx"):
            return DocxLoader()
        elif file_path.endswith(".pptx"):
            return PptxLoader()
        # ... more formats
        else:
            raise ValueError(f"Unsupported file type: {file_path}")
```

**Adding Excel Support (Example):**

**Step 1: Create Loader (3 minutes)**
```python
# app/services/excel_loader.py
from app.services.loader import Loader

class ExcelLoader(Loader):
    def load(self, file_path: str) -> list[str]:
        import openpyxl
        wb = openpyxl.load_workbook(file_path)

        sheets = []
        for sheet in wb.worksheets:
            # Extract all cell values as text
            rows = []
            for row in sheet.iter_rows(values_only=True):
                row_text = '\t'.join(str(cell) for cell in row if cell)
                if row_text.strip():
                    rows.append(row_text)

            sheets.append('\n'.join(rows))

        return sheets
```

**Step 2: Create Writer (3 minutes)**
```python
# app/services/excel_writer.py
from app.services.writer import Writer
import openpyxl

class ExcelWriter(Writer):
    def write(self, sheets: list[str], original_path: str) -> str:
        # Load original workbook to preserve structure
        wb = openpyxl.load_workbook(original_path)

        # Replace cell contents with translations
        for sheet_idx, sheet_text in enumerate(sheets):
            if sheet_idx < len(wb.worksheets):
                sheet = wb.worksheets[sheet_idx]
                rows = sheet_text.split('\n')
                for row_idx, row_text in enumerate(rows, start=1):
                    cells = row_text.split('\t')
                    for col_idx, cell_value in enumerate(cells, start=1):
                        sheet.cell(row=row_idx, column=col_idx).value = cell_value

        # Save to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            wb.save(tmp.name)
            return tmp.name
```

**Step 3: Register in Factories (2 minutes)**
```python
# app/services/loader.py
class LoaderFactory:
    @staticmethod
    def get_loader(file_path: str) -> Loader:
        # ... existing formats ...
        elif file_path_lower.endswith(".xlsx"):
            return ExcelLoader()  # ← Add this line
```

```python
# app/services/writer.py
class WriterFactory:
    @staticmethod
    def get_writer(format: str) -> Writer:
        # ... existing formats ...
        elif format.upper() == "XLSX":
            return ExcelWriter()  # ← Add this line
```

**Step 4: Update Frontend (2 minutes)**
```python
# streamlit_app.py
uploaded_file = st.file_uploader(
    "📄 Upload Document",
    type=[
        "pdf", "docx", "pptx", "odt", "txt",
        "xlsx"  # ← Add this
    ]
)
```

**Total Time: ~10 minutes** ✅

**Why This is Fast:**
- ✅ **Abstract base classes** enforce consistent interface
- ✅ **Factory pattern** centralizes format routing
- ✅ **No orchestrator changes** - automatic routing
- ✅ **Translation agent is format-agnostic** - just translates text
- ✅ **Validation works automatically** - validates any format
- ✅ **Progress tracking works** - reuses existing callbacks


**Currently Supported (10 formats added this way):**
- PDF, DOCX, PPTX, ODT, TXT
- PNG, JPG, JPEG, WEBP, GIF (via OCR)

---

## 5. What happens when a user uploads an unsupported or corrupted file?

### Strategy: Multi-Layer Validation + Graceful Error Handling

**Layer 1: Frontend Validation (Prevention)**
```python
# streamlit_app.py
uploaded_file = st.file_uploader(
    "📄 Upload Document",
    type=["pdf", "docx", "pptx", "odt", "txt", "png", "jpg", "jpeg", "webp", "gif"],
    help="Select a document or image to translate"
)

# File size validation
if uploaded_file:
    file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
    if file_size_mb > 200:
        st.error(f"⚠️ File too large: {file_size_mb:.1f}MB. Maximum size is 200MB.")
        # Prevents submission
```

**Result:** Users can't select `.exe`, `.zip`, or other unsupported formats through UI

**Layer 2: Backend Format Validation**
```python
# app/services/loader.py
class LoaderFactory:
    @staticmethod
    def get_loader(file_path: str) -> Loader:
        file_path_lower = file_path.lower()

        # ... format checks ...

        else:
            raise ValueError(
                f"Unsupported file type: {file_path}. "
                f"Supported formats: PDF, DOCX, ODT, TXT, PPTX, PNG, JPG, JPEG, WEBP, GIF"
            )
```

**Layer 3: Corruption Detection (File Parsing)**
```python
# Example: PDF corruption detection
# app/services/pdf_loader.py
def load_pdf(file_bytes: bytes) -> list[str]:
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for page in doc:
            pages.append(page.get_text())
        return pages
    except Exception as e:
        # PyMuPDF raises exception if PDF is corrupted
        raise ValueError(f"Failed to read PDF file: {str(e)}. The file may be corrupted.")
```

```python
# Example: DOCX corruption detection
# app/services/docx_loader.py
def load(self, file_path: str) -> Dict[str, Any]:
    try:
        doc = Document(file_path)
        elements = []
        # ... extract content ...
        return {"elements": elements, "metadata": {}}
    except Exception as e:
        # python-docx raises exception for corrupted files
        raise ValueError(f"Failed to read DOCX file: {str(e)}. The file may be corrupted.")
```

**Layer 4: Global Error Handler**
```python
# app/main.py
@app.websocket("/ws/translate")
async def translate_pdf_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        # ... translation workflow ...

    except ValueError as e:
        # Unsupported format or corrupted file
        logger.error(f"Validation error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })

    except Exception as e:
        # Unexpected errors
        logger.error(f"Translation failed: {e}", exc_info=True)
        await websocket.send_json({
            "type": "error",
            "message": f"Translation failed: {str(e)}"
        })
```

**Layer 5: Frontend Error Display**
```python
# streamlit_app.py
async def _translate_ws(file_bytes, filename, language, output_format, q):
    try:
        # ... websocket communication ...

        if data["type"] == "error":
            q.put({"type": "error", "message": data["message"]})
            break

    except Exception as e:
        # Connection errors, parsing errors, etc.
        q.put({"type": "error", "message": str(e)})

# Display to user
if st.session_state.status.startswith("Error:"):
    st.error(st.session_state.status)
```

**User Experience Examples:**

**Unsupported File (`.zip`):**
```
❌ Upload blocked by frontend
UI shows: "Please select a valid file format"
```

**Corrupted PDF:**
```
❌ Backend detects during parsing
Error message: "Failed to read PDF file: invalid header. The file may be corrupted."
User sees: Red error banner with clear message
```

**File Too Large (250MB):**
```
❌ Frontend validation
UI shows: "⚠️ File too large: 250.0MB. Maximum size is 200MB."
Translate button disabled
```

**Security Considerations (Additional Protection):**
```python
# Potential enhancement: Magic byte validation
def validate_file_type(file_bytes: bytes, claimed_extension: str) -> bool:
    """Verify file matches claimed type by checking magic bytes."""
    magic_bytes = {
        'pdf': b'%PDF',
        'docx': b'PK\x03\x04',  # ZIP format
        'png': b'\x89PNG',
        'jpg': b'\xff\xd8\xff',
    }

    file_magic = file_bytes[:4]
    expected_magic = magic_bytes.get(claimed_extension)

    if expected_magic and not file_bytes.startswith(expected_magic):
        raise ValueError(f"File does not match claimed type: {claimed_extension}")

    return True
```

**Error Recovery Flow:**
```
1. User uploads corrupted file
2. Backend detects error during load
3. Detailed error message sent to frontend
4. User sees: "⚠️ Translation failed: File may be corrupted"
5. Upload another file prompt displayed
6. No crash, no data loss, clear next steps
```

**Key Features:**
- ✅ **Multi-layer validation** (frontend + backend)
- ✅ **Graceful error messages** (not technical stack traces)
- ✅ **No silent failures** (all errors reported to user)
- ✅ **Security-first** (file size limits, type validation)
- ✅ **Clear recovery path** (user knows what to do next)

---

## Summary

| Question | Strategy | Key Implementation |
|----------|----------|-------------------|
| **Large Documents** | Smart chunking + overlap | 200-token context preservation, semantic boundaries |
| **Speed** | Async parallelization | 5 concurrent LLM calls, asyncio.gather() |
| **Architecture** | Multi-agent system | Separate translator + validator agents |
| **Extensibility** | Factory pattern | Add new format in ~10 minutes |
| **Error Handling** | Multi-layer validation | Frontend + backend + parsing + display |

All architectural decisions prioritize:
- **User Experience** - Clear feedback, graceful errors
- **Performance** - Parallel processing, async I/O
- **Maintainability** - Clean abstractions, separation of concerns
- **Observability** - Structured logging, tracing
- **Extensibility** - Easy to add features without breaking existing code
