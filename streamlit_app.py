import streamlit as st
import asyncio
import websockets
import json
import queue
import threading
import time
import base64
import html
import os
import tempfile
from pathlib import Path

from app.services.format_converter import FormatConverter

# =================================================
# SESSION STATE (ALL DEFINED ONCE)
# =================================================
if "msg_queue" not in st.session_state:
    st.session_state.msg_queue = queue.Queue()

if "job_running" not in st.session_state:
    st.session_state.job_running = False

if "progress" not in st.session_state:
    st.session_state.progress = 0

if "status" not in st.session_state:
    st.session_state.status = ""

if "file_bytes" not in st.session_state:
    st.session_state.file_bytes = None

if "output_filename" not in st.session_state:
    st.session_state.output_filename = None

if "workflow_started" not in st.session_state:
    st.session_state.workflow_started = False

if "validation_summary" not in st.session_state:
    st.session_state.validation_summary = None

if "input_file_bytes" not in st.session_state:
    st.session_state.input_file_bytes = None

if "input_filename" not in st.session_state:
    st.session_state.input_filename = None


# =================================================
# HELPERS
# =================================================
def _get_mime_type(filename: str | None) -> str:
    if not filename:
        return "application/octet-stream"

    ext = Path(filename).suffix.lower()
    mapping = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    return mapping.get(ext, "application/octet-stream")


def _convert_office_bytes_to_pdf(file_bytes: bytes, suffix: str) -> bytes | None:
    converter_map = {
        ".docx": FormatConverter.docx_to_pdf,
        ".pptx": FormatConverter.pptx_to_pdf,
        ".odt": FormatConverter.odt_to_pdf,
    }

    converter = converter_map.get(suffix.lower())
    if converter is None:
        return None

    input_path = None
    pdf_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_bytes)
            input_path = tmp.name

        pdf_path = converter(input_path)
        with open(pdf_path, "rb") as f:
            return f.read()
    except Exception as exc:
        print(f"⚠️ Preview conversion failed ({suffix}): {exc}")
        return None
    finally:
        if input_path and os.path.exists(input_path):
            os.unlink(input_path)
        if pdf_path and os.path.exists(pdf_path) and pdf_path != input_path:
            os.unlink(pdf_path)


def _prepare_preview_payload(file_bytes: bytes | None, filename: str | None) -> dict | None:
    if not file_bytes or not filename:
        return None

    ext = Path(filename).suffix.lower()
    image_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}

    if ext in image_exts:
        mime = "image/jpeg" if ext in {".jpg", ".jpeg"} else f"image/{ext.lstrip('.')}"
        return {"type": "image", "bytes": file_bytes, "mime": mime}

    if ext == ".pdf":
        return {"type": "pdf", "bytes": file_bytes}

    if ext in {".docx", ".pptx", ".odt"}:
        pdf_bytes = _convert_office_bytes_to_pdf(file_bytes, ext)
        if pdf_bytes:
            return {"type": "pdf", "bytes": pdf_bytes}
        return {"type": "text", "text": "Preview unavailable for this document."}

    try:
        text = file_bytes.decode("utf-8", errors="ignore")
        snippet = text.strip()[:5000]
        if snippet:
            return {"type": "text", "text": snippet}
    except Exception:
        pass

    return None

# =================================================
# DRAIN QUEUE  (thread-safe → session state)
# =================================================
def _drain_queue():
    """Read every pending message the background thread pushed
    and apply it to session state (runs on the Streamlit thread)."""
    q = st.session_state.msg_queue
    while not q.empty():
        try:
            msg = q.get_nowait()
        except queue.Empty:
            break
        kind = msg["type"]
        if kind == "progress":
            st.session_state.progress = msg["value"]
            st.session_state.status = msg["status"]
        elif kind == "validation":
            st.session_state.validation_summary = msg["summary"]
            print(f"📊 Received validation summary: {msg['summary']}")  # Debug
        elif kind == "file":
            st.session_state.file_bytes = msg["bytes"]
            st.session_state.output_filename = msg["filename"]
            st.session_state.status = "Translation complete ✓"
            st.session_state.progress = 100
        elif kind == "error":
            st.session_state.status = f"Error: {msg['message']}"
        elif kind == "done":
            st.session_state.job_running = False


