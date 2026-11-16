"""RulePeerCodec (A) 封筒: 鍵の正規化、RPC1 固定ベクタ、ZIP1 読み取り互換。

- key_normalization: Synthetic public fixtures only: no real user keys, network or model work.
- rule_peer_codec_key_compat: Fixed RPC1 envelopes (regenerated from the pre-NFC vectors' keys, nonce and payload).
- zip1_read_compat: Immutable public ZIP1 vectors; RPC1 remains the only write format.
"""

from RulePeerCodec import rule_peer_codec as codec
from RulePeerCodec import rule_peer_codec as z
from pathlib import Path
import base64
import json
import os
import subprocess
import sys
import unicodedata

import pytest


# ──── key_normalization ───────────────────────────────────────────

"""Synthetic public fixtures only: no real user keys, network or model work."""


ROOT = Path(__file__).resolve().parents[1]


SCRIPT = ROOT / "RulePeerCodec/rule_peer_codec.py"


NFC = "SYNTHETIC café fixture; not a secret"


NFD = unicodedata.normalize("NFD", NFC)


PAYLOAD = b"PUBLIC SYNTHETIC LEGACY V1 PAYLOAD"


AAD = "fixture-channel"


NONCE = bytes(range(16))


# Frozen vectors (originally pre-#107 84b28be7); regenerated for the RPC1 envelope
# and TalkCompress/RulePeerCodec/v1 salt with the same key, nonce and payload.
LEGACY_NFD = b"UlBDMQEQAAECAwQFBgcICQoLDA0ODwAAACJ8VPo9S5GERO3Jqx5zvLIuNP_JXEdFDBHIjwEDc9fr43_2r7nBu1TaP7MrMVzq6FudHtW2S6-_Vz_xK2JqaGIzJMc"


LEGACY_FINGERPRINT = "ba935e367e626057"


# Same public input under #107's implicit NFC behavior (source blob
# 384d48a02380f53079b0d31d03dc77e9f9998632); now selected explicitly.
IMPLICIT_107_NFC = b"UlBDMQEQAAECAwQFBgcICQoLDA0ODwAAACJbWFQiBzSx1t1woOlazJXAHHtLVXKRNr34PR6tCoiceO72V5JiJuZaym0wyJ5W6aMP14fsUpy4xUTnEoFh25ohaEY"


def cli(*args, text=None):
    env = dict(os.environ)
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=text,
                          env=env, capture_output=True, timeout=15)


def test_frozen_legacy_nfd_envelope_and_fingerprint_remain_compatible():
    assert z.decode(LEGACY_NFD, key=NFD, aad=AAD) == PAYLOAD
    assert z.encode(PAYLOAD, key=NFD, nonce=NONCE, aad=AAD) == LEGACY_NFD
    assert z.key_fingerprint(NFD) == LEGACY_FINGERPRINT
    assert z.derive_key(NFD) == z.derive_key(NFD.encode("utf-8"))
    assert z.derive_key(NFC) != z.derive_key(NFD)
    frame = base64.urlsafe_b64decode(LEGACY_NFD + b"=" * (-len(LEGACY_NFD) % 4))
    assert frame[:6] == b"RPC1\x01\x10"


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
def test_cli_text_key_matches_api_fingerprint_and_legacy_decode(mode):
    key_args = ["--key", NFD]
    r = cli("fingerprint", *key_args, "--key-normalization", mode)
    assert r.returncode == 0, r.stderr
    assert r.stdout.decode().strip() == z.key_fingerprint(NFD, key_normalization=mode)
    if mode == "none":
        r = cli("decode", *key_args, "--aad", AAD, "--text", LEGACY_NFD.decode())
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


@pytest.mark.parametrize("mode", [None, "none", "NFC"])
def test_read_key_preserves_legacy_bytes_unless_nfc_is_explicit(mode):
    args = z.argparse.Namespace(key=NFD, key_file=None)
    if mode is not None:
        args.key_normalization = mode
    key = z._read_key(args)
    assert key == (NFD if mode == "NFC" else NFD.encode("utf-8"))
    assert type(key) is (str if mode == "NFC" else bytes)
    selected = "none" if mode is None else mode
    assert z.key_fingerprint(key, key_normalization=selected) == z.key_fingerprint(NFD, key_normalization=selected)


# ──── rule_peer_codec_key_compat ──────────────────────────────────

"""Fixed RPC1 envelopes (regenerated from the pre-NFC vectors' keys, nonce and payload)."""


