

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io

def build_pdf(pages: list[str]) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    for page in pages:
        text_obj = c.beginText(40, 800)
        for line in page.split("\n"):
            text_obj.textLine(line)
        c.drawText(text_obj)
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.read()
