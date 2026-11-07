"""Prompt templates use {{field}} placeholders. Rendering is plain text substitution only
(no code execution), so a template cannot run anything."""
import re

from app.core.errors import ValidationAppError

_VAR = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def extract_variables(template: str) -> list[str]:
    seen: list[str] = []
    for name in _VAR.findall(template):
        if name not in seen:
            seen.append(name)
    return seen


def render(template: str, row: dict) -> str:
    def sub(match: re.Match) -> str:
        name = match.group(1)
        if name not in row:
            raise ValidationAppError(f"Template field '{name}' is missing from the data row.")
        value = row[name]
        return "" if value is None else str(value)

    return _VAR.sub(sub, template)