FIXTURE = json.loads((Path(__file__).parent / 'fixtures/rule_peer_codec_legacy_keys.json').read_text())


CLI = str(Path(z.__file__).resolve())


def run_cli(monkeypatch, source, key, mode, *extra):
    args = [sys.executable, CLI, mode, source, str(key)]
    return subprocess.run(args + list(extra), capture_output=True)


@pytest.mark.parametrize('row', FIXTURE['rows'], ids=lambda r: r['label'])
def test_legacy_api_and_recovery(row):
    key = row['key']
    envelope = row['envelope']
    expected = FIXTURE['payload'].encode()
    assert z.decode(envelope, key=key.encode()) == expected
    assert z.key_fingerprint(key.encode()) == row['fingerprint']
    # Default policy is raw UTF-8: text keys recover legacy envelopes exactly.
    assert z.decode(envelope, key=key) == expected
    assert z.key_fingerprint(key) == row['fingerprint']
    # Explicit NFC opt-in derives a different key for non-NFC text.
    if row['label'] == 'nfd':
        with pytest.raises(ValueError, match='MAC verification failed'):
            z.decode(envelope, key=key, key_normalization='NFC')
        assert z.key_fingerprint(key, key_normalization='NFC') != row['fingerprint']
    else:
        assert z.decode(envelope, key=key, key_normalization='NFC') == expected


@pytest.mark.parametrize('source', ['--key', '--key-file'])
@pytest.mark.parametrize('row', FIXTURE['rows'], ids=lambda r: r['label'])
def test_cli_legacy_recovery_and_fingerprints(monkeypatch, tmp_path, source, row):
    key = row['key']
    if source == '--key-file':
        path = tmp_path / 'key'
        path.write_bytes(key.encode() + b'\r\n')
        key = path
    result = run_cli(monkeypatch, source, key, 'decode', '--text', row['envelope'])
    # Default raw policy: every legacy envelope recovers with its own bytes.
    assert result.returncode == 0, result.stderr
    assert result.stdout == FIXTURE['payload'].encode()
    fp = run_cli(monkeypatch, source, key, 'fingerprint')
    assert fp.returncode == 0, fp.stderr
    expected = z.key_fingerprint(row['key'].encode() if source == '--key-file' else row['key'])
    assert fp.stdout.decode().strip() == expected


@pytest.mark.parametrize('source', ['--key', '--key-file'])
@pytest.mark.parametrize('key', ['café', 'cafe\u0301'])
def test_cli_new_envelopes_match_input_policy(monkeypatch, tmp_path, source, key):
    value = key
    api_key = key
    if source == '--key-file':
        value = tmp_path / 'key'
        value.write_bytes(key.encode() + b'\r\n')
        api_key = key.encode()
    result = run_cli(monkeypatch, source, value, 'encode', '--text', 'new payload')
    assert result.returncode == 0, result.stderr
    assert z.decode(result.stdout, key=api_key) == b'new payload'
    other = 'cafe\u0301' if key == 'café' else 'café'
    # Default raw policy: the other Unicode form is a different passphrase.
    with pytest.raises(ValueError, match='MAC verification failed'):
        z.decode(result.stdout, key=other.encode())


@pytest.mark.parametrize('source', ['--key'])
def test_cli_nfc_opt_in_unifies_unicode_forms(monkeypatch, source):
    nfd = 'café'
    nfc = 'café'
    result = run_cli(monkeypatch, source, nfd, 'encode', '--text', 'new payload',
                     '--key-normalization', 'NFC')
    assert result.returncode == 0, result.stderr
    assert z.decode(result.stdout, key=nfc, key_normalization='NFC') == b'new payload'
    assert z.decode(result.stdout, key=nfd, key_normalization='NFC') == b'new payload'


def test_binary_key_file_unchanged(monkeypatch, tmp_path):
    key = b'\xff\x00binary\r\n'
    path = tmp_path / 'binary-key'
    path.write_bytes(key)
    result = run_cli(monkeypatch, '--key-file', path, 'encode', '--text', 'binary')
    assert result.returncode == 0, result.stderr
    assert z.decode(result.stdout, key=key.rstrip(b'\r\n')) == b'binary'
    # The API itself preserves trailing CR/LF too.
    assert z.derive_key(key) != z.derive_key(key.rstrip(b'\r\n'))


# ──── zip1_read_compat ────────────────────────────────────────────

"""Immutable public ZIP1 vectors; RPC1 remains the only write format."""


FIXTURE_zip1_read_compat = json.loads((ROOT / 'tests/fixtures/zip1_legacy_keys.json').read_text())


