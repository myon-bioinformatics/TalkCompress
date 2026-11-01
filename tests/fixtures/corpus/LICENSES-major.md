# 主要10言語コーパス（en/zh/es/hi/ar/pt/fr/ru/ja/de）のライセンス表示

- `tatoeba/<lang>.jsonl`（tier=short）: Tatoeba（https://tatoeba.org/）の文。OPUS-Tatoeba v2023-04-12 mono
  （https://opus.nlpl.eu/Tatoeba/）経由。CC BY 2.0 FR（https://creativecommons.org/licenses/by/2.0/fr/）。
  著作者は Tatoeba 投稿者。OPUS mono には文 ID・投稿者名が含まれないため、行の author は「Tatoeba contributors」。
- `flores200/<lang>.jsonl`（tier=medium / long）: FLORES-200 dev+devtest（NLLB Team, Meta AI,
  https://github.com/facebookresearch/flores/blob/main/flores200/README.md）。CC BY-SA 4.0
  （https://creativecommons.org/licenses/by-sa/4.0/）。long は同じ元記事の文を空白で連結した改変物で、CC BY-SA 4.0 で配布する。
  行の url は FLORES メタデータにある元記事（Wikinews / Wikivoyage / Wikibooks）。

同梱は tier ごと先頭 20 件のサンプルのみ。全件は `python scripts/fetch_corpus_major.py`
（stdlib のみ、取得元 sha256 固定）で `.cache/corpus/major/` に生成する。
