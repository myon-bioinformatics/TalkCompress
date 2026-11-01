# 主要10言語コーパス（en/zh/es/hi/ar/pt/fr/ru/ja/de）のライセンス表示

- `tatoeba/<lang>.jsonl`（tier=short）: Tatoeba（https://tatoeba.org/）の文。OPUS-Tatoeba v2023-04-12 mono
  （https://opus.nlpl.eu/Tatoeba/）経由。CC BY 2.0 FR（https://creativecommons.org/licenses/by/2.0/fr/）。
  著作者は Tatoeba 投稿者。OPUS mono には文 ID・投稿者名が含まれないため、行の author は「Tatoeba contributors」。
- `flores200/<lang>.jsonl`（tier=medium / long）: FLORES-200 dev+devtest（NLLB Team, Meta AI,
  https://github.com/facebookresearch/flores/blob/main/flores200/README.md）。CC BY-SA 4.0
  （https://creativecommons.org/licenses/by-sa/4.0/）。long は同じ元記事の文を空白で連結した改変物で、CC BY-SA 4.0 で配布する。
  行の url は FLORES メタデータにある元記事（Wikinews / Wikivoyage / Wikibooks）。

OPUS / FLORES 同梱分は tier ごと先頭20件。Tatoeba en/fr/ja は別途 API seed を含み、ja は公式詳細配布からの口語文も含む。source=Tatoeba の行では acquisition_source に取得経路、author/url に著者と出典を保持する。公式配布・API 分も CC BY 2.0 FR だが OPUS 由来ではない。

全件は `python scripts/fetch_corpus_major.py`
（stdlib のみ、取得元 sha256 固定）で `.cache/corpus/major/` に生成する。

## 全件の取得元（sha256 固定）

manifest のエントリは同梱サンプル（`path`）だけです。全件は次のアーカイブから `scripts/fetch_corpus_major.py` で生成します。
`fetch_url` のエントリにしていないのは、アーカイブ1つが複数の言語や派生ファイルに対応していて、
#134 のスキーマ（count/bytes/o200k_tokens は `update` の実測値）と1対1に合わないためです。

| 取得元 | fetch_url | sha256 |
|---|---|---|
| FLORES-200 | https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz | b8b0b76783024b85797e5cc75064eb83fc5288b41e9654dabc7be6ae944011f6 |
| Tatoeba en | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/en.txt.gz | a32c5500cd76b9479859764fb78537a4b9b53fab8fa3bdc0fc04dd70f28bf29b |
| Tatoeba zh | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/cmn.txt.gz | 7d8c04289d38802096685c567d81d7aba4f22c704a9483f475eff87997a5e8dc |
| Tatoeba es | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/es.txt.gz | 755ee3bdccfb8465ba8250a6626ee7b32faeb2d1f62eb7f185c34ba118073aa0 |
| Tatoeba hi | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/hi.txt.gz | 6de9ff2cca108d04a41d9a3e09f1afebd4f8ada29a9c7178f05eb57ad7dd96c3 |
| Tatoeba ar | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/ar.txt.gz | 7060d6d2b0b2313e9a9e4449ad976203f741e7729ab20a702051ed6d0ff6ed5d |
| Tatoeba pt | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/pt.txt.gz | d47a3c64769a29cad793d98cf035974b5b13230657e151ef8151109d54be4bf1 |
| Tatoeba fr | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/fr.txt.gz | 79a452df4bb738269822dad847ea5db44b8eb5d362d8d9ef7b66305f38098b5d |
| Tatoeba ru | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/ru.txt.gz | c4128c01ad0746fd83699545f166c3645afa4593233a6335f7dbb5d296579c79 |
| Tatoeba ja | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/ja.txt.gz | 61ef5f80aa418354c3b879088cc51d90c20970c921404bce7b17531b0059a4c9 |
| Tatoeba de | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/de.txt.gz | 9a0c846db1a9847a6ded516ff107f0da09fb30dd4dda33c8dcfd6ec9fccc35d4 |

- long の連結: ja と zh は区切りなし、それ以外は半角スペース1つ。
- Tatoeba の一次出典は https://tatoeba.org/ （利用規約 https://tatoeba.org/en/terms_of_use ）。OPUS: https://opus.nlpl.eu/Tatoeba/
- FLORES の ja medium の先頭にある「1円ほどす。」は原文のままで、取り込み時に崩れたものではありません。
