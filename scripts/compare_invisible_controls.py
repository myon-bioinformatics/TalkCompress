"""Reproduce #147 against a pinned git baseline and Tatoeba per_language exports.

Dev-only tiktoken. Input files are <ISO639-3>.tsv.bz2, downloadable with
--download. No corpus is redistributed: output records sentence IDs, source URLs,
input SHA256 and split membership. Keep the downloaded inputs to replay the exact
snapshot; current upstream exports may change. --expected checks input hashes.
"""
from __future__ import annotations

import argparse
import bz2
import hashlib
import json
import math
from pathlib import Path
import random
import re
import subprocess
import sys
import types
import unicodedata
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from TesseraTalk import tessera_talk as current
import tiktoken

BASE = 'adf9fcf49e2f7ee8695819e00929f9bd0673c6ae'
LANGS = ('ben', 'sin', 'khm', 'tha', 'lao', 'tam', 'mya', 'ori')
CONTROLS = '\u200b\u200c\u200d'
CHARS = r'[\u0980-\u0DFF\u0E80-\u0FFF\u1000-\u109F\u1780-\u17FF]'
BRIDGE = re.compile('(' + CHARS + '+)([\u200b-\u200d]+)(?=' + CHARS + ')')
EXAMPLES = ['அກ\u200bຂ', 'কກ\u200bຂ', 'ກ\u200bຂক', 'කක\u200dකক', 'កខ\u200bគஅ', 'ශ්‍රී', 'ශ්\u200bරී', 'ශ්\u200cරී', 'ក្\u200dខ', 'ក្\u200cខ', 'ක\u200cක', 'ক্‍ষ', 'ক্‌ষ', 'ক\u200bখ',
            'កម្ពុជា\u200bជាប្រទេស\u200bដ៏ស្រស់ស្អាត', 'ଓଡ଼ିଆ',
            'ଓ\u200bଡ଼ିଆ', 'ଓ\u200cଡ଼ିଆ', 'ଓ\u200dଡ଼ିଆ',
            '👨‍👩‍👧‍👦', '👩🏽‍💻', '❤️', '☺️',
            'abcශ්‍රීxyz', 'ไทยລາວ', 'ක\u200bក', 'ক\u200bක',
            '\u200bක', 'ක\u200b', 'ක\u200b\u200bක', 'ක\u200d👩',
            'क्‍ष', 'ক্‍ষ ශ්‍රී ខ្មែរ', 'Hello world. こんにちは。']


def baseline(ref):
    src = subprocess.check_output(['git', 'show', ref + ':TesseraTalk/tessera_talk.py'], cwd=ROOT, text=True)
    mod = types.ModuleType('_invisible_baseline')
    mod.__file__ = current.__file__  # calibration fixture path stays identical
    sys.modules[mod.__name__] = mod
    exec(compile(src, mod.__file__, 'exec'), mod.__dict__)
    return mod


