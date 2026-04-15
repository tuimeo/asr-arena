"""
Symmetric encryption for API keys stored in browser localStorage.

Uses Fernet (AES-128-CBC + HMAC-SHA256). The encryption key can be
configured via ENCRYPTION_KEY in .env, otherwise a hardcoded default is used.

IMPORTANT: The default key is public (in source code). For production
deployments, always set a custom ENCRYPTION_KEY in .env.
"""

import os

from cryptography.fernet import Fernet, InvalidToken

_ENV_KEY = os.getenv("ENCRYPTION_KEY", "")


def _get_fernet() -> Fernet:
    key = _ENV_KEY if _ENV_KEY else None
    if not key:
        # Generate a deterministic Fernet key from the default passphrase
        import hashlib
        import base64
        raw = hashlib.sha256(b"asr_compare_default_encryption_key_2026").digest()
        key = base64.urlsafe_b64encode(raw).decode()
    # Fernet requires exactly 32 url-safe base64 bytes
    return Fernet(key.encode() if isinstance(key, str) else key)


_fernet = _get_fernet()


def encrypt_keys(keys_dict: dict) -> str:
    """Encrypt a keys dict to a single opaque string."""
    import json
    plaintext = json.dumps(keys_dict, separators=(",", ":")).encode()
    return _fernet.encrypt(plaintext).decode()


def decrypt_keys(token: str) -> dict:
    """Decrypt an opaque string back to a keys dict. Raises ValueError on failure."""
    import json
    try:
        plaintext = _fernet.decrypt(token.encode())
        return json.loads(plaintext)
    except (InvalidToken, Exception) as e:
        raise ValueError("密钥解密失败，可能已过期或服务端密钥已更换") from e
