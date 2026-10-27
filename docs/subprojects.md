# サブプロジェクト（A–E）と git subtree

TalkCompress は A–E の**親**です。将来まとめて切り出すときは Aoi の子リポと同様に `git subtree` で同期する想定です。いまは独立しそうにないので、同一リポ内のディレクトリのまま進めます。

| ID | ディレクトリ | 層 |
| --- | --- | --- |
| A | `Zipilogue/` | 1 機械同士（共有ルール / 任意封筒） |
| B | `TesseraTalk/` | 2 文単位多言語 + 翻訳トークン最短 |
| C | `ShorthandEdge/` | 3 人間ギリギリ（合意台帳はここ） |
| D | `DensityZip/` | 横断オーケストレーション + **density** 指標ファサード |
| E | `MorphoZip/` | 4 文内・文法最小・代名詞在庫ビット |

### Zip 名の区別

A **Zipilogue** / D **DensityZip** / E **MorphoZip** は別物。散文では単独の「Zip」を使わずフルネームで書く。モジュールも `density_zip.py` / `morpho_zip.py` / `zipilogue.py` とフルに揃える。

## 真親への登録はしない

[myon-bioinformatics/myon-bioinformatics](https://github.com/myon-bioinformatics/myon-bioinformatics) の `child-heads.json` / vendor-consumers などには**載せません**。共有ワークフロー（change-detection・junit-identity）は `uses:` で親リポの SHA にピン留めするだけです。

## 後から切るとき（メモ）

Aoi の [child-repositories.md](https://github.com/myon-bioinformatics/Aoi/blob/main/docs/child-repositories.md) と同じ系統:

1. `git subtree split --prefix=<Dir>` で履歴を切り出し
2. 子リポの main に push（force なし・merge commit）
3. 必要ならこちらへ `git subtree pull`（`--squash` なし）

独立の気配が出てからでよいです。