def run():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-dir', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--baseline', default=BASE)
    ap.add_argument('--download', action='store_true')
    ap.add_argument('--expected', type=Path, help='Prior report whose input hashes must match')
    args = ap.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    old = baseline(args.baseline)
    enc = tiktoken.get_encoding('o200k_base')
    merged = re.compile(old._PRETOKEN.pattern.replace('(?P<i>' + CHARS + '+)',
                        '(?P<i>' + CHARS + '+(?:[\u200b-\u200d]+' + CHARS + '+)*)'), old._PRETOKEN.flags)

    def include(s):
        n = old.estimate_tokens(s)
        s = unicodedata.normalize('NFC', s)
        for m in merged.finditer(s):
            p = m.group()
            if m.lastgroup == 'i' and any(c in p for c in CONTROLS):
                clean = re.sub('[\u200b-\u200d]', '', p)
                n += math.ceil(len(clean) / old._brahmic_rate(p[0])) - old.estimate_tokens(p)
        return n

    def correction(s):
        n = old.estimate_tokens(s)
        s = unicodedata.normalize('NFC', s)
        return n - sum(old.estimate_tokens(m.group(2)) for m in BRIDGE.finditer(s))

    methods = {'main': old.estimate_tokens, 'include_all': include,
               'correct_all': correction, 'selected': current.estimate_tokens}
    def row(s, sid=None):
        return {'id': sid, 'actual': len(enc.encode(s, disallowed_special=())),
                **{name: fn(s) for name, fn in methods.items()}}

    def metrics(rows):
        return {name: {'n': len(rows), 'ratio': sum(r[name] for r in rows) / max(1, sum(r['actual'] for r in rows)),
                       'mae': sum(abs(r[name] - r['actual']) for r in rows) / max(1, len(rows)),
                       'exact': sum(r[name] == r['actual'] for r in rows)} for name in methods}

    report = {'baseline': args.baseline, 'tiktoken': tiktoken.__version__, 'encoding': 'o200k_base',
              'normalization': 'raw input to estimator and o200k; candidates normalize NFC as main does',
              'seed': 1104, 'inputs': {}, 'languages': {}, 'examples': [], 'compression_comparisons': 0}
    expected = json.loads(args.expected.read_text())['inputs'] if args.expected else None
    parity = 0
    def check_outputs(s):
        nonlocal parity
        for opts in ({'rle': True}, {'rle': False, 'preserve_newlines': True},
                     {'rle': True, 'translate_min': True}):
            a, b = old.compress(s, **opts), current.compress(s, **opts)
            if a != b or old.expand(a) != current.expand(b):
                raise SystemExit('Compression/expansion output changed: ' + repr(s))
            parity += 1

    for lang in LANGS:
        url = f'https://downloads.tatoeba.org/exports/per_language/{lang}/{lang}_sentences.tsv.bz2'
        path = args.data_dir / (lang + '.tsv.bz2')
        if args.download and not path.exists():
            path.write_bytes(urllib.request.urlopen(url, timeout=60).read())
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if expected is not None and expected[lang]['sha256'] != digest:
            raise SystemExit('Input snapshot changed: ' + lang)
        # Deduplicate text before sorting/shuffling, exactly as #145. Keep a stable ID.
        by_text = {}
        for line in bz2.decompress(raw).decode('utf-8').splitlines():
            sid, _, text = line.split('\t', 2)
            by_text.setdefault(text, sid)
        texts = sorted(by_text)
        random.Random(1104).shuffle(texts)
        k = min(200, len(texts) // 2)
        report['inputs'][lang] = {'url': url, 'sha256': digest, 'unique': len(texts)}
        report['languages'][lang] = {}
        for split, ss in [('fit', texts[:k]), ('held_out', texts[k:2*k])]:
            rows = [row(s, by_text[s]) for s in ss]
            controls = [r for s, r in zip(ss, rows) if any(c in s for c in CONTROLS)]
            report['languages'][lang][split] = {'metrics': metrics(rows), 'control_metrics': metrics(controls), 'rows': rows}
            for s in ss:
                check_outputs(s)
        # Natural controls omitted from the 400-sentence sample are reported separately;
        # this is diagnostic, not a second held-out selection or a tuning set.
        cs = [s for s in texts if any(c in s for c in CONTROLS)]
        report['languages'][lang]['all_natural_controls'] = {'metrics': metrics([row(s) for s in cs]),
                                                          'ids': [by_text[s] for s in cs]}
    for s in EXAMPLES:
        report['examples'].append({'text': s, **row(s), 'o200k_ids': enc.encode(s)})
        check_outputs(s)
    for lang, splits in report['languages'].items():
        held = splits['held_out']['metrics']
        if held['selected']['mae'] > held['main']['mae']:
            raise SystemExit('Held-out MAE regression: ' + lang)
    report['compression_comparisons'] = parity
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: {s: v[s]['metrics'] for s in ('fit', 'held_out')} for k,v in report['languages'].items()}, indent=2))
    print('Compression/expansion comparisons:', parity)


if __name__ == '__main__':
    run()
