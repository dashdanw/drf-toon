"""Codec selection: the native Rust extension when built, else the pure-Python ``toon_format``."""

import json
from typing import Any

import toon_format

try:
    from drf_toon import _native
except ImportError:  # pragma: no cover - exercised only on installs without the wheel
    _native = None  # type: ignore[assignment]

NATIVE = _native is not None

DecodeError: type[Exception] = (
    _native.ToonDecodeError if _native is not None else toon_format.ToonDecodeError
)


def encode_json(json_bytes: bytes) -> str:
    """Encode a JSON document (bytes) as TOON text."""
    if _native is not None:
        encoded = _native.encode_json(json_bytes)
        if encoded is not None:
            return encoded
        # toon-rust 0.7 rounds integers beyond 64 bits through f64; the Python codec keeps them.
    return toon_format.dumps(json.loads(json_bytes))


def decode(text: str) -> Any:
    """Decode TOON text into Python objects."""
    if _native is not None:
        return _native.decode(text)
    return toon_format.loads(text)
