"""
Symmetric encryption for sensitive settings (e.g. SMTP password).

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` package.
The encryption key is derived from the application SECRET_KEY via SHA-256 so
that it is always 32 bytes regardless of the SECRET_KEY length.

Backward-compat note: the previous XOR+Base64 scheme never produced valid
Fernet tokens (they start with "gAAAAA").  Any stored value that does *not*
begin with "gAAAAA" is treated as plaintext so existing rows are not lost on
first decryption after the upgrade.
"""

import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _get_fernet() -> Fernet:
    """Derive a stable Fernet key from the application SECRET_KEY."""
    secret = current_app.config.get("SECRET_KEY") or ""
    if not secret:
        raise RuntimeError("SECRET_KEY is not configured – cannot encrypt/decrypt values.")
    # SHA-256 gives us exactly 32 bytes; base64-url-encode as Fernet requires
    raw_key = hashlib.sha256(secret.encode("utf-8")).digest()
    import base64
    fernet_key = base64.urlsafe_b64encode(raw_key)
    return Fernet(fernet_key)


def encrypt_value(value: str) -> str:
    """Encrypt *value* with Fernet and return a base64url token string.

    Returns an empty string for empty input.
    """
    if not value:
        return ""
    f = _get_fernet()
    return f.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_value(value: str) -> str:
    """Decrypt a Fernet token produced by :func:`encrypt_value`.

    * Empty input → empty string.
    * Valid Fernet token → decrypted plaintext.
    * Anything else (legacy XOR ciphertext or raw plaintext) → raises
      :class:`ValueError` so callers can handle the error explicitly instead of
      silently returning corrupt data.
    """
    if not value:
        return ""
    f = _get_fernet()
    try:
        return f.decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, Exception) as exc:
        raise ValueError(
            "Failed to decrypt stored value – the SECRET_KEY may have changed "
            "or the stored value is not a valid Fernet token."
        ) from exc
