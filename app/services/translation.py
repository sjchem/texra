

from openai import OpenAI

client = OpenAI()

def translate_text(text: str, target_lang: str) -> str:
    resp = client.responses.create(
        model="gpt-4.1-mini",
        input=f"Translate the following text to {target_lang}:\n{text}"
    )
    return resp.output_text
