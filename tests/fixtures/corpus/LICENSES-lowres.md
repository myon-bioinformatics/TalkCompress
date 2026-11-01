# コーパス出典とライセンス（ko/vi/th/id/tr/he/fa/sw/bn/ta）

`scripts/fetch_corpus_lowres.py` が取得・生成する `short/`・`medium/`・`long/` の各 `<lang>.jsonl` の出典です。リポジトリにはサンプル（各ファイル先頭 20 件）だけを置き、全量は同スクリプトで `build/corpus/` に再生成します。取得元アーカイブは sha256 で固定しています。

| category | 出典 | ライセンス | 帰属表示 |
|---|---|---|---|
| short | Tatoeba（OPUS-Tatoeba v2023-04-12 mono） https://tatoeba.org/ | CC BY 2.0 FR | Tatoeba の各文の投稿者（https://tatoeba.org/ 上の文ごとの contributor）。OPUS: J. Tiedemann, "Parallel Data, Tools and Interfaces in OPUS", LREC 2012 |
| medium | FLORES-200 dev+devtest（単文） https://github.com/facebookresearch/flores | CC BY-SA 4.0 | NLLB Team et al., "No Language Left Behind", 2022; Goyal et al., "The FLORES-101 Evaluation Benchmark", 2021 |
| long | FLORES-200 dev+devtest（同一記事 URL の連続文を空白で連結） | CC BY-SA 4.0 | 同上。原文は Wikinews・Wikijunior・Wikivoyage（CC BY 系） |

- `long` は FLORES-200 の改変物（連結）なので、CC BY-SA 4.0 の継承条件に従います。
- NC・ND のデータは含みません。