# =================================================
# ASYNC TRANSLATION (RUNS IN THREAD EVENT LOOP)
# =================================================
async def _translate_ws(file_bytes: bytes, filename: str, language: str, output_format: str, q: queue.Queue):
    """Run the WebSocket translation and push messages to *q*."""
    try:
        uri = "ws://127.0.0.1:8000/ws/translate"
        async with websockets.connect(uri, max_size=50 * 1024 * 1024) as ws:
            await ws.send(json.dumps({
                "filename": filename,
                "target_language": language,
                "output_format": output_format,
            }))
            await ws.send(file_bytes)

            while True:
                msg = await ws.recv()
                if isinstance(msg, str):
                    data = json.loads(msg)

                    if data["type"] == "progress":
                        q.put({
                            "type": "progress",
                            "value": data["value"],
                            "status": f"Translating… {data['value']}%",
                        })

                    elif data["type"] == "validation":
                        q.put({
                            "type": "validation",
                            "summary": data["summary"],
                        })

                    elif data["type"] == "file":
                        pdf_bytes = await ws.recv()
                        q.put({
                            "type": "file",
                            "bytes": pdf_bytes,
                            "filename": data["filename"],
                        })
                        break

                    elif data["type"] == "error":
                        q.put({"type": "error", "message": data["message"]})
                        break
    except Exception as e:
        q.put({"type": "error", "message": str(e)})
    finally:
        q.put({"type": "done"})


def _run_in_thread(file_bytes: bytes, filename: str, language: str, output_format: str, q: queue.Queue):
    asyncio.run(_translate_ws(file_bytes, filename, language, output_format, q))


_drain_queue()

