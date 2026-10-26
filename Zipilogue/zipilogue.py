#!/usr/bin/env python3
"""Zipilogue (A): machine-to-machine authenticated encoding (layer 1).

Envelope (base64url, no padding) of a self-describing binary frame:

  magic(4) | ver(1) | nlen(1) | nonce | ct_len(4 BE) | ciphertext | mac(32)

Key schedule: hashlib.scrypt(passphrase) → 32-byte key.
Stream: HMAC-SHA256 keystream (counter blocks) XOR plaintext.
MAC:   HMAC-SHA256(key, magic||ver||nonce||aad_len||aad||ciphertext)

Optional associated context (``aad`` / channel label) is folded into the MAC
so the same plaintext+key under different labels do not verify interchangeably.
AAD is NOT written into the envelope — both peers must supply the same label.

Key resolution: ``--key`` / ``--key-file``, else env ``TALKCOMPRESS_ZIP_KEY``.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import os
import secrets
import struct
import sys
from pathlib import Path
from typing import Final

MAGIC: Final[bytes] = b"ZIP1"
VERSION: Final[int] = 1
NONCE_LEN: Final[int] = 16
MAC_LEN: Final[int] = 32
KEY_LEN: Final[int] = 32
_SCRYPT_N: Final[int] = 2**14
_SCRYPT_R: Final[int] = 8
_SCRYPT_P: Final[int] = 1
_SCRYPT_SALT: Final[bytes] = b"TalkCompress/Zipilogue/v1"


def derive_key(passphrase: bytes | str) -> bytes:
    raw = passphrase.encode("utf-8") if isinstance(passphrase, str) else passphrase
    if not raw:
        raise ValueError("key must be non-empty")
    return hashlib.scrypt(
        raw,
        salt=_SCRYPT_SALT,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=KEY_LEN,
    )


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac.new(
            key,
            nonce + struct.pack(">I", counter) + b"\x00stream",
            hashlib.sha256,
        ).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _normalize_aad(aad: bytes | str | None) -> bytes:
    if aad is None:
        return b""
    if isinstance(aad, str):
        return aad.encode("utf-8")
    return aad


def _mac(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes = b"") -> bytes:
    # Empty AAD keeps the legacy MAC (backward compatible).
    # Non-empty AAD folds aad_len (4 BE) + aad so channel labels separate MAC space.
    if aad:
        material = MAGIC + bytes([VERSION]) + nonce + struct.pack(">I", len(aad)) + aad + ciphertext
    else:
        material = MAGIC + bytes([VERSION]) + nonce + ciphertext
    return hmac.new(key, material, hashlib.sha256).digest()


def encode(
    payload: bytes,
    *,
    key: bytes | str,
    nonce: bytes | None = None,
    aad: bytes | str | None = None,
) -> bytes:
    """Return compact base64url (no padding) envelope bytes (ASCII)."""
    k = derive_key(key)
    n = nonce if nonce is not None else secrets.token_bytes(NONCE_LEN)
    if len(n) != NONCE_LEN:
        raise ValueError(f"nonce must be {NONCE_LEN} bytes")
    aad_b = _normalize_aad(aad)
    ks = _keystream(k, n, len(payload))
    ct = bytes(a ^ b for a, b in zip(payload, ks, strict=True))
    tag = _mac(k, n, ct, aad_b)
    frame = (
        MAGIC
        + bytes([VERSION, NONCE_LEN])
        + n
        + struct.pack(">I", len(ct))
        + ct
        + tag
    )
    return base64.urlsafe_b64encode(frame).rstrip(b"=")


def decode(
    envelope: bytes | str,
    *,
    key: bytes | str,
    aad: bytes | str | None = None,
) -> bytes:
    """Decode base64url envelope; raises ValueError on tamper / bad format / AAD mismatch."""
    k = derive_key(key)
    aad_b = _normalize_aad(aad)
    raw = envelope.encode("ascii") if isinstance(envelope, str) else envelope
    raw = raw.strip()
    pad = (-len(raw)) % 4
    try:
        frame = base64.urlsafe_b64decode(raw + b"=" * pad)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("invalid base64url envelope") from exc

    min_len = 4 + 1 + 1 + NONCE_LEN + 4 + MAC_LEN
    if len(frame) < min_len:
        raise ValueError("envelope too short")
    if frame[:4] != MAGIC:
        raise ValueError("bad magic")
    ver = frame[4]
    if ver != VERSION:
        raise ValueError(f"unsupported version: {ver}")
    nlen = frame[5]
    if nlen != NONCE_LEN:
        raise ValueError("unexpected nonce length")
    off = 6
    nonce = frame[off : off + nlen]
    off += nlen
    (ct_len,) = struct.unpack(">I", frame[off : off + 4])
    off += 4
    if off + ct_len + MAC_LEN != len(frame):
        raise ValueError("length mismatch")
    ct = frame[off : off + ct_len]
    off += ct_len
    tag = frame[off : off + MAC_LEN]
    expect = _mac(k, nonce, ct, aad_b)
    if not hmac.compare_digest(tag, expect):
        raise ValueError("MAC verification failed")
    ks = _keystream(k, nonce, len(ct))
    return bytes(a ^ b for a, b in zip(ct, ks, strict=True))


def encode_frames(
    payloads: list[bytes],
    *,
    key: bytes | str,
    aad: bytes | str | None = None,
) -> bytes:
    """Encode each payload as its own envelope; join with newlines (batch bot messages)."""
    lines = [encode(p, key=key, aad=aad) for p in payloads]
    return b"\n".join(lines)


def decode_frames(
    blob: bytes | str,
    *,
    key: bytes | str,
    aad: bytes | str | None = None,
) -> list[bytes]:
    """Decode newline-separated envelopes; skip blank lines."""
    raw = blob.encode("ascii") if isinstance(blob, str) else blob
    out: list[bytes] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(decode(line, key=key, aad=aad))
    return out


def _read_key(args: argparse.Namespace) -> bytes:
    if args.key_file:
        data = Path(args.key_file).read_bytes()
        return data.rstrip(b"\r\n")
    if args.key is not None:
        return args.key.encode("utf-8")
    env = os.environ.get("TALKCOMPRESS_ZIP_KEY")
    if env:
        return env.encode("utf-8")
    raise SystemExit("provide --key, --key-file, or TALKCOMPRESS_ZIP_KEY")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Zipilogue: layer-1 authenticated machine encoding")
    p.add_argument("mode", choices=("encode", "decode"))
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument("--key", help="shared passphrase (do not commit real keys)")
    g.add_argument("--key-file", help="read passphrase from file (trailing newline stripped)")
    p.add_argument("--text", help="UTF-8 text; otherwise stdin (encode: text/bytes, decode: envelope)")
    p.add_argument("--file", help="read binary input from PATH (encode: plaintext; decode: envelope)")
    p.add_argument("--out", help="write binary output to PATH instead of stdout")
    p.add_argument(
        "--aad",
        default="",
        help="associated context / channel label folded into MAC (must match on decode)",
    )
    p.add_argument("--hex-in", action="store_true", help="decode mode: treat input as hex of envelope")
    p.add_argument(
        "--frames",
        action="store_true",
        help="line-oriented batch: encode each plaintext line as its own envelope; "
        "decode splits envelopes by newline",
    )
    args = p.parse_args(argv)

    key = _read_key(args)
    aad = args.aad or ""

    if args.mode == "encode":
        if args.frames:
            if args.file:
                raw_text = Path(args.file).read_text(encoding="utf-8")
            elif args.text is not None:
                raw_text = args.text
            else:
                raw_text = sys.stdin.read()
            payloads = [ln.encode("utf-8") for ln in raw_text.splitlines() if ln.strip()]
            env = encode_frames(payloads, key=key, aad=aad)
        elif args.file:
            env = encode(Path(args.file).read_bytes(), key=key, aad=aad)
        elif args.text is not None:
            env = encode(args.text.encode("utf-8"), key=key, aad=aad)
        else:
            env = encode(sys.stdin.buffer.read(), key=key, aad=aad)
        if args.out:
            Path(args.out).write_bytes(env + b"\n")
        else:
            sys.stdout.buffer.write(env + b"\n")
        return 0

    if args.file:
        blob = Path(args.file).read_bytes()
    elif args.text is not None:
        blob = args.text.encode("ascii")
    else:
        blob = sys.stdin.buffer.read()
    if args.hex_in:
        blob = bytes.fromhex(blob.decode("ascii").strip())
    if args.frames:
        plains = decode_frames(blob, key=key, aad=aad)
        out_bytes = b"\n".join(plains)
        if args.out:
            Path(args.out).write_bytes(out_bytes + b"\n")
        else:
            sys.stdout.buffer.write(out_bytes + b"\n")
        return 0
    plain = decode(blob.strip(), key=key, aad=aad)
    if args.out:
        Path(args.out).write_bytes(plain)
    else:
        sys.stdout.buffer.write(plain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
