import base64
import json
import os
import secrets
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _key() -> bytes:
    value = os.environ.get("SESSION_ENCRYPTION_KEY", "")
    try:
        key = base64.b64decode(value, validate=True)
    except Exception as error:
        raise RuntimeError("SESSION_ENCRYPTION_KEY must be a base64-encoded 32-byte key.") from error
    if len(key) != 32:
        raise RuntimeError("SESSION_ENCRYPTION_KEY must be a base64-encoded 32-byte key.")
    return key


def encrypt_json(value: Any) -> str:
    """Encode the same nonce/tag/ciphertext layout used by the previous Node API."""
    nonce = secrets.token_bytes(12)
    encrypted = AESGCM(_key()).encrypt(nonce, json.dumps(value, separators=(",", ":")).encode(), None)
    ciphertext, tag = encrypted[:-16], encrypted[-16:]
    return base64.b64encode(nonce + tag + ciphertext).decode("ascii")


def decrypt_json(encoded: str) -> Any:
    try:
        data = base64.b64decode(encoded, validate=True)
        if len(data) < 29:
            raise ValueError("encrypted value is too short")
        nonce, tag, ciphertext = data[:12], data[12:28], data[28:]
        return json.loads(AESGCM(_key()).decrypt(nonce, ciphertext + tag, None))
    except RuntimeError:
        raise
    except Exception as error:
        raise ValueError("Unable to decrypt saved Instagram state.") from error
