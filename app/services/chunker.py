

def chunk_text(text: str, max_chars=2000) -> list[str]:
    chunks, current = [], ""
    for para in text.split("\n\n"):
        if len(current) + len(para) < max_chars:
            current += para + "\n\n"
        else:
            chunks.append(current)
            current = para + "\n\n"
    if current:
        chunks.append(current)
    return chunks
