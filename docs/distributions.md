# TalkCompress の最小配布（minpy バンドル）

Aoi の [distributions.md](https://github.com/myon-bioinformatics/Aoi/blob/main/docs/distributions.md) と同じやり方で、
標準ライブラリだけで動く単一ファイルを `dist/` に置く。

| 配布 | 単一ファイル | 元 | 提供範囲 |
|---|---|---|---|
| kgraph | `dist/kgraph_min.py` | `shared/kgraph.py` | 型付きノードと三つ組、述語ごとの隣接リスト（両方向）、逆引き索引、関係種別で絞った幅優先探索、status 集計、`graphlib` による依存順と循環検出 |

TalkCompress のデータ（対応表・往復記録）は含めない。それを読むのは `scripts/mapping_graph.py`（docs/ontology/）で、
グラフの核だけを自前の標準ライブラリ実装として切り出して配る。Python 3.11 以降で `python -I -S` でも import できる。

## コンパイラの取得元（親から直接ピン留め）

孫リポジトリは共有ツールを **Aoi 経由** で vendor する規則がある。TalkCompress は Aoi の子ではない:

- `docs/subprojects.md` のとおり、TalkCompress は A–E の親で、真親（myon-bioinformatics/myon-bioinformatics）の
  `child-heads.json` / vendor-consumers には載せず、共有ワークフローは `uses:` で **親リポの SHA に直接** ピン留めしている。
- Aoi の `docs/child-repositories.md` にも TalkCompress は載っていない（Aoi の subtree 子ではない）。
- TalkCompress には py_launch.cjs や vendor-lock JSON のような Aoi 経由の vendor 設定が無い。

したがって TalkCompress は親の直接の子として扱い、Aoi 自身と同じく **親の `tools/minpy.py` を直接** ピン留めする。

## 登録と再生成

`distributions.json` が配布レジストリ（schema `talkcompress-distributions/1`。項目の意味は Aoi の `aoi-distributions/1` と同じ）。

- `source`: 入口（`shared/kgraph.py`）を凍結した commit。成果物を含める後続 commit から参照し、自己参照を避ける。
- `tool`: 親の `tools/minpy.py` の取得元 commit と SHA-256。**import する前に毎回照合** する。
  ピンは minpy の最新版が親 main に入ったマージコミット
  `26c442bc51b8a2837fe2556782b2937f396932af`（親 PR #230）で、SHA-256 は
  `4c3c6890495fbbca9b4539474ff9f56cd2eaff7c66feae219f6e5a8a463839e1`。
- `python`: 生成に使う major.minor。リポの `.python-version` と同じ 3.14。生成物のバイト列は minor に依存する。
- `license`: `LICENSE` を `dist/LICENSE` に同梱する（MIT 通知）。
- `projects.<name>`: `entry`・`paths`（minpy の検索パス）・`watch`（ピンと照合するファイル）・`output`（`dist/*_min.py`）。

```sh
uv run python scripts/build_distributions.py           # dist/ を再生成
uv run python scripts/build_distributions.py --check   # 書き込まずに一致を確認
```

`--minpy` を省くと、ピンの commit の raw ファイルを一度だけ `.test-deps/`（gitignore）に取得し、SHA-256 を照合してから使う。
照合に失敗したら import しない。生成は全部作ってから書き、`--check` は書き込まない。`allow` が空でない（標準ライブラリ以外を含む）
バンドルは拒否する。新しい環境変数は使わない。

`source` の commit が手元の履歴にあれば、`watch` のファイルがその commit から変わっていないこと、未追跡ファイルが無いことを
確かめてから、その commit のスナップショットで生成する（Aoi と同じ）。浅い clone（CI）でその commit が無い場合はピンを証明できないので、
作業ツリーのファイルから同じ commit 名で生成してバイト比較だけ行う（元が変われば比較で検出できる）。
結果 JSON の `source_pin_verified` でどちらだったかを示す。

## テスト

`tests/test_distributions.py`（`uv run pytest` で実行、ワークフローの変更なし）:

- コミット済みバンドルのヘッダ（repository / commit / entry / python / allow 空）と content-sha256 の自己ハッシュ
- `dist/LICENSE` が `LICENSE` と同じ
- コピーしたバンドルだけを `python -I -S` で import して API を動かす
- Python が `distributions.json` の minor と同じとき、ピン留めした minpy で再生成して **コミット済みバンドルとバイト一致** すること
  （他の minor では skip、ネットワークが無く minpy を取得できないときも skip）
- 偽の minpy は SHA-256 照合で import 前に拒否される

`shared/kgraph.py` を変えたら、変更を commit → `distributions.json` の `source` を更新 → 再生成、の順にする。
