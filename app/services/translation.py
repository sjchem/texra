


import asyncio
import time
from agents import Runner
from app.agents.translator import translator_agent
from app.core.logging import get_logger

logger = get_logger("TranslatorService")

_TRANSLATION_SEMAPHORE = asyncio.Semaphore(5)


async def translate_text(text: str, target_lang: str) -> str:
    start = time.time()

    async with _TRANSLATION_SEMAPHORE:
        result = await Runner.run(
            translator_agent,
            input=f"Target language: {target_lang}\n\nText:\n{text}"
        )

    logger.info(
        f"Translation completed in {time.time() - start:.2f}s "
        f"(chars={len(text)})"
    )

    return result.final_output
