# 多言語テストコーパス：ライセンス・置き場所・manifest

トークンの測り直しと「変換 → AI に元へ戻させる」往復テスト用の多言語テキストの扱いを決める。
収集の分担：主要言語＝3bot、1億話者未満・多文字種＝4bot、口語/ASR/文字化け/絵文字・コード混在＝5bot、
ライセンス確認・置き場所・manifest＝2bot（この文書）。

## 1. 許可するライセンス

| 可否 | ライセンス | manifest の `license` 値 |
|---|---|---|
| 可 | CC0 1.0 | `CC0 1.0` |
| 可 | パブリックドメイン（米国著作権切れ・米国政府著作物など） | `Public domain` |
| 可（表示義務） | CC BY 2.0 FR / 3.0 / 4.0 | `CC BY 2.0 FR` ほか |
| 可（表示＋継承） | CC BY-SA 3.0 / 4.0 | `CC BY-SA 4.0` ほか |
| **不可** | NC（非営利）・ND（改変禁止）・独自規約・ライセンス不明 | — |

ND を外すのは、圧縮変換そのものが「改変」にあたるため。許可リストは
`scripts/corpus_manifest.py` の `ALLOWED_LICENSES` が正で、ここに無い値は検証で落ちる。
追加したいときはこの表とコードを同じ PR で直す。

## 2. 出典ごとの判定

| 出典 | ライセンス | 判定 | 根拠 | 注意 |
|---|---|---|---|---|
| Wikipedia 本文 | CC BY-SA 4.0（一部 GFDL 併用） | 可（BY-SA） | https://en.wikipedia.org/wiki/Wikipedia:Copyrights | 記事 URL・版 ID（oldid）を記録。執筆者表示は記事履歴へのリンクで可。引用画像・フェアユース部分は除く |
| Tatoeba 文 | 文ごとに CC BY 2.0 FR（一部 CC0 1.0） | 可 | https://tatoeba.org/en/terms_of_use / API の `license` 欄 | 文 ID と投稿者名（owner）を行ごとに保持。owner が無い孤児文と `is_unapproved` は入れない。音声は別ライセンスなので使わない |
| FLORES-200（dev/devtest） | CC BY-SA 4.0 | 可（BY-SA） | https://github.com/facebookresearch/flores/blob/main/flores200/README.md | 評価用セット。数百 KB 規模なので外部取得＋sha256 固定 |
| Common Voice 文テキスト（validated_sentences） | CC0 1.0 | 可 | https://commonvoice.mozilla.org/en/datasets | テキストのみ使う。音声は CC0 だが大容量・本件は不要。話者メタデータは入れない |
| Project Gutenberg（米国 PD 作品） | Public domain（米国） | 可 | https://www.gutenberg.org/policy/license.html | 既存 `tests/fixtures/pd_corpus/` と同方針。Gutenberg のヘッダ/フッタ（商標条項）は削る |
| OPUS: Tatoeba サブセット | CC BY 2.0 FR | 可 | https://opus.nlpl.eu/Tatoeba/ | 本家 Tatoeba から取る方が投稿者表示が楽 |
| OPUS: WikiMatrix | CC BY-SA 4.0 | 可（BY-SA） | https://opus.nlpl.eu/WikiMatrix/ | 自動抽出の対訳で質にムラ。往復テストには不向き、トークン計測向け |
| OPUS: Europarl | 欧州議会の再利用規約（明示の CC ではない） | **保留** | https://www.europarl.europa.eu/legal-notice/en/ | 許可リスト外なので入れない。必要なら別途確認 |
| OPUS: OpenSubtitles / CCMatrix / ParaCrawl など | 権利不明・クロール由来 | **不可** | 各 OPUS ページ | 字幕・Web クロールは元の著作権が不明 |
| Universal Dependencies 各ツリーバンク | ツリーバンクごとに異なる（CC BY-SA / CC BY-NC-SA 混在） | 個別判定 | 各ツリーバンクの LICENSE | NC のもの（例：一部の日本語 UD）は不可 |
| Aozora Bunko | 著作権切れ作品は PD | 可（作品単位で確認） | https://www.aozora.gr.jp/guide/kijyunn.html | 「著作権存続」作品は除く。入力者表示を残す |

OPUS は**サブセットごとに必ず個別確認**し、manifest には元コーパスのライセンスを書く。

## 3. 表示義務と継承（BY / BY-SA）

- 各 JSONL 行に `source` / `license` / `author`（分かる範囲）/ `url`（元文書や文 ID の URL）を持たせる。
  manifest の `attribution` 欄で行単位表示の場所を示す。
