import json
import logging
import re
from collections.abc import Callable

from .llm_client import call_with_retries
from .resources import read_prompt_text

CODE_FENCE_OPEN_RE = re.compile(r"^```(?:json)?\s*", flags=re.IGNORECASE)
CODE_FENCE_CLOSE_RE = re.compile(r"\s*```$")


def extract_json_array(text: str) -> list[str]:
    stripped = text.strip()
    stripped = CODE_FENCE_OPEN_RE.sub("", stripped)
    stripped = CODE_FENCE_CLOSE_RE.sub("", stripped)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if isinstance(item, str) and item.strip()]


def dedup_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def expand_query(
    question: str,
    num_variants: int,
    prompt_path: str | None,
    llm: Callable[[str], str],
) -> list[str]:
    template = read_prompt_text(prompt_path, default_filename="multi_query.txt")
    prompt = template.format(question=question, num_variants=num_variants)
    raw = call_with_retries(prompt, llm)

    variants = extract_json_array(raw)
    if not variants:
        logging.warning("Multi-query expansion returned no parseable variants; falling back to question only")
        return [question]

    if variants[0].strip() != question.strip():
        variants = [question, *variants]

    return dedup_preserve_order(variants)[:num_variants]
