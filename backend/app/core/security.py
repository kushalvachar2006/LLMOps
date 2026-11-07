"""API-key generation and verification.

Keys look like  llmops_<12 hex id>_<43 char random secret>.  Only a keyed hash (HMAC-SHA256) of the
secret part is stored. The full key is shown once, at creation, and can never be recovered.
The 256-bit random secret makes a fast hash safe here (it cannot be guessed or brute-forced).
"""
import hashlib
import hmac
import re
import secrets

KEY_RE = re.compile(r"^llmops_([0-9a-f]{12})_([A-Za-z0-9_-]{43})$")


def generate_api_key() -> tuple[str, str, str]:
    """Return (key_id, secret, full_token)."""
    key_id = secrets.token_hex(6)
    secret = secrets.token_urlsafe(32)
    return key_id, secret, f"llmops_{key_id}_{secret}"


def hash_secret(secret: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), secret.encode(), hashlib.sha256).hexdigest()


def parse_token(token: str | None) -> tuple[str, str] | None:
    match = KEY_RE.match(token or "")
    return (match.group(1), match.group(2)) if match else None


def verify_secret(secret: str, pepper: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(secret, pepper), stored_hash)


def admin_token_ok(provided: str | None, expected: str) -> bool:
    return hmac.compare_digest((provided or "").encode(), expected.encode())
