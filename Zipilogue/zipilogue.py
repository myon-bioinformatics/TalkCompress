#!/usr/bin/env python3
"""Zipilogue (A): machine-to-machine shared-rule channel + optional MAC envelope.

Core idea: sender and receiver grow a shared RuleBook across turns — declare
``rule: long => short`` or auto-adopt repeated phrases (threshold default 3)
into opaque tokens (r1, r2, …). Alphabet / regularity / length are free as long
as both sides recognize the assertions. Conversations start longer; after
dozens of turns frequent patterns shorten like slang.

Optional crypto envelope (base64url, no padding) remains a transport wrap:

  magic(4) | ver(1) | nlen(1) | nonce | ct_len(4 BE) | ciphertext | mac(32)

Key schedule: hashlib.scrypt(passphrase) → 32-byte key.
Stream: HMAC-SHA256 keystream (counter blocks) XOR plaintext.
MAC:   HMAC-SHA256(key, magic||ver||nonce||aad_len||aad||ciphertext)

Optional associated context (``aad`` / channel label) is folded into the MAC
so the same plaintext+key under different labels do not verify interchangeably.
AAD is NOT written into the envelope — both peers must supply the same label.

Key resolution: ``--key`` / ``--key-file``, else env ``TALKCOMPRESS_ZIP_KEY``.
``key_fingerprint`` / CLI ``fingerprint`` confirm shared secrets without printing keys.
``--dry-run`` on encode reports envelope length without dumping binary.
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



def key_fingerprint(passphrase: bytes | str, *, length: int = 16) -> str:
    """Short hex fingerprint of the *derived* key (not the passphrase).

    Bots can compare fingerprints to confirm a shared secret without printing
    the key or passphrase. Default length is 16 hex chars (64 bits of SHA-256).
    """
    digest = hashlib.sha256(derive_key(passphrase)).hexdigest()
    return digest[: max(8, min(length, 64))]


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


def _load_rulebook():
    """Import sibling rulebook module without requiring package install."""
    import importlib.util

    rb_path = Path(__file__).resolve().parent / "rulebook.py"
    spec = importlib.util.spec_from_file_location("zipilogue_rulebook", rb_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {rb_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["zipilogue_rulebook"] = mod
    spec.loader.exec_module(mod)
    return mod


def _rule_text(args: argparse.Namespace) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if args.text is not None:
        return args.text
    return sys.stdin.read()


def _maybe_wrap_envelope(text: str, args: argparse.Namespace) -> str:
    """If --key present, wrap UTF-8 rule text in MAC envelope; else return text."""
    has_key = bool(args.key or args.key_file or os.environ.get("TALKCOMPRESS_ZIP_KEY"))
    if not has_key:
        return text
    key = _read_key(args)
    aad = args.aad or ""
    env = encode(text.encode("utf-8"), key=key, aad=aad)
    return env.decode("ascii")


def _maybe_unwrap_envelope(blob: str, args: argparse.Namespace) -> str:
    has_key = bool(args.key or args.key_file or os.environ.get("TALKCOMPRESS_ZIP_KEY"))
    if not has_key:
        return blob
    key = _read_key(args)
    aad = args.aad or ""
    return decode(blob.strip().encode("ascii"), key=key, aad=aad).decode("utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Zipilogue: shared-rule ledger + optional MAC envelope (layer 1)"
    )
    p.add_argument(
        "mode",
        choices=(
            "encode",
            "decode",
            "fingerprint",
            "rule-observe",
            "rule-declare",
            "rule-encode",
            "rule-decode",
            "rule-sim",
            "rule-export",
            "rule-import",
            "rule-threshold",
            "rule-negotiate",
        ),
    )
    g = p.add_mutually_exclusive_group(required=False)
    g.add_argument("--key", help="shared passphrase (do not commit real keys)")
    g.add_argument("--key-file", help="read passphrase from file (trailing newline stripped)")
    p.add_argument("--text", help="UTF-8 text; otherwise stdin (encode: text/bytes, decode: envelope)")
    p.add_argument("--file", help="read input from PATH")
    p.add_argument("--out", help="write output to PATH instead of stdout")
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
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="encode: print envelope byte length (and stats) without dumping binary",
    )
    p.add_argument(
        "--stats",
        action="store_true",
        help="print JSON length/fingerprint/rule stats to stderr",
    )
    p.add_argument(
        "--state",
        help="RuleBook JSON path (required for rule-* modes)",
    )
    p.add_argument("--long", dest="rule_long", help="rule-declare: long form")
    p.add_argument("--short", dest="rule_short", help="rule-declare: short token")
    p.add_argument(
        "--threshold",
        type=int,
        default=None,
        help="rule-observe/sim: auto-adopt after N sightings (default 3 / book value)",
    )
    p.add_argument(
        "--corpus",
        help="rule-sim: line-oriented corpus file (else --file/--text/stdin)",
    )
    p.add_argument(
        "--no-auto-adopt",
        action="store_true",
        help="rule-observe/sim: record proposals only, do not adopt",
    )
    p.add_argument(
        "--export",
        dest="export_path",
        help="rule-export: write rules dump to PATH (default stdout JSON)",
    )
    p.add_argument(
        "--import",
        dest="import_path",
        help="rule-import / rule-negotiate: peer export JSON path (repeat via --peer)",
    )
    p.add_argument(
        "--peer",
        action="append",
        default=[],
        help="rule-negotiate: additional peer export JSON (repeatable)",
    )
    p.add_argument(
        "--replace",
        action="store_true",
        help="rule-import: replace rules instead of merge",
    )
    p.add_argument(
        "--adopt-proposals",
        action="store_true",
        help="rule-import/negotiate: also declare peer proposals",
    )
    args = p.parse_args(argv)

    # --- shared-rule modes (key optional) ---
    if args.mode.startswith("rule-"):
        import json as _json

        rb = _load_rulebook()
        if not args.state:
            raise SystemExit(f"{args.mode} requires --state PATH")
        book = rb.RuleBook.load(args.state, threshold=args.threshold)
        if args.no_auto_adopt:
            book.auto_adopt = False

        if args.mode == "rule-declare":
            if not args.rule_long:
                raise SystemExit("rule-declare needs --long")
            rule = book.declare(args.rule_long, args.rule_short)
            book.save()
            print(rule.short)
            if args.stats:
                print(_json.dumps({"declared": rule.to_dict(), **book.stats()}, ensure_ascii=False), file=sys.stderr)
            return 0

        if args.mode == "rule-observe":
            text = _rule_text(args)
            info = book.observe(text)
            encoded = book.encode_with_rules(text)
            book.save()
            out = encoded
            if args.out:
                Path(args.out).write_text(out + ("\n" if not out.endswith("\n") else ""), encoding="utf-8")
            else:
                print(out)
            print(_json.dumps(info, ensure_ascii=False), file=sys.stderr)
            return 0

        if args.mode == "rule-encode":
            text = _rule_text(args)
            encoded = book.encode_with_rules(text)
            wrapped = _maybe_wrap_envelope(encoded, args)
            if args.out:
                Path(args.out).write_text(wrapped + "\n", encoding="utf-8")
            else:
                print(wrapped)
            if args.stats:
                print(
                    _json.dumps(
                        {
                            "chars_before": len(text),
                            "chars_after": len(encoded),
                            "wrapped": wrapped != encoded,
                            **book.stats(),
                        },
                        ensure_ascii=False,
                    ),
                    file=sys.stderr,
                )
            return 0

        if args.mode == "rule-decode":
            blob = _rule_text(args)
            unwrapped = _maybe_unwrap_envelope(blob, args)
            decoded = book.decode_with_rules(unwrapped)
            if args.out:
                Path(args.out).write_text(decoded + ("\n" if not decoded.endswith("\n") else ""), encoding="utf-8")
            else:
                print(decoded)
            if args.stats:
                print(
                    _json.dumps(
                        {"chars_before": len(unwrapped), "chars_after": len(decoded), **book.stats()},
                        ensure_ascii=False,
                    ),
                    file=sys.stderr,
                )
            return 0

        if args.mode == "rule-sim":
            if args.corpus:
                corpus = Path(args.corpus).read_text(encoding="utf-8")
            else:
                corpus = _rule_text(args)
            lines = [ln for ln in corpus.splitlines() if ln.strip()]
            rows = []
            for i, line in enumerate(lines, start=1):
                before = line
                info = book.observe(line)
                after = book.encode_with_rules(line)
                row = {
                    "turn": book.turn,
                    "chars_before": len(before),
                    "chars_after": len(after),
                    "adopted": info.get("adopted", []),
                    "text": after,
                }
                rows.append(row)
                print(f"[{book.turn}] {len(before)}→{len(after)} {after}")
            book.save()
            print(
                _json.dumps(
                    {"turns": len(rows), "final_rules": len(book.rules), "rules": [r.to_dict() for r in book.rules]},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            return 0


        if args.mode == "rule-export":
            dest = args.export_path or args.out
            payload = book.export_rules(dest)
            if not dest:
                print(_json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(dest)
            if args.stats:
                print(_json.dumps(book.stats(), ensure_ascii=False), file=sys.stderr)
            return 0

        if args.mode == "rule-import":
            src = args.import_path
            if not src:
                raise SystemExit("rule-import needs --import PATH")
            info = book.import_rules(
                src, merge=not args.replace, adopt_proposals=args.adopt_proposals
            )
            book.save()
            print(_json.dumps(info, ensure_ascii=False))
            return 0

        if args.mode == "rule-threshold":
            if args.threshold is None:
                raise SystemExit("rule-threshold needs --threshold N")
            book.set_threshold(args.threshold)
            book.save()
            print(book.threshold)
            if args.stats:
                print(_json.dumps(book.stats(), ensure_ascii=False), file=sys.stderr)
            return 0

        if args.mode == "rule-negotiate":
            peers: list = []
            if args.import_path:
                peers.append(args.import_path)
            peers.extend(args.peer or [])
            if not peers:
                raise SystemExit("rule-negotiate needs --import and/or --peer PATH")
            info = book.negotiate(peers, adopt_proposals=True)
            book.save()
            print(_json.dumps(info, ensure_ascii=False))
            return 0

        raise SystemExit(f"unhandled rule mode: {args.mode}")

    # --- crypto envelope modes (key required) ---
    key = _read_key(args)
    aad = args.aad or ""

    if args.mode == "fingerprint":
        fp = key_fingerprint(key)
        print(fp)
        if args.stats:
            import json as _json
            print(
                _json.dumps({"fingerprint": fp, "len": len(fp)}, ensure_ascii=False),
                file=sys.stderr,
            )
        return 0

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
        if args.stats or args.dry_run:
            import json as _json
            print(
                _json.dumps(
                    {
                        "envelope_bytes": len(env),
                        "fingerprint": key_fingerprint(key),
                        "dry_run": bool(args.dry_run),
                    },
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
        if args.dry_run:
            print(len(env))
            return 0
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
