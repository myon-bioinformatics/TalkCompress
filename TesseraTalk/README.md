# TesseraTalk（B）

**層2 — 機械 + 高度な人間。** 文ごとに言語が切り替わるモザイク。LTR + 。！？ を当面の前提。

**重み:** 翻訳によるトークン削減。**EN + ZH + JA は開始セットであり、ハードな言語天井ではない。** スコープには Romance（es / fr / pt / it）、Germanic（de / nl / en）、Greek（el）、および ja / zh が入る。自然に短い形（翻訳由来の略語含む）は許容。C の合意台帳パッチ（under→下 など）は **適用しない**。

## できること

- 文分割（`.!?。？！…`）
- Unicode スクリプト + 軽い語彙／表記キューによるヒューリスティック LID（Romance / Germanic / Greek 含む）
- `compress` → モザイク / `expand` → 平文 / `tag` → `[lang] …`
- **RLE モザイク（既定オン）**: 連続する同言語では言語タグを省略し継承

  ```
  en:Hello.|World.|ja:こんにちは。
  ```

  `expand` は旧形式 `lang:sent|lang:sent` と RLE の両方を受理。`--no-rle` で常にフルタグ。
- `--stats` で文数・言語ヒストグラム（JSON → stderr）
- **翻訳トークン最短（opt-in）**: `--translate-min` / `translate_min=True`

  文ごとに `fixtures/translations.json` の候補を `estimate_tokens` で比較し、**厳密に短いときだけ**採用。既定は **fixture エンジン**（pytest 決定的・オフライン）。C 台帳とは別経路。

- **ライブ MT（opt-in）**: `--translate-engine=argos|deep`

  対象言語（Romance / Germanic / el / ja / zh）へ **並列翻訳**し、`estimate_tokens` の短さ＋**揺らぎ（曖昧さ）ペナルティ**で選ぶ。最短でも意味がぶれる語（例: `set` / `table`）は、少し長いが明確な候補や原文に負けることがある。

  | engine | 依存 | 備考 |
  | --- | --- | --- |
  | `fixture`（既定） | なし | バンクのみ。CI / pytest 用（決定的・オフライン） |
  | `deep` | `uv sync --group translate`（`deep-translator`） | 並列・ネットワーク |
  | `argos` | 別途 `argostranslate` + 言語パック | 並列・オフライン可だが重い。default sync には入れない |

  未インストール時は静かにバンク／原文へフォールバック（例外にしない）。

```bash
uv run python TesseraTalk/tessera_talk.py tag --text 'Hello. こんにちは. Hola. Guten Tag. Γεια σου.'
uv run python TesseraTalk/tessera_talk.py compress --text 'Hello. World. こんにちは。'
uv run python TesseraTalk/tessera_talk.py compress --no-rle --text 'Hello. World.'
uv run python TesseraTalk/tessera_talk.py expand --text 'en:Hello.|World.|ja:こんにちは。'
uv run python TesseraTalk/tessera_talk.py compress --stats --text 'Hello. こんにちは。'
uv run python TesseraTalk/tessera_talk.py compress --translate-min --text 'Good morning. Please reply as soon as possible.'
uv run python TesseraTalk/tessera_talk.py compress --translate-min --allow-langs es,fr,de,el --text 'I would be grateful if you could assist me with this issue.'
# optional live (needs --group translate):
# uv run python TesseraTalk/tessera_talk.py compress --translate-min --translate-engine deep --text 'Hello friends.'
```

## prefer-ltr / script_mix

`--prefer-ltr` biases Latin+CJK mixes without kana toward `en` rather than `zh`. `script_mix(text)` returns script counts/ratios; included in `--stats` JSON.

## C との境界

| | B TesseraTalk | C ShorthandEdge |
| --- | --- | --- |
| 短縮の主因 | 文の翻訳でトークンが減るなら採用 | 登録済み略語・合意台帳 lex |
| 略語 | 翻訳結果として自然に出るもの OK | パッチ／台帳で明示登録 |
| under→下 等 | しない（翻訳バンク経由のみ） | 台帳で適用 |
| 言語スコープ | Romance / Germanic / Greek + ja/zh（EN+ZH+JA は開始セット） | 台帳ベースは EN+ZH+JA 寄り、cognate 可 |

## Round notes

翻訳バンクに ES/FR/PT/IT/DE/NL/EL を拡充。`--translate-min` は DensityZip 経由でも可。`--translate-engine=deep|argos` は並列多言語→長さ＋揺らぎで採用。
