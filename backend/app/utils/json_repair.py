"""Small LLM-output repair kit.

Local 3B models happily emit ```json fences, trailing commas and single quotes.
Rather than retrying (slow, costs tokens) we repair first and only retry if the
repair fails.
"""
import json
import re
from typing import Any, Dict, Optional

FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def _strip_fences(raw: str) -> str:
    match = FENCE.search(raw)
    return match.group(1) if match else raw


def _balanced_slice(raw: str) -> Optional[str]:
    """Grab the first balanced {...} block, ignoring braces inside strings."""
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(raw)):
        ch = raw[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]
    return None


def extract_json(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None

    candidate = _strip_fences(raw).strip()
    for attempt in (candidate, _balanced_slice(candidate) or ""):
        if not attempt:
            continue
        for repaired in (attempt, _repair(attempt)):
            try:
                value = json.loads(repaired)
                if isinstance(value, dict):
                    return value
            except (json.JSONDecodeError, TypeError):
                continue
    return None


def _repair(text: str) -> str:
    text = re.sub(r",\s*([}\]])", r"\1", text)          # trailing commas
    text = re.sub(r"'([^'\"]*)'\s*:", r'"\1":', text)    # single-quoted keys
    text = re.sub(r":\s*'([^']*)'", r': "\1"', text)     # single-quoted values
    text = text.replace("None", "null").replace("True", "true").replace("False", "false")
    text = re.sub(r"\bNaN\b", "null", text)
    return text
