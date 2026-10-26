# MorphoZip（E）

**層4 — 文内多言語・文法最小。** 予測候補が少ない短い形を優先。語彙の一意読み（rank-1）もここで扱う。

## 方針

- 一人称 → `I`（私は/僕は/俺は…を潰す）
- 接続 → `&` `/` `w/` `w/o` など
- whatever 系 → `∀` / `∀loc` / `∀who` … / hereafter → `∴→`
- 助数詞: JA 既存は維持。EN 数量句も実験的に短くする（`3 animals` → `3匹`, `2 people` → `2人`, `5 pieces` → `5個`, `4 times` → `4回` など）
- 性による屈折は避け、彼は/彼女は / he or she → `they`
- 数字は既定で `0-9`。`--hex-nums` で小文字16進（`255` → `0xff`）。`--hex-bare` で `0x` なし（`0-F` スタイル）
- 中国語偏重なし。`--stats` で文字密度

## 語彙ポリシー（揺らぎ削減）

`shared/lex_policy.py` を利用:

1. **FILLER 除去** — um / えーと / I mean など
2. **一意読み** — 多義の基本動詞を論文調・手順寄りの語へ（find out → ascertain → `ascrt` など）
3. **語源寄せ** — 近縁 LTR で共有ルートが見える短い形へ（information/información → `info`）。FR `nombre` は偽友なので対象外

F サブプロジェクトは作らず、この層に集約。C（ShorthandEdge）は FILLER 除去のみ共有。

```bash
uv run python MorphoZip/morpho_zip.py --text 'um 私は will find out the information'
uv run python MorphoZip/morpho_zip.py --stats --text 'I am here with you'
uv run python MorphoZip/morpho_zip.py --text 'I see 3 animals and 2 people'
uv run python MorphoZip/morpho_zip.py --hex-nums --text 'retry 255 times'
uv run python MorphoZip/morpho_zip.py --no-unique --text '...'   # 一意化オフ
```

## Protected spans

`[[keep:...]]` and `` `keep:...` `` wrappers are stripped; inner text is preserved unchanged through compress. `--protect-regex` (repeatable) masks full matches the same way.

