"""
Signed requests from IEB (Ed25519).

Each IEB installation holds a private key that never leaves the machine. Copilot holds only the
PUBLIC keys below - they are not secrets, so they can live in the code and need no server
configuration. A request is accepted only when:

    X-IEB-Instance   names a trusted instance
    X-IEB-Timestamp  is within MAX_SKEW seconds of the server clock
    X-IEB-Nonce      has not been seen in the last MAX_SKEW seconds (replay protection)
    X-IEB-Signature  is a valid Ed25519 signature over the canonical string

    canonical = METHOD \\n PATH \\n TIMESTAMP \\n NONCE \\n sha256_hex(body)

To add or rotate an installation: `python -m core.copilot_bridge --init` on that machine prints its
public key; put it in TRUSTED_KEYS and deploy.
"""
from __future__ import annotations

import base64
import hashlib
import time
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

TRUSTED_KEYS: dict[str, str] = {
    # The owner's Windows PC running IEB (key generated 2026-09-27).
    "ieb-liv-pc-1": "7/jk+hVH//5qFHVkMc+x9RL4UMGyN3mXSL2l8RGrHkg=",
}
MAX_SKEW = 300

_seen_nonces: dict[str, float] = {}


@dataclass
class AuthResult:
    ok: bool
    instance_id: str | None
    reason: str = ""


def canonical(method: str, path: str, timestamp: str, nonce: str, body: bytes) -> bytes:
    return "\n".join([method.upper(), path, timestamp, nonce, hashlib.sha256(body).hexdigest()]).encode()


def verify(method: str, path: str, headers: dict, body: bytes, now: float | None = None) -> AuthResult:
    now = time.time() if now is None else now
    instance = headers.get("x-ieb-instance") or ""
    ts = headers.get("x-ieb-timestamp") or ""
    nonce = headers.get("x-ieb-nonce") or ""
    sig = headers.get("x-ieb-signature") or ""
    if not instance or not ts or not nonce or not sig:
        return AuthResult(False, instance or None, "missing signature headers")
    key_b64 = TRUSTED_KEYS.get(instance)
    if not key_b64:
        return AuthResult(False, instance, "unknown instance")
    try:
        ts_f = float(ts)
    except ValueError:
        return AuthResult(False, instance, "bad timestamp")
    if abs(now - ts_f) > MAX_SKEW:
        return AuthResult(False, instance, "timestamp outside the allowed window")
    if not (8 <= len(nonce) <= 64):
        return AuthResult(False, instance, "bad nonce")
    for k, t in list(_seen_nonces.items()):
        if now - t > MAX_SKEW:
            _seen_nonces.pop(k, None)
    key = f"{instance}:{nonce}"
    if key in _seen_nonces:
        return AuthResult(False, instance, "replayed request")
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(key_b64)).verify(
            base64.b64decode(sig), canonical(method, path, ts, nonce, body))
    except (InvalidSignature, ValueError):
        return AuthResult(False, instance, "invalid signature")
    _seen_nonces[key] = now
    return AuthResult(True, instance)
