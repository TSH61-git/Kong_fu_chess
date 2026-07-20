# Pure password hashing — no I/O, no server/db knowledge.
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Optional

from server import config


def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
    salt = salt if salt is not None else os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, config.PBKDF2_ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    digest_hex, _ = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(digest_hex, expected_hash_hex)