def frame(envelope):
    raw = envelope.encode() if isinstance(envelope, str) else envelope
    return bytearray(base64.urlsafe_b64decode(raw + b'=' * (-len(raw) % 4)))


@pytest.mark.parametrize('row', FIXTURE_zip1_read_compat['rows'], ids=lambda row: row['label'])
def test_frozen_zip1_read_and_rpc1_write(row):
    assert frame(row['envelope'])[:4] == b'ZIP1'
    payload = FIXTURE_zip1_read_compat['payload'].encode()
    assert codec.decode(row['envelope'], key=row['key']) == payload
    new = codec.encode(payload, key=row['key'])
    assert frame(new)[:4] == b'RPC1'
    assert codec.decode(new, key=row['key']) == payload
    assert codec.decode_frames(row['envelope'].encode() + b'\n' + new, key=row['key']) == [payload, payload]
    assert codec.key_fingerprint(row['key']) != row['fingerprint']


@pytest.mark.parametrize('row', FIXTURE_zip1_read_compat['rows'], ids=lambda row: row['label'])
def test_zip1_fail_closed(row):
    for kwargs in ({'key': 'wrong'}, {'key': row['key'], 'aad': 'wrong'}):
        with pytest.raises(ValueError, match='MAC verification failed'):
            codec.decode(row['envelope'], **kwargs)
    for offset in (6, 26, -1):
        raw = frame(row['envelope']); raw[offset] ^= 1
        with pytest.raises(ValueError, match='MAC verification failed'):
            codec.decode(base64.urlsafe_b64encode(raw), key=row['key'])
    for envelope, magic in ((row['envelope'], b'RPC1'), (codec.encode(b'x', key=row['key']), b'ZIP1')):
        raw = frame(envelope); raw[:4] = magic
        with pytest.raises(ValueError, match='MAC verification failed'):
            codec.decode(base64.urlsafe_b64encode(raw), key=row['key'])
    raw = frame(row['envelope']); raw[4] = 2
    with pytest.raises(ValueError, match='unsupported version'):
        codec.decode(base64.urlsafe_b64encode(raw), key=row['key'])
    with pytest.raises(ValueError, match='MAC verification failed'):
        codec.decode(FIXTURE_zip1_read_compat['rows'][2]['envelope'], key=FIXTURE_zip1_read_compat['rows'][2]['key'], key_normalization='NFC')


def test_cli_zip1_decode():
    row = FIXTURE_zip1_read_compat['rows'][0]
    result = subprocess.run([sys.executable, str(ROOT / 'RulePeerCodec/rule_peer_codec.py'), 'decode', '--key', row['key'], '--text', row['envelope']], capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == FIXTURE_zip1_read_compat['payload'].encode()


# Original main vectors, with authenticated non-empty AAD.
LEGACY_NFD_zip1_read_compat = b'WklQMQEQAAECAwQFBgcICQoLDA0ODwAAACLtZRyAg3ee6-X7XRaCKbU2a_jLB25O64Gh3id1QiYo0yANsOn1Av5OxxC_R_DCeDP1dlZyWSeecujhTo035ptctJw'


IMPLICIT_107_NFC_zip1_read_compat = b'WklQMQEQAAECAwQFBgcICQoLDA0ODwAAACIaLgMcMMRHQhli4wSJ25_eKT7XQWwAVXu4yfbE8HiZgX0P1ZQ83wwPMtGmlwaCm6DEa4pXc_uyohJanZ7EqED8U1c'


def test_zip1_aad_and_explicit_normalization():
    key = 'SYNTHETIC cafe\u0301 fixture; not a secret'
    payload = b'PUBLIC SYNTHETIC LEGACY V1 PAYLOAD'
    assert codec.decode(LEGACY_NFD_zip1_read_compat, key=key, aad='fixture-channel') == payload
    assert codec.decode(IMPLICIT_107_NFC_zip1_read_compat, key=key, aad='fixture-channel', key_normalization='NFC') == payload
    for envelope, mode in ((LEGACY_NFD_zip1_read_compat, 'NFC'), (IMPLICIT_107_NFC_zip1_read_compat, 'none')):
        with pytest.raises(ValueError, match='MAC verification failed'):
            codec.decode(envelope, key=key, aad='fixture-channel', key_normalization=mode)
    with pytest.raises(ValueError, match='MAC verification failed'):
        codec.decode(LEGACY_NFD_zip1_read_compat, key=key, aad='wrong')
