# 時制を統合した採用形（`--collisions` の `tense_merge`）

生成: `uv run python scripts/mapping_graph.py --collisions --markdown > docs/ontology/tense-merge-collisions.md`。
手で直さず再生成する（`tests/test_mapping_graph.py` が生成結果との一致を確認する）。

`tense_merge` は、同じ `lang:form` が同じ動詞の別時制の英語にも採用されている形。グラフは報告するだけで、採用は変えない（[mapping-ontology.md](mapping-ontology.md) 6 節）。

## 件数

`tense_merge`: 23 形（pt 10 / de 9 / es 3 / fr 1）。

| lang | 形の数 |
|---|---|
| de | 9 |
| es | 3 |
| fr | 1 |
| pt | 10 |

統合している時制の組み合わせ:

| 時制 | 形の数 | 形 |
|---|---|---|
| 過去＋現在完了 | 18 | `de:dachten`、`de:dachtest`、`de:fanden`、`de:kam`、`de:kamen`、`de:nahmen`、`de:sagten`、`de:sah`、`de:sahen`、`es:dije`、`es:dijeron`、`es:fui`、`pt:achaste`、`pt:demos`、`pt:deste`、`pt:deu`、`pt:fiz`、`pt:fomos` |
| 過去＋現在完了＋過去完了 | 2 | `pt:deram`、`pt:foram` |
| 現在＋未来 | 2 | `pt:vou`、`pt:vão` |
| 現在＋過去 | 1 | `fr:dit` |

同じ `--collisions` の他の分類（参考）: `cross_language` 0、`lang_label_mismatch` 0、`multi_meaning` 0。

## 往復で確かめた読み

往復の判定は形ごとの最新コホートで行い、復元させた英語はコホートの `targets[].source` に残る。
上の 23 形が採用されている英語は計 77 行で、そのうち最新コホートで復元対象だったのは 23 行。
最新コホートが測っていない時制を含む形は 23 形ある。その時制の英語へ AI が戻せるかは、往復ではまだ確かめていない。

## 一覧

