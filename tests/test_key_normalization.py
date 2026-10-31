"""Synthetic public fixtures only: no real user keys, network or model work."""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import unicodedata

import pytest

from Zipilogue import zipilogue as z


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "Zipilogue/zipilogue.py"
NFC = "SYNTHETIC café fixture; not a secret"
NFD = unicodedata.normalize("NFD", NFC)
PAYLOAD = b"PUBLIC SYNTHETIC LEGACY V1 PAYLOAD"
AAD = "fixture-channel"
NONCE = bytes(range(16))
# Frozen using pre-#107 source at 84b28be729bf3d51d3e8a054cb0ab63edecb90a4,
# Zipilogue/zipilogue.py blob 8a907215fddead5f90a15c8a75c70064f5fa3097.
LEGACY_NFD = b"WklQMQEQAAECAwQFBgcICQoLDA0ODwAAACLtZRyAg3ee6-X7XRaCKbU2a_jLB25O64Gh3id1QiYo0yANsOn1Av5OxxC_R_DCeDP1dlZyWSeecujhTo035ptctJw"
LEGACY_FINGERPRINT = "3f27e6e999cde86f"
# Same public input under #107's implicit NFC behavior (source blob
# 384d48a02380f53079b0d31d03dc77e9f9998632); now selected explicitly.
IMPLICIT_107_NFC = b"WklQMQEQAAECAwQFBgcICQoLDA0ODwAAACIaLgMcMMRHQhli4wSJ25_eKT7XQWwAVXu4yfbE8HiZgX0P1ZQ83wwPMtGmlwaCm6DEa4pXc_uyohJanZ7EqED8U1c"


def cli(*args, text=None, env_key=None):
    env = dict(os.environ)
    env.pop("TALKCOMPRESS_ZIP_KEY", None)
    if env_key is not None:
        env["TALKCOMPRESS_ZIP_KEY"] = env_key
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=text,
                          env=env, capture_output=True, timeout=15)


def test_frozen_legacy_nfd_envelope_and_fingerprint_remain_compatible():
    assert z.decode(LEGACY_NFD, key=NFD, aad=AAD) == PAYLOAD
    assert z.encode(PAYLOAD, key=NFD, nonce=NONCE, aad=AAD) == LEGACY_NFD
    assert z.key_fingerprint(NFD) == LEGACY_FINGERPRINT
    assert z.derive_key(NFD) == z.derive_key(NFD.encode("utf-8"))
    assert z.derive_key(NFC) != z.derive_key(NFD)
    frame = base64.urlsafe_b64decode(LEGACY_NFD + b"=" * (-len(LEGACY_NFD) % 4))
    assert frame[:6] == b"ZIP1\x01\x10"


def test_explicit_nfc_is_canonical_not_compatibility_normalization():
    assert z.derive_key(NFC, key_normalization="NFC") == z.derive_key(NFD, key_normalization="NFC")
    assert z.derive_key("ﬁ", key_normalization="NFC") != z.derive_key("fi", key_normalization="NFC")
    assert z.key_fingerprint(NFC, key_normalization="NFC") == z.key_fingerprint(NFD, key_normalization="NFC")


def test_explicit_mode_is_required_and_decode_never_falls_back():
    envelope = z.encode(PAYLOAD, key=NFD, nonce=NONCE, aad=AAD, key_normalization="NFC")
    assert envelope == IMPLICIT_107_NFC
    assert envelope == z.encode(PAYLOAD, key=NFC, nonce=NONCE, aad=AAD)
    assert z.decode(envelope, key=NFD, aad=AAD, key_normalization="NFC") == PAYLOAD
    with pytest.raises(ValueError, match="MAC verification failed"):
        z.decode(envelope, key=NFD, aad=AAD)
    with pytest.raises(ValueError, match="MAC verification failed"):
        z.decode(LEGACY_NFD, key=NFD, aad=AAD, key_normalization="NFC")


API_CALLS = [
    lambda key, mode: z.derive_key(key, key_normalization=mode),
    lambda key, mode: z.key_fingerprint(key, key_normalization=mode),
    lambda key, mode: z.encode(PAYLOAD, key=key, key_normalization=mode),
    lambda key, mode: z.decode(LEGACY_NFD, key=key, key_normalization=mode),
    lambda key, mode: z.encode_frames([], key=key, key_normalization=mode),
    lambda key, mode: z.decode_frames(b"", key=key, key_normalization=mode),
]


@pytest.mark.parametrize("call", API_CALLS)
def test_raw_bytes_reject_nfc_even_for_empty_batches(call):
    with pytest.raises(ValueError, match="requires text"):
        call(NFD.encode(), "NFC")


@pytest.mark.parametrize("call", API_CALLS)
@pytest.mark.parametrize("mode", ["nfc", "NFKC", "auto", None])
def test_unknown_modes_fail_closed(call, mode):
    with pytest.raises(ValueError, match="key_normalization"):
        call(NFD, mode)


def test_frames_propagate_mode_and_aad():
    messages = [b"first public fixture", b"second public fixture"]
    blob = z.encode_frames(messages, key=NFD, aad=AAD, key_normalization="NFC")
    assert z.decode_frames(blob, key=NFC, aad=AAD, key_normalization="NFC") == messages
    with pytest.raises(ValueError, match="MAC verification failed"):
        z.decode_frames(blob, key=NFD, aad=AAD)
    with pytest.raises(ValueError, match="MAC verification failed"):
        z.decode_frames(blob, key=NFC, aad="wrong", key_normalization="NFC")


