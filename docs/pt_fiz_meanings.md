# pt `fiz` の 3 意味の扱い（2026-11-10 JST）

`scripts/mapping_graph.py --collisions` の `multi_meaning` に、`pt:fiz` だけが 3 意味で出ていた。

| 意味 | bank / entry | EN source | o200k token / UTF-8（EN → fiz） |
|---|---|---|---|
| do:past | `es_fr_tense.json` `do-past-1s` | I did | 2 / 5 → 1 / 3 |
| do:perf | `tense_matrix.json` `mx-do-perf-1s`（生成） | I have done（EN 最安 I've done） | 2 / 9 → 1 / 3 |
| do-it:past | `pt_el_latin_tense.json` `do-it-past-1s` | I did it | 3 / 8 → 1 / 3 |

## 往復の根拠（`roundtrip.json` の `pt:fiz`、読み取りのみ）

- pt ゲート（#171、`source_acceptance: any-official-source-v1`）では形単位で 9/9 pass。
- 受理ソースは bank 順の `I have done` / `I did` / `I did it`。最初のソース `I have done` は 0/9 で、
  9 件すべて **別の公式受理ソース `I did`** との一致で通過した（`pt_results.md` の alternate=yes 21 形の 1 つ）。
- 実際の復元: `Fiz.` → `I did.`、`Maybe fiz today.` → `Maybe I did today.`、
  `She told me that fiz.` → `She told me that I did.`（各 3 seed、全 9 件同じ）。
- 変換後の文字列は 3 意味で同一なので、この 9 回答は 3 意味すべてに当てはまる。
  意味別に見ると do:past 9/9、do:perf 0/9、do-it:past 0/9（`it` は一度も戻らない）。

## 判断

- **do:past（I did → fiz）: 残す。** 回答そのものが一致（9/9）。
- **do:perf（I have done → fiz）: 残す（tense_merge として記録）。** 失うのは完了相だけで、項（目的語など）は失わない。
  pt の単純完了過去は英語の現在完了も担い（`tenho feito` は「ずっと〜してきた」の継続で別義）、
  過去／完了の統合は `de:sah`・`es:fui`・`pt:deu` など既存の 22 形と同じ扱い。外すと
  any-official-source の pass 判定そのものを変えることになり、この PR の範囲を超える。
- **do-it:past（I did it → fiz）: 外す。** 目的語 `it` が落ち、往復で 0/9（9 件とも `I did`）。
  同じ失敗で外した `do-it-fut-1s`（`farei`、回答は `I will do.`）と揃え、
  `examples_not_registered` に理由付きで移した。`roundtrip_reversed` は付けない（`fiz` という形自体は pass で、
  外したのは意味 1 つだけのため）。
- 外した後の `I did it` は `do-past-1s` が当たり、`fiz it`（2 / 6）になる。EN 3 / 8 より短く、`it` も残る。
  `fiz it` という文字列は往復**未測定**（測定済みの `fiz` → `I did` に英語の `it` が付く形）。
- 他言語候補の昇格はない（`do-it-past-1s` の候補は `fiz` だけ）。`ROUNDTRIP_ENFORCED_LANGS` は `{nl}` のまま。

結果として `multi_meaning` は 0 件になり、`pt:fiz` は `tense_merge`（do:past / do:perf）に入る。
