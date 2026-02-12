

import os

from dotenv import load_dotenv
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    print("⚠️ OPENAI_API_KEY is not set")

import tempfile
import shutil
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.orchestrator import TranslationOrchestrator
from app.core.logging import setup_logging

setup_logging()

app = FastAPI()

def _get_output_filename(input_filename: str, output_format: str) -> str:
    """Generate output filename based on format."""
    base_name = input_filename.rsplit('.', 1)[0]
    ext_map = {
        "PDF": "pdf",
        "DOCX": "docx",
        "PPTX": "pptx"
    }
    ext = ext_map.get(output_format, "pdf")
    return f"translated_{base_name}.{ext}"

@app.websocket("/ws/translate")
async def translate_pdf_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        # First message should be metadata (filename, target_language, output_format)
        metadata_str = await websocket.receive_text()
        metadata = json.loads(metadata_str)
        filename = metadata.get("filename")
        target_language = metadata.get("target_language")
        output_format = metadata.get("output_format", "PDF")  # Default to PDF

        # Second message is the file content
        pdf_bytes = await websocket.receive_bytes()

        async def progress_callback(progress: int):
            await websocket.send_json({"type": "progress", "value": progress})

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, filename)
            with open(input_path, "wb") as f:
                f.write(pdf_bytes)

            orchestrator = TranslationOrchestrator()

            # Enable validation by default (can be disabled via metadata)
            enable_validation = metadata.get("enable_validation", True)

            output_path = await orchestrator.translate(
                input_path, target_language, progress_callback, output_format, enable_validation
            )

            # Get validation summary
            validation_summary = orchestrator.get_validation_summary()

            # Log validation summary for debugging
            print(f"\n📊 Validation Summary: {validation_summary}\n")

            with open(output_path, "rb") as f:
                output_pdf_bytes = f.read()

            # Determine output filename based on format
            output_filename = _get_output_filename(filename, output_format)

            # Send validation results first
            await websocket.send_json({
                "type": "validation",
                "summary": validation_summary
            })
            print(f"✓ Sent validation summary to client")

            # Send the translated file
            await websocket.send_json({"type": "file", "filename": output_filename})
            await websocket.send_bytes(output_pdf_bytes)

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"An error occurred: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        pass

@app.get("/health")
def health():
    return {"status": "ok"}
