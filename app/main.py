

from fastapi import FastAPI, UploadFile, Form
from services import pdf_loader, chunker, translation, pdf_writer

app = FastAPI()

@app.post("/translate")
async def translate_pdf(
    file: UploadFile,
    target_language: str = Form(...)
):
    pdf_bytes = await file.read()
    pages = pdf_loader.load_pdf(pdf_bytes)

    translated_pages = []
    for page in pages:
        chunks = chunker.chunk_text(page)
        translated = [translation.translate_text(c, target_language) for c in chunks]
        translated_pages.append("".join(translated))

    output_pdf = pdf_writer.build_pdf(translated_pages)

    return Response(output_pdf, media_type="application/pdf")