# =================================================
# PAGE CONFIG
# =================================================
st.set_page_config(
    page_title="STARK TRANSLATOR",
    page_icon="⭕",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =================================================
# STYLES - Stark Future Brand
# =================================================
st.markdown(
    """
    <style>
        /* Dark theme - Stark Future Brand */
        .stApp {
            background-color: #050505;
        }

        /* Hide default Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background-color: #050505;
            border-right: 2px solid #c9a961;
            padding-top: 1rem;
        }

        [data-testid="stSidebar"] .stMarkdown {
            color: #e0e0e0 !important;
            margin-bottom: 0.5rem;
        }

        /* Custom logo */
        .stark-logo {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            border: 8px solid transparent;
            background: linear-gradient(#050505, #050505) padding-box,
                    linear-gradient(135deg, #e5c17c 0%, #c9a961 50%, #8b7355 100%) border-box;
            box-shadow: 0 0 20px rgba(201, 169, 97, 0.3);
            margin: 5px auto 10px auto;
        }

        .stark-title {
            font-size: 32px;
            font-weight: 700;
            letter-spacing: 3px;
            background: linear-gradient(135deg, #d4af37 0%, #c9a961 50%, #8b7355 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-align: center;
            margin-bottom: 15px;
            margin-top: 0;
            text-shadow: 0 2px 10px rgba(201, 169, 97, 0.2);
        }

        /* Main area title */
        .main-title {
            font-size: 36px;
            font-weight: 700;
            letter-spacing: 6px;
            background: linear-gradient(135deg, #d4af37 0%, #c9a961 50%, #8b7355 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 20px;
            text-shadow: 0 2px 10px rgba(201, 169, 97, 0.2);
        }

        /* Asset category cards */
        .asset-card {
            background: #0a0a0a;
            border: 2px solid #c9a961;
            border-radius: 12px;
            padding: 40px 30px;
            text-align: center;
            min-height: 280px;
            transition: all 0.3s ease;
            margin: 10px;
        }

        .asset-card:hover {
            border-color: #d4af37;
            box-shadow: 0 0 30px rgba(201, 169, 97, 0.3);
            transform: translateY(-5px);
        }

        .asset-card-title {
            font-size: 20px;
            font-weight: 700;
            letter-spacing: 2px;
            color: #c9a961;
            margin-bottom: 25px;
            text-transform: uppercase;
        }

        .asset-card-formats {
            font-size: 20px;
            color: #e0e0e0;
            margin-bottom: 15px;
            line-height: 1.8;
            font-weight: 500;
        }

        .asset-card-description {
            font-size: 14px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 20px;
        }

        /* System status */
        .system-status {
            position: fixed;
            bottom: 20px;
            right: 20px;
            font-size: 11px;
            color: #666;
            letter-spacing: 2px;
            text-transform: uppercase;
        }

        .version-info {
            position: fixed;
            bottom: 20px;
            left: 20px;
            font-size: 11px;
            color: #666;
            letter-spacing: 2px;
            text-transform: uppercase;
        }

        /* Button styling */
        .stButton>button {
            background: #c9a961;
            color: #050505;
            font-weight: 700;
            border: none;
            border-radius: 8px;
            padding: 16px 50px;
            font-size: 18px;
            letter-spacing: 2px;
            transition: all 0.3s ease;
            text-transform: uppercase;
        }

        .stButton>button:hover {
            background: #d4af37;
            box-shadow: 0 0 25px rgba(201, 169, 97, 0.5);
            transform: translateY(-2px);
        }

        .stButton>button:disabled {
            background: #333;
            color: #666;
        }

        /* Download button */
        .stDownloadButton>button {
            background: #c9a961;
            color: #050505;
            font-weight: 700;
            border: none;
            border-radius: 8px;
            padding: 12px 30px;
            transition: all 0.3s ease;
            letter-spacing: 1px;
        }

        .stDownloadButton>button:hover {
            background: #d4af37;
            box-shadow: 0 0 20px rgba(201, 169, 97, 0.4);
        }

        /* Text and labels */
        label, .stMarkdown {
            color: #e0e0e0 !important;
        }

        /* Progress bar */
        .stProgress > div > div {
            background-color: #c9a961;
        }

        /* File uploader */
        .stFileUploader {
            border: 2px solid #c9a961;
            border-radius: 8px;
            padding: 15px;
            background-color: #0a0a0a;
            margin-bottom: 10px;
        }

        /* Select box */
        .stSelectbox > div > div {
            background-color: #0a0a0a;
            border: 1px solid #c9a961;
            color: #e0e0e0;
        }

        /* Preview container */
        .preview-container {
            border: 2px solid #c9a961;
            border-radius: 8px;
            padding: 20px;
            background-color: #0a0a0a;
            min-height: 680px;
            max-height: 680px;
            overflow: hidden;
        }

        .preview-title {
            font-size: 18px;
            font-weight: 700;
            color: #c9a961;
            margin-bottom: 15px;
            letter-spacing: 2px;
            text-transform: uppercase;
        }

        /* Info box */
        .stAlert {
            background-color: #0a0a0a;
            border: 2px solid #c9a961;
            color: #e0e0e0;
        }

        /* Section divider */
        .section-divider {
            border-top: 1px solid #333;
            margin: 40px 0;
        }

        /* Welcome page centered layout */
        .welcome-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 80vh;
            padding: 40px;
        }

        .welcome-logo {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            border: 10px solid transparent;
            background: linear-gradient(#050505, #050505) padding-box,
                    linear-gradient(135deg, #e5c17c 0%, #c9a961 50%, #8b7355 100%) border-box;
            box-shadow: 0 0 30px rgba(201, 169, 97, 0.5);
            margin: 0 auto 30px auto;
        }

        .welcome-title {
            font-size: 48px;
            font-weight: 700;
            letter-spacing: 8px;
            background: linear-gradient(135deg, #d4af37 0%, #c9a961 50%, #8b7355 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-align: center;
            margin-bottom: 60px;
            text-shadow: 0 2px 10px rgba(201, 169, 97, 0.2);
        }

        /* Clickable cards */
        .asset-card {
            cursor: pointer;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# =================================================
# SIDEBAR - Input Controls (Only show when workflow started)
# =================================================
if st.session_state.workflow_started:
    with st.sidebar:
        # Stark logo
        st.markdown(
            """
            <div class="stark-logo"></div>
            <h1 class="stark-title">STARK TRANSLATOR</h1>
            """,
            unsafe_allow_html=True
        )

        st.markdown("---")

        # File uploader with size limit
        uploaded_file = st.file_uploader(
            "📄 Upload Document or Image (Max 200MB)",
            type=["pdf", "docx", "odt", "txt", "pptx", "png", "jpg", "jpeg", "webp", "gif"],
            help="Select a document or image to translate (Maximum size: 200MB)"
        )

        current_file_bytes = None

        # Validate file size & store uploaded content for later preview/downloading
        if uploaded_file:
            current_file_bytes = uploaded_file.getvalue()
            st.session_state.input_file_bytes = current_file_bytes
            st.session_state.input_filename = uploaded_file.name

            file_size_mb = len(current_file_bytes) / (1024 * 1024)
            if file_size_mb > 200:
                st.error(f"⚠️ File too large: {file_size_mb:.1f}MB. Maximum size is 200MB.")
        # Target language
        target_language = st.selectbox(
            "🌍 Target Language",
            ("Spanish", "French", "English", "Portuguese", "Italian", "German", "Chinese", "Japanese"),
            help="Choose the language to translate to"
        )

        # Output format selection (dynamic based on input file)
        output_format = "PDF"  # Default
        if uploaded_file:
            file_ext = uploaded_file.name.split('.')[-1].lower()

            if file_ext == 'docx':
                output_format = st.selectbox(
                    "📤 Output Format",
                    ("DOCX (preserve formatting)", "PDF"),
                    help="Choose output format"
                )
                output_format = "DOCX" if "DOCX" in output_format else "PDF"
            elif file_ext == 'pptx':
                output_format = st.selectbox(
                    "📤 Output Format",
                    ("PPTX (preserve formatting)", "PDF"),
                    help="Choose output format"
                )
                output_format = "PPTX" if "PPTX" in output_format else "PDF"
            elif file_ext == 'odt':
                output_format = st.selectbox(
                    "📤 Output Format",
                    ("DOCX (Word)", "PDF"),
                    help="Choose output format"
                )
                output_format = "DOCX" if "DOCX" in output_format else "PDF"
            elif file_ext == 'pdf':
                st.info("📤 Output: PDF (formatting preserved)")
                output_format = "PDF"
            elif file_ext in ['png', 'jpg', 'jpeg', 'webp', 'gif']:
                st.info("📤 Output: PDF (OCR + Translation)")
                output_format = "PDF"
            else:  # txt and other text formats
                st.info("📤 Output: PDF")
                output_format = "PDF"

        st.markdown("---")

        # File info
        if uploaded_file:
            st.success(f"✓ {uploaded_file.name}")
            if st.session_state.input_file_bytes:
                st.info(f"📊 Size: {len(st.session_state.input_file_bytes) / 1024:.1f} KB")
        else:
            st.warning("⚠️ No file uploaded")

        st.markdown("---")
else:
    # Initialize variables when sidebar is hidden
    uploaded_file = None
    target_language = "Spanish"
    output_format = "PDF"

# =================================================
# MAIN AREA - Welcome Page or Translation Interface
# =================================================

if not st.session_state.workflow_started:
    # ============================================
    # WELCOME PAGE - Centered with Cards
    # ============================================
    st.markdown(
        """
        <div class="welcome-logo"></div>
        <h1 class="welcome-title">STARK TRANSLATOR</h1>
        """,
        unsafe_allow_html=True
    )

    # Three dashboard cards
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            """
            <div class="asset-card">
                <div class="asset-card-title">SMALL DOCUMENTS</div>
                <div class="asset-card-formats">
                    PDF, DOCX, ODT, PPTX, TXT (up to 20 pages)
                </div>
                <div class="asset-card-description">INSTANT TRANSLATION • MAX 50MB</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Start Translation →", key="card1", use_container_width=True):
            st.session_state.workflow_started = True
            st.rerun()

    with col2:
        st.markdown(
            """
            <div class="asset-card">
                <div class="asset-card-title">IMAGE/SCANNED DOCUMENT</div>
                <div class="asset-card-formats">
                    JPEG, PNG, GIF, WEBP
                </div>
                <div class="asset-card-description">OCR & TRANSLATE • MAX 50MB</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Start Translation →", key="card2", use_container_width=True):
            st.session_state.workflow_started = True
            st.rerun()

    with col3:
        st.markdown(
            """
            <div class="asset-card">
                <div class="asset-card-title">LARGE DOCUMENTS</div>
                <div class="asset-card-formats">
                    PDF, DOCX, ODT (20-200 pages)
                </div>
                <div class="asset-card-description">BATCH PROCESSING • MAX 200MB</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Start Translation →", key="card3", use_container_width=True):
            st.session_state.workflow_started = True
            st.rerun()

    # System status footer
    st.markdown(
        """
        <div class="system-status">SYSTEM READY</div>
        <div class="version-info">V1.0.0-ALPHA</div>
        """,
        unsafe_allow_html=True
    )

else:
    # ============================================
    # TRANSLATION INTERFACE - With Sidebar
    # ============================================

    # Header with title and back button
    header_col1, header_col2, header_col3 = st.columns([2, 1, 1])
    with header_col1:
        st.markdown('<h1 class="main-title">STARK TRANSLATOR</h1>', unsafe_allow_html=True)
    with header_col3:
        if st.button("⬅️ BACK TO HOME", key="back_top", use_container_width=True):
            st.session_state.workflow_started = False
            st.session_state.file_bytes = None
            st.session_state.output_filename = None
            st.session_state.progress = 0
            st.session_state.status = ""
            st.session_state.input_file_bytes = None
            st.session_state.input_filename = None
            st.rerun()

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # Translate button (prominent in main area)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        translate_clicked = st.button(
            "🔄 TRANSLATE",
            disabled=st.session_state.job_running or uploaded_file is None,
            use_container_width=True,
            type="primary"
        )

    # Progress section
    if st.session_state.job_running or st.session_state.progress > 0:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        progress_col1, progress_col2 = st.columns([4, 1])
        with progress_col1:
            progress_value = st.session_state.progress / 100.0
            st.progress(progress_value)
        with progress_col2:
            st.metric("Progress", f"{st.session_state.progress}%")

        if st.session_state.status:
            st.info(st.session_state.status)

    # =================================================
    # RESULT UI - Side-by-Side Preview with Download
    # =================================================
    if st.session_state.file_bytes:
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        # Header with download button
        header_col1, header_col2 = st.columns([3, 1])
        with header_col1:
            st.markdown('<div class="preview-title">📄 TRANSLATION RESULTS</div>', unsafe_allow_html=True)
        with header_col2:
            download_mime = _get_mime_type(st.session_state.output_filename)
            st.download_button(
                "⬇️ DOWNLOAD",
                data=st.session_state.file_bytes,
                file_name=st.session_state.output_filename,
                mime=download_mime,
                use_container_width=True,
            )

        original_preview = _prepare_preview_payload(
            st.session_state.get('input_file_bytes'),
            st.session_state.get('input_filename'),
        )
        translated_preview = _prepare_preview_payload(
            st.session_state.file_bytes,
            st.session_state.output_filename,
        )

        # Side-by-Side Preview
        left_col, right_col = st.columns(2)

        with left_col:
            st.markdown('<div class="preview-title">ORIGINAL DOCUMENT</div>', unsafe_allow_html=True)
            if original_preview:
                if original_preview['type'] == 'image':
                    img_base64 = base64.b64encode(original_preview['bytes']).decode('utf-8')
                    img_display_original = f'''
                        <div class="preview-container" style="padding: 10px; overflow: auto; display: flex; align-items: center; justify-content: center;">
                            <img
                                src="data:{original_preview['mime']};base64,{img_base64}"
                                style="max-width: 100%; max-height: 660px; object-fit: contain;">
                        </div>
                    '''
                    st.markdown(img_display_original, unsafe_allow_html=True)
                elif original_preview['type'] == 'pdf':
                    original_base64 = base64.b64encode(original_preview['bytes']).decode('utf-8')
                    pdf_display_original = f'''
                        <div class="preview-container" style="padding: 0; overflow: hidden;">
                            <iframe
                                src="data:application/pdf;base64,{original_base64}"
                                width="100%"
                                height="680"
                                type="application/pdf"
                                style="border: none; display: block;">
                            </iframe>
                        </div>
                    '''
                    st.markdown(pdf_display_original, unsafe_allow_html=True)
                else:
                    text_html = f"""
                        <div class='preview-container' style='overflow:auto;'>
                            <pre style='white-space: pre-wrap; font-family: monospace; color: #e0e0e0;'>{html.escape(original_preview['text'])}</pre>
                        </div>
                    """
                    st.markdown(text_html, unsafe_allow_html=True)
            else:
                st.markdown(
                    """
                    <div class="preview-container">
                        <div style="text-align: center; padding: 50px; color: #666;">
                            <div style="font-size: 48px; margin-bottom: 20px;">📄</div>
                            <div style="font-size: 16px; letter-spacing: 2px;">NO DOCUMENT</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        with right_col:
            st.markdown('<div class="preview-title">TRANSLATED DOCUMENT</div>', unsafe_allow_html=True)

            if translated_preview and translated_preview['type'] == 'pdf':
                base64_pdf = base64.b64encode(translated_preview['bytes']).decode('utf-8')
                pdf_display = f'''
                    <div class="preview-container" style="padding: 0; overflow: hidden;">
                        <iframe
                            src="data:application/pdf;base64,{base64_pdf}"
                            width="100%"
                            height="680"
                            type="application/pdf"
                            style="border: none; display: block;">
                        </iframe>
                    </div>
                '''
                st.markdown(pdf_display, unsafe_allow_html=True)
            elif translated_preview and translated_preview['type'] == 'image':
                img_base64 = base64.b64encode(translated_preview['bytes']).decode('utf-8')
                img_display_translated = f'''
                    <div class="preview-container" style="padding: 10px; overflow: auto; display: flex; align-items: center; justify-content: center;">
                        <img
                            src="data:{translated_preview['mime']};base64,{img_base64}"
                            style="max-width: 100%; max-height: 660px; object-fit: contain;">
                    </div>
                '''
                st.markdown(img_display_translated, unsafe_allow_html=True)
            elif translated_preview and translated_preview['type'] == 'text':
                text_html = f"""
                    <div class='preview-container' style='overflow:auto;'>
                        <pre style='white-space: pre-wrap; font-family: monospace; color: #e0e0e0;'>{html.escape(translated_preview['text'])}</pre>
                    </div>
                """
                st.markdown(text_html, unsafe_allow_html=True)
            else:
                st.markdown(
                    """
                    <div class="preview-container">
                        <div style="text-align: center; padding: 50px; color: #666;">
                            <div style="font-size: 48px; margin-bottom: 20px;">🕒</div>
                            <div style="font-size: 16px; letter-spacing: 2px;">PREVIEW UNAVAILABLE</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # Additional info and reset button
        info_col1, info_col2, info_col3 = st.columns([1, 1, 1])
        with info_col1:
            st.info(f"📊 File: {st.session_state.output_filename}")
        with info_col2:
            st.info(f"📏 Size: {len(st.session_state.file_bytes) / 1024:.1f} KB")
        with info_col3:
            if st.button("🔄 Translate Another", use_container_width=True):
                st.session_state.file_bytes = None
                st.session_state.output_filename = None
                st.session_state.progress = 0
                st.session_state.status = ""
                st.session_state.validation_summary = None
                st.session_state.input_file_bytes = None
                st.session_state.input_filename = None
                st.rerun()

        # Quality Validation Summary (displayed below document viewers)
        if hasattr(st.session_state, 'validation_summary') and st.session_state.validation_summary:
            validation = st.session_state.validation_summary

            if validation.get('validation_enabled', False) and validation.get('chunks_validated', 0) > 0:
                st.markdown('<div style="margin-top: 30px;"></div>', unsafe_allow_html=True)

                quality_score = validation.get('average_quality_score', 0)
                assessment = validation.get('assessment', 'N/A')
                recommendation = validation.get('recommendation', 'review')
                total_issues = validation.get('total_issues', 0)
                high_severity = validation.get('high_severity_issues', 0)

                # Color based on quality score
                if quality_score >= 90:
                    color = "#4CAF50"  # Green
                    icon = "✅"
                elif quality_score >= 75:
                    color = "#FFC107"  # Yellow/Gold
                    icon = "✓"
                elif quality_score >= 60:
                    color = "#FF9800"  # Orange
                    icon = "⚠️"
                else:
                    color = "#F44336"  # Red
                    icon = "❌"

                # Display validation header
                st.markdown(
                    f'<div style="text-align: center; margin-bottom: 20px;"><h2 style="color: #d4af37; font-size: 28px; letter-spacing: 2px;">📊 QUALITY VALIDATION REPORT</h2></div>',
                    unsafe_allow_html=True
                )

                # Three column layout for metrics
                metric_col1, metric_col2, metric_col3 = st.columns(3)

                with metric_col1:
                    st.markdown(
                        f"""
                        <div style="background: linear-gradient(135deg, rgba(212, 175, 55, 0.1), rgba(0, 0, 0, 0.3));
                                    border: 2px solid {color}; border-radius: 15px; padding: 25px; text-align: center;
                                    min-height: 260px; height: 260px; display: flex; flex-direction: column; justify-content: center;">
                            <div style="font-size: 48px; margin-bottom: 10px;">{icon}</div>
                            <div style="color: {color}; font-size: 42px; font-weight: bold; margin-bottom: 5px;">{quality_score}</div>
                            <div style="color: #888; font-size: 14px; margin-bottom: 10px;">out of 100</div>
                            <div style="color: {color}; font-size: 18px; font-weight: bold;">{assessment}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with metric_col2:
                    st.markdown(
                        f"""
                        <div style="background: linear-gradient(135deg, rgba(212, 175, 55, 0.1), rgba(0, 0, 0, 0.3));
                                    border: 2px solid #d4af37; border-radius: 15px; padding: 25px; text-align: center;
                                    min-height: 260px; height: 260px; display: flex; flex-direction: column; justify-content: center;">
                            <div style="color: #d4af37; font-size: 14px; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 1px;">Total Issues</div>
                            <div style="color: white; font-size: 48px; font-weight: bold; margin-bottom: 10px;">{total_issues}</div>
                            <div style="color: #d4af37; font-size: 14px; text-transform: uppercase; margin-bottom: 5px; letter-spacing: 1px;">High Severity</div>
                            <div style="color: {'#F44336' if high_severity > 0 else '#4CAF50'}; font-size: 32px; font-weight: bold;">{high_severity}</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                with metric_col3:
                    rec_color = "#4CAF50" if recommendation == "pass" else "#FF9800" if recommendation == "review" else "#F44336"
                    rec_icon = "✅" if recommendation == "pass" else "⚠️" if recommendation == "review" else "❌"
                    st.markdown(
                        f"""
                        <div style="background: linear-gradient(135deg, rgba(212, 175, 55, 0.1), rgba(0, 0, 0, 0.3));
                                    border: 2px solid {rec_color}; border-radius: 15px; padding: 25px; text-align: center;
                                    min-height: 260px; height: 260px; display: flex; flex-direction: column; justify-content: center;">
                            <div style="color: #d4af37; font-size: 14px; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 1px;">Recommendation</div>
                            <div style="font-size: 64px; margin: 20px 0;">{rec_icon}</div>
                            <div style="color: {rec_color}; font-size: 24px; font-weight: bold; text-transform: uppercase; letter-spacing: 2px;">{recommendation}</div>
                            <div style="color: #888; font-size: 12px; margin-top: 10px;">Based on {validation.get('chunks_validated', 0)} samples</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

    elif not st.session_state.job_running and uploaded_file:
        # Show placeholder when file is uploaded but not translated yet
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.info("👆 Click the **TRANSLATE** button above to begin translation.")

    # =================================================
    # TRANSLATE BUTTON LOGIC (Inside workflow_started block)
    # =================================================
    if translate_clicked:
        file_content = st.session_state.get('input_file_bytes')
        file_name = st.session_state.get('input_filename')

        if not file_content or not file_name:
            st.error("⚠️ Unable to read the uploaded file. Please upload again.")
            st.stop()

        # Reset state
        st.session_state.progress = 0
        st.session_state.status = "Starting translation…"
        st.session_state.file_bytes = None
        st.session_state.output_filename = None
        st.session_state.job_running = True

        t = threading.Thread(
            target=_run_in_thread,
            args=(file_content, file_name, target_language, output_format, st.session_state.msg_queue),
            daemon=True,
        )
        t.start()
        st.rerun()  # immediately start the polling cycle


# =================================================
# POLLING RERUN  — keeps the UI responsive while the
# background thread is working.  After the "done"
# message is drained above, job_running becomes False
# and we stop polling (the page will show the result).
# =================================================
if st.session_state.job_running:
    time.sleep(0.5)
    st.rerun()
