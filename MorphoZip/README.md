# MorphoZip（E）

**層4 — 文内多言語・文法最小。** 予測候補が少ない短い形を優先。一意読み（rank-1・長い形）と語源寄せもここで扱う。

## 方針

- 一人称 → `I`（私は/僕は/俺は…を潰す）
- 接続 → `&` `/` `w/` `w/o` など
- whatever 系 → `∀` / `∀loc` / `∀who` … / hereafter → `∴→`
- 助数詞: JA 既存は維持。EN 数量句も実験的に短くする（`3 animals` / `three animals` → `3匹`, `2 people` → `2人` など）
- スペル数字 → 数字（`three`→`3`, `twenty-one`→`21`）。助数詞の前に適用
- 冠詞: 引用なしの `the`/`a`/`an` は落とす。`"the"` / `'the'` は内側の語だけ残す（引用符は外す）。`--keep-articles` で無効化
- 軽い短縮: `I will` → `I'll`（`私は will` も先に `I` 化してから）
- 性による屈折は避け、彼は/彼女は / he or she → `they`
- 数字は既定で `0-9`。`--hex-nums` で小文字16進（`255` → `0xff`）。`--hex-bare` で `0x` なし（`0-F` スタイル）
- 中国語偏重なし。`--stats` で文字密度

## 語彙ポリシー（揺らぎ削減）

`shared/lex_policy.py` を利用（**E 既定**）:

1. **一意読み（長い形）** — find out → `ascertain`（UNIQUE_COMPACT の `ascrt` は付けない）
2. **語源寄せ** — information/info/情報/información → `ℹ️`（U+2139 U+FE0F）

**FILLER 除去と UNIQUE_COMPACT（ascrt など）は C（ShorthandEdge）の担当。** E 単体ではフィラーを残す。`--strip` / `--aggressive-fillers` でオプトイン可。パイプライン `C,E` なら C が先にフィラーを落とす。

```bash
uv run python MorphoZip/morpho_zip.py --text '私は will find out the information about three animals'
# → I'll ascertain ℹ️ about 3匹
uv run python MorphoZip/morpho_zip.py --stats --text 'I am here with you'
uv run python MorphoZip/morpho_zip.py --text 'I see 3 animals and 2 people'
uv run python MorphoZip/morpho_zip.py --hex-nums --text 'retry 255 times'
uv run python MorphoZip/morpho_zip.py --strip --text 'um ready'   # オプトイン
uv run python MorphoZip/morpho_zip.py --no-unique --text '...'   # 一意化オフ
```

## Protected spans

`[[keep:...]]` and `` `keep:...` `` wrappers are stripped; inner text is preserved unchanged through compress. `--protect-regex` (repeatable) masks full matches the same way.
