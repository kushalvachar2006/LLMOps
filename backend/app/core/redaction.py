"""Best-effort scrubbing of text before it is stored.

This catches common patterns only. It cannot guarantee that all personal data is removed, which is
why prompt/response storage is OFF by default.
"""
import re

_PATTERNS = [
    (re.compile(r"\b[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,5}\b"), "[email]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.I), "Bearer [redacted]"),
    (re.compile(r"\b(?:sk|pk|rk|AIza|ghp|xox[abp])[-_A-Za-z0-9]{12,}\b"), "[api-key]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[card-number]"),
    (re.compile(r"(?<!\w)\+?\d[\d\s().-]{8,}\d\b"), "[phone]"),
]


def redact(text: str | None, enabled: bool = True) -> str | None:
    if text is None or not enabled:
        return text
    for pattern, label in _PATTERNS:
        text = pattern.sub(label, text)
    return text