| lang:form | 時制 | 採用している英語 | 最新コホートで復元させた英語 | status | 最新 restored/completed |
|---|---|---|---|---|---|
| `de:dachten` | 過去＋現在完了 | they thought（mx-think-past-3p）<br>they have thought（mx-think-perf-3p） ※未測定 | they thought | pass | 9/9 |
| `de:dachtest` | 過去＋現在完了 | you thought（mx-think-past-2）<br>you have thought（mx-think-perf-2） ※未測定 | you thought | pass | 9/9 |
| `de:fanden` | 過去＋現在完了 | we found（mx-find-past-1p）<br>they found（mx-find-past-3p） ※未測定<br>we have found（mx-find-perf-1p） ※未測定<br>they have found（mx-find-perf-3p） ※未測定 | we found | pass | 9/9 |
| `de:kam` | 過去＋現在完了 | i came（mx-come-past-1s）<br>he came（mx-come-past-3s-he） ※未測定<br>it came（mx-come-past-3s-it） ※未測定<br>she came（mx-come-past-3s-she） ※未測定<br>i have come（mx-come-perf-1s） ※未測定<br>he has come（mx-come-perf-3s-he） ※未測定<br>it has come（mx-come-perf-3s-it） ※未測定<br>she has come（mx-come-perf-3s-she） ※未測定 | i came | pass | 9/9 |
| `de:kamen` | 過去＋現在完了 | we came（mx-come-past-1p）<br>they came（mx-come-past-3p） ※未測定<br>we have come（mx-come-perf-1p） ※未測定<br>they have come（mx-come-perf-3p） ※未測定 | we came | pass | 9/9 |
| `de:nahmen` | 過去＋現在完了 | we took（mx-take-past-1p）<br>they took（mx-take-past-3p） ※未測定<br>we have taken（mx-take-perf-1p） ※未測定<br>they have taken（mx-take-perf-3p） ※未測定 | we took | pass | 9/9 |
| `de:sagten` | 過去＋現在完了 | we said（mx-say-past-1p）<br>we have said（mx-say-perf-1p） ※未測定 | we said | pass | 9/9 |
| `de:sah` | 過去＋現在完了 | i saw（mx-see-past-1s）<br>he saw（mx-see-past-3s-he） ※未測定<br>it saw（mx-see-past-3s-it） ※未測定<br>she saw（mx-see-past-3s-she） ※未測定<br>i have seen（mx-see-perf-1s） ※未測定<br>he has seen（mx-see-perf-3s-he） ※未測定<br>it has seen（mx-see-perf-3s-it） ※未測定<br>she has seen（mx-see-perf-3s-she） ※未測定 | i saw | pass | 9/9 |
| `de:sahen` | 過去＋現在完了 | we saw（mx-see-past-1p）<br>they saw（mx-see-past-3p） ※未測定<br>we have seen（mx-see-perf-1p） ※未測定<br>they have seen（mx-see-perf-3p） ※未測定 | we saw | pass | 9/9 |
| `es:dije` | 過去＋現在完了 | i said（say-past-1s）<br>i have said（mx-say-perf-1s） ※未測定 | i said | pass | 9/9 |
| `es:dijeron` | 過去＋現在完了 | they said（mx-say-past-3p）<br>they have said（mx-say-perf-3p） ※未測定 | they said | pass | 9/9 |
| `es:fui` | 過去＋現在完了 | i went（go-past-1s）<br>i have gone（mx-go-perf-1s） ※未測定 | i went | pass | 9/9 |
| `fr:dit` | 現在＋過去 | he says（mx-say-pres-3s-he）<br>it says（mx-say-pres-3s-it） ※未測定<br>she says（mx-say-pres-3s-she） ※未測定<br>he said（mx-say-past-3s-he） ※未測定<br>it said（mx-say-past-3s-it） ※未測定<br>she said（mx-say-past-3s-she） ※未測定 | he says | pass | 9/9 |
| `pt:achaste` | 過去＋現在完了 | you found（mx-find-past-2）<br>you have found（mx-find-perf-2） ※未測定 | you found | pass | 9/9 |
| `pt:demos` | 過去＋現在完了 | we gave（mx-give-past-1p）<br>we have given（mx-give-perf-1p） ※未測定 | we gave | pass | 9/9 |
| `pt:deram` | 過去＋現在完了＋過去完了 | they gave（mx-give-past-3p）<br>they have given（mx-give-perf-3p） ※未測定<br>they had given（mx-give-pluperf-3p） ※未測定 | they gave | pass | 9/9 |
| `pt:deste` | 過去＋現在完了 | you gave（mx-give-past-2）<br>you have given（mx-give-perf-2） ※未測定 | you gave | pass | 9/9 |
| `pt:deu` | 過去＋現在完了 | he gave（mx-give-past-3s-he）<br>it gave（mx-give-past-3s-it） ※未測定<br>she gave（mx-give-past-3s-she） ※未測定<br>he has given（mx-give-perf-3s-he） ※未測定<br>it has given（mx-give-perf-3s-it） ※未測定<br>she has given（mx-give-perf-3s-she） ※未測定 | he gave | pass | 9/9 |
| `pt:fiz` | 過去＋現在完了 | i did（do-past-1s） ※未測定<br>i have done（mx-do-perf-1s） | i have done | pass | 9/9 |
| `pt:fomos` | 過去＋現在完了 | we went（mx-go-past-1p）<br>we have gone（mx-go-perf-1p） ※未測定 | we went | pass | 9/9 |
| `pt:foram` | 過去＋現在完了＋過去完了 | they went（mx-go-past-3p）<br>they have gone（mx-go-perf-3p） ※未測定<br>they had gone（mx-go-pluperf-3p） ※未測定 | they went | pass | 9/9 |
| `pt:vou` | 現在＋未来 | i go（go-pres-1s） ※未測定<br>i will go（go-fut-1s）<br>i am going to go（go-fut-goingto-1s） ※未測定 | i will go | pass | 9/9 |
| `pt:vão` | 現在＋未来 | they go（mx-go-pres-3p）<br>they will go（go-fut-3p） ※未測定 | they go | pass | 9/9 |

※未測定: その英語を復元対象にしたコホートが最新記録に無い行。
