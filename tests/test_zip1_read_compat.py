"""Immutable public ZIP1 vectors; RPC1 remains the only write format."""
import base64
import json
from pathlib import Path
import subprocess
import sys

import pytest
from RulePeerCodec import rule_peer_codec as codec

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / 'tests/fixtures/zip1_legacy_keys.json').read_text())


def frame(envelope):
    raw = envelope.encode() if isinstance(envelope, str) else envelope
    return bytearray(base64.urlsafe_b64decode(raw + b'=' * (-len(raw) % 4)))


@pytest.mark.parametrize('row', FIXTURE['rows'], ids=lambda row: row['label'])
def test_frozen_zip1_read_and_rpc1_write(row):
    assert frame(row['envelope'])[:4] == b'ZIP1'
    payload = FIXTURE['payload'].encode()
    assert codec.decode(row['envelope'], key=row['key']) == payload
    new = codec.encode(payload, key=row['key'])
    assert frame(new)[:4] == b'RPC1'
    assert codec.decode(new, key=row['key']) == payload
    assert codec.decode_frames(row['envelope'].encode() + b'\n' + new, key=row['key']) == [payload, payload]
    assert codec.key_fingerprint(row['key']) != row['fingerprint']


@pytest.mark.parametrize('row', FIXTURE['rows'], ids=lambda row: row['label'])
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
        codec.decode(FIXTURE['rows'][2]['envelope'], key=FIXTURE['rows'][2]['key'], key_normalization='NFC')


def test_cli_zip1_decode():
    row = FIXTURE['rows'][0]
    result = subprocess.run([sys.executable, str(ROOT / 'RulePeerCodec/rule_peer_codec.py'), 'decode', '--key', row['key'], '--text', row['envelope']], capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout == FIXTURE['payload'].encode()


# Original main vectors, with authenticated non-empty AAD.
LEGACY_NFD = b'WklQMQEQAAECAwQFBgcICQoLDA0ODwAAACLtZRyAg3ee6-X7XRaCKbU2a_jLB25O64Gh3id1QiYo0yANsOn1Av5OxxC_R_DCeDP1dlZyWSeecujhTo035ptctJw'
IMPLICIT_107_NFC = b'WklQMQEQAAECAwQFBgcICQoLDA0ODwAAACIaLgMcMMRHQhli4wSJ25_eKT7XQWwAVXu4yfbE8HiZgX0P1ZQ83wwPMtGmlwaCm6DEa4pXc_uyohJanZ7EqED8U1c'


def test_zip1_aad_and_explicit_normalization():
    key = 'SYNTHETIC cafe\u0301 fixture; not a secret'
    payload = b'PUBLIC SYNTHETIC LEGACY V1 PAYLOAD'
    assert codec.decode(LEGACY_NFD, key=key, aad='fixture-channel') == payload
    assert codec.decode(IMPLICIT_107_NFC, key=key, aad='fixture-channel', key_normalization='NFC') == payload
    for envelope, mode in ((LEGACY_NFD, 'NFC'), (IMPLICIT_107_NFC, 'none')):
        with pytest.raises(ValueError, match='MAC verification failed'):
            codec.decode(envelope, key=key, aad='fixture-channel', key_normalization=mode)
    with pytest.raises(ValueError, match='MAC verification failed'):
        codec.decode(LEGACY_NFD, key=key, aad='wrong')