- BY-SA 由来のファイルは、そのファイル（改変・圧縮した派生物を含む）を BY-SA で配布する。
  リポジトリのコードは MIT のままで、`tests/fixtures/corpus/` 以下のデータだけが各ライセンスに従う。
- 改変（圧縮変換結果をフィクスチャとして保存する等）をした場合は「改変あり」と出典に書く。

## 4. 置き場所（チーム合意）

```
tests/fixtures/corpus/
  manifest.json              # 全エントリ（同梱サンプル・外部取得の両方）
  manifest.schema.json       # 参照用 JSON Schema（正は scripts/corpus_manifest.py）
  <category>/<lang>.jsonl    # 小さいサンプルのみ
```

- `<category>` は内容の種類（例：`sentence` 一般文・対訳、`wiki` 百科、`asr` 書き起こし・口語、
  `mojibake` 文字化け、`mixed` 絵文字/記号/数式/コード混在）。小文字英数と `_` `-`。
- `<lang>` は ISO 639-1（無ければ 639-3）。文字種の区別が要るなら `sr-Latn` のような BCP 47 副タグ。
- JSONL 1 行 = `{"id","text","lang","tier","source","license","author","url"}`。
  **tier（`short` 1 文 / `medium` 数文の段落 / `long` 記事・章の抜粋）は行ごとの欄**で、パスには入れない。
- **生の元データはコミットしない。** コミットするのは取得スクリプト、小さいサンプル、ライセンス表示だけ。
  同梱サンプルは 1 ファイル 256 KB（262144 バイト）以下・`tests/fixtures/corpus/` 全体 5 MB（5242880 バイト）以下。`check` が強制する。
  それ以上（FLORES-200 全体、Common Voice 全文、Wikipedia 抜粋の大量分など）は manifest に
  `fetch_url` と `sha256` を書き、`scripts/corpus_fetch.py` で `.cache/corpus/`（git 管理外）に取る。
  sha256 が合わなければ保存しない。CI はネットワークを使わず同梱分だけで回す。
- 1 言語 × 1 tier あたり数百件を目標。同梱に収まらない分は外部取得側に回す。

## 5. manifest

必須項目：`id, category, source, url, license, license_url, lang, count, bytes, o200k_tokens,
sha256, retrieved_at, ai_roundtrip`、それに `path`（同梱。`<category>/<lang>.jsonl`）か
`fetch_url`（外部）のどちらか一方。任意で `attribution`。

- `count` 件数、`bytes` 各 text の UTF-8 バイト合計、`o200k_tokens` 各 text を o200k_base で個別に
  エンコードしたトークン数の合計、`sha256` ファイル全体のハッシュ。
- `ai_roundtrip` は測るまで `"未測定"`。測ったら手法と結果を短く書く。

`tests/test_corpus_manifest.py` が各 PR で次を検査する：
同梱ファイルの存在、sha256/count/bytes/o200k の実測一致、ライセンスが許可リスト内（行単位も）、
`id`・`(category, lang, source)`・`path` の manifest 内重複なし、manifest に載っていない孤児 jsonl なし、
1 ファイル 256 KB／全体 5 MB の上限。
各行は JSON object で、`id,text,lang,tier,source,license,author,url` が空でない文字列、
tier が short/medium/long、行の `lang`・`license` が manifest エントリと一致、ファイル内 `id` 重複なし。

**依存の例外：** 共有 Python ツールは単一ファイル・stdlib のみが原則だが、`scripts/corpus_manifest.py` は
o200k トークン数を数えるためだけに `tiktoken`（dev 依存）を使う明示的な例外とする（遅延 import）。
`scripts/corpus_fetch.py` は stdlib のみ（urlopen タイムアウト 60 秒、id は `[A-Za-z0-9][A-Za-z0-9._:-]*` で検証し、
保存先が `.cache/corpus/` の外に出ないことを確認）。

```
uv run python scripts/corpus_manifest.py measure tests/fixtures/corpus/sentence/ja.jsonl
uv run python scripts/corpus_manifest.py update   # 同梱ファイルの数値を再計算して書き戻す
uv run python scripts/corpus_manifest.py check    # 検証
uv run python scripts/corpus_fetch.py [--id X]    # 外部取得 + sha256 照合
```

数値は必ず `update` で実測したものを入れる。手書きの数値は `check` で落ちる。

## 6. シード（このPR）

Tatoeba API（2026-11-01 取得）から ja / en / fr の短文を 11〜12 件ずつ（`sentence/<lang>.jsonl`、tier=short）。
孤児文・未承認文は除外。数値は manifest.json を参照（実測）。AI 往復は未測定。
