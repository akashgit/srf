"""Extract fenced code blocks from LLM output."""

from __future__ import annotations

import re

import structlog

logger = structlog.get_logger()


def extract_code_block(text: str) -> str:
    """Extract the first fenced code block from text.

    Handles ```python, ```, and bare code. Returns the code content
    without the fence markers.
    """
    pattern = r"```(?:python)?\s*\n(.*?)```"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    if text.strip().startswith("def ") or text.strip().startswith("import "):
        return text.strip()
    logger.warning("code_parsing.no_block_found", text_length=len(text))
    return text.strip()
