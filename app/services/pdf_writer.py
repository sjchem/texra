"""Standalone helper – delegates to the main PdfWriter."""

from app.services.writer import PdfWriter


def build_pdf(pages: list[str]) -> str:
    writer = PdfWriter()
    return writer.write(pages, "output.pdf")