def test_empty_batches_retain_legacy_default_behavior():
    assert z.encode_frames([], key=b"") == b""
    assert z.decode_frames(b"", key=b"") == []


@pytest.mark.parametrize("mode", ["none", "NFC"])
def test_tamper_wrong_key_and_wrong_aad_still_fail(mode):
    envelope = z.encode(PAYLOAD, key=NFD, aad=AAD, key_normalization=mode)
    for key, aad in [("wrong public fixture", AAD), (NFD, "wrong channel")]:
        with pytest.raises(ValueError, match="MAC verification failed"):
            z.decode(envelope, key=key, aad=aad, key_normalization=mode)
    raw = bytearray(base64.urlsafe_b64decode(envelope + b"=" * (-len(envelope) % 4)))
    raw[-1] ^= 1
    tampered = base64.urlsafe_b64encode(raw).rstrip(b"=")
    with pytest.raises(ValueError, match="MAC verification failed"):
        z.decode(tampered, key=NFD, aad=AAD, key_normalization=mode)


@pytest.mark.parametrize("mode", ["none", "NFC"])
@pytest.mark.parametrize("source", ["argument", "environment"])
def test_cli_text_key_matches_api_fingerprint_and_legacy_decode(mode, source):
    key_args = ["--key", NFD] if source == "argument" else []
    env_key = NFD if source == "environment" else None
    r = cli("fingerprint", *key_args, "--key-normalization", mode, env_key=env_key)
    assert r.returncode == 0, r.stderr
    assert r.stdout.decode().strip() == z.key_fingerprint(NFD, key_normalization=mode)
    if mode == "none":
        r = cli("decode", *key_args, "--aad", AAD, "--text", LEGACY_NFD.decode(), env_key=env_key)
        assert r.returncode == 0 and r.stdout == PAYLOAD, r.stderr


def test_cli_default_fingerprint_is_frozen_legacy():
    r = cli("fingerprint", "--key", NFD)
    assert r.returncode == 0 and r.stdout.decode().strip() == LEGACY_FINGERPRINT


@pytest.mark.parametrize("mode", ["none", "NFC"])
@pytest.mark.parametrize("source", ["text", "stdin", "file"])
def test_cli_encode_decode_and_frames_forward_mode(mode, source, tmp_path):
    path = tmp_path / "public-input.txt"
    path.write_bytes(PAYLOAD)
    input_args = ["--text", PAYLOAD.decode()] if source == "text" else ["--file", str(path)] if source == "file" else []
    stdin = PAYLOAD if source == "stdin" else None
    for frames in [False, True]:
        frame_args = ["--frames"] if frames else []
        r = cli("encode", "--key", NFD, "--key-normalization", mode, "--aad", AAD,
                *frame_args, *input_args, text=stdin)
        assert r.returncode == 0, r.stderr
        decode = z.decode_frames if frames else z.decode
        want = [PAYLOAD] if frames else PAYLOAD
        assert decode(r.stdout.strip(), key=NFD, aad=AAD, key_normalization=mode) == want
        d = cli("decode", "--key", NFD, "--key-normalization", mode, "--aad", AAD,
                *frame_args, text=r.stdout)
        assert d.returncode == 0 and d.stdout == PAYLOAD + (b"\n" if frames else b""), d.stderr


def test_cli_key_file_preserves_bytes_and_rejects_nfc_before_read(tmp_path):
    keyfile = tmp_path / "public-key.txt"
    keyfile.write_bytes(NFD.encode() + b"\r\n")
    r = cli("fingerprint", "--key-file", str(keyfile))
    assert r.returncode == 0 and r.stdout.decode().strip() == LEGACY_FINGERPRINT
    for path in [keyfile, tmp_path / "does-not-exist"]:
        r = cli("fingerprint", "--key-file", str(path), "--key-normalization", "NFC")
        assert r.returncode == 2 and b"raw --key-file bytes" in r.stderr
        assert not r.stdout and b"Traceback" not in r.stderr


@pytest.mark.parametrize("mode", ["none", "NFC"])
def test_cli_dry_run_fingerprint_uses_selected_mode(mode):
    r = cli("encode", "--key", NFD, "--key-normalization", mode, "--text", "public", "--dry-run")
    assert r.returncode == 0, r.stderr
    stats = json.loads(r.stderr)
    assert stats["fingerprint"] == z.key_fingerprint(NFD, key_normalization=mode)
    assert stats["dry_run"] and int(r.stdout) == stats["envelope_bytes"]


@pytest.mark.parametrize("mode", ["none", "NFC"])
def test_cli_rule_wrap_and_unwrap_forward_mode(mode, tmp_path):
    state = tmp_path / "book.json"
    r = cli("rule-declare", "--state", str(state), "--long", "ready and waiting", "--short", "r1")
    assert r.returncode == 0, r.stderr
    r = cli("rule-encode", "--state", str(state), "--text", "ready and waiting",
            "--key", NFD, "--aad", AAD, "--key-normalization", mode)
    assert r.returncode == 0, r.stderr
    assert z.decode(r.stdout.strip(), key=NFD, aad=AAD, key_normalization=mode) == b"r1"
    d = cli("rule-decode", "--state", str(state), "--text", r.stdout.decode().strip(),
            "--key", NFD, "--aad", AAD, "--key-normalization", mode)
    assert d.returncode == 0 and d.stdout.strip() == b"ready and waiting", d.stderr
