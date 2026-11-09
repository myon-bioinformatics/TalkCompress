# ポルトガル語（pt）の厳密往復フィルタ（2026-11-09 JST）

## 対象・列挙差分

開始 main: `cdb895387170d42990ebf93573a307959b92c148`。隔離クローンだけで作業。
4ファイルの採用済みptラベルを自分で数え直した。

| ファイル | entry | ユニーク形 |
|---|---:|---:|
| tense_matrix.json | 373 | 248 |
| es_fr_tense.json | 22 | 16 |
| pt_el_latin_phrases.json | 5 | 5 |
| pt_el_latin_tense.json | 4 | 4 |
| 和集合 | 404 | 270 |

`tense_matrix.build()` / CLI `--lang pt` の既定範囲は373entry・248形だけ。
手書きbankを加えると22形増える。270形に各1件、bank順で最初のentryを選び、
`run(entries=..., only_lang="pt", accepted_sources=...)` に渡した。
測定前の全公式ソースとentry順は `pt_sources.json` に凍結してあり、削減後bankから再列挙しない。
他言語が勝っている31entry内の31個の負けpt候補は対象外で、entry全体をそのまま保持した。
`essayé` はptラベルだが同一entryの候補ではfrになっている既存不整合があり、
ラベル通り測定・不通過として除外した。同じ不通過文字列をfrへ付け替えて救済していない。

## 独立判定・完全ブラインドではない旨の開示

判定担当はTalkCompressに携わる同じassistantである。依頼には4つのソースファイル名と
270形/404entryの件数が含まれたが、例示の形↔英語ペアは含まれなかった。
判定担当は810件の変換後文だけを読み、公式英語のmapを開く前に復元を確定した。
したがってソース遮断の独立判定ではあるが、プロジェクト知識まで完全に遮断した
完全ブラインド実験とは主張しない。公式ソースを見た後で、ハイフン・類義語・人称などの
near-missを修正していない。

- 独立回答 `pt_blind.json`: SHA256 `d161afaef0b6f8dea08c5ff5babb69f349a7baea60f697ddaf5e85b36dd369df`。
- 変換文のみ810件のSHA256: `73fb04a10d7d26fa7c45453c03e271ed64697f6565e4795369d3588abb4d6551`。
- 公式 `sentences()` の3テンプレート `{s}.` / `Maybe {s} today.` / `She told me that {s}.`。
  文全体の先頭1文字だけが大文字化され、第一テンプレートでは269/270形の先頭が変わる。
  他2テンプレート内の形は変わらない。810文に形間衝突はない。
- `roundtrip_replay.py pt` を公式run()で再生。seeds [1,2,3]、min_trials 9、norm-nfc-v1。
  決定的replayなので各形の3回答を3seedに再使用する。9回の独立したlive推論ではない。
- ptはge100m_langsなので閾値0.6。trials>0の復元率0は全言語共通で不可。

## 共有形の採点（#168ルールを明示実装）

63形が複数entryを共有し、65形に複数の公式英語ソースがある。
entry数別の形数は 1:207 / 2:16 / 3:25 / 4:21 / 6:1。
公式ソース数別は 1:205 / 2:15 / 3:26 / 4:22 / 5:1 / 6:1。2形が複数ファイルに現れる。

run()に省略可能な `accepted_sources` を追加した。従来の既定動作は変更せず、
各targetのsourceとidentityは最初のfrom[0]のまま、同一形の全公式ソースを同じテンプレートに入れて
norm一致を取る。別ソースはtargetを追加せず、試行数を増やさない。判定回答も一切書き換えない。
receiptには生のresponse、accepted_sources、matched_source、first_source_match、
matched_via_alternateを保存し、読込時に整合性を再検証する。configに受理ソースmapのhashを保存。
run()が数えた2430試行・各9件をそのまま記録し、手でtrial数を書き換えていない。

**形単位:** 210形通過（各9/9）、60形不通過（各0/9）。計1890/2430。
**最初のfrom[0]に限る厳密集計:** 189形通過、1701/2430。
**別公式ソースでのみ通過:** 21形。全形表・この21形の列挙は `pt_results.md`。
**entry別参考集計:** 全404entryの各from[0]に限定すると1890/3636。
共有63形に属するentry分は486/1773。これは同じ変換文から人称などを識別できない差を含み、
形単位の公式受理英語との一致とは別物。これらの参考値をrun()の試行数に加えていない。

## 除外・変更範囲

- 生成matrixから63entryを除外。生成JSONは手編集せず、`tense_matrix.py` の
  per-form `ROUNDTRIP_REVERSED` に記録して公式生成器を実行した。
- #168の候補段階での全消去をそのまま使うと、負けpt候補を持つ他言語winnerや
  通過しているparityクラスまで消えるため、**元のranking/parity確定後の採用winnerにだけ**
  適用した。対象cellはcandidates=[]、reject、roundtrip_reversed付きで英語維持。
  次点候補の再選択はせず、英語同形候補も昇格しない。その他の生成entryは完全同一。
- 手書きbankはes_fr_tenseの3entry、pt_el_latin_phrasesの4entry、pt_el_latin_tenseの1entryを
  実際の全文復元と0/9をwhy_droppedに記してexamples_not_registeredへ移した。
  削除したtenseの英語ソースは生成器でも予約し、削除を機に別言語が新規採用されるのを防いだ。
- 次点昇格0件。既存候補のo200k token→UTF-8とruntime estimatorの比較はpt_results.md。
  指定されたentry全体の隔離方針を守り、圧縮が有利でも未検証の別言語候補は昇格しない。
- 通過210形に属するentryはすべて保持。不通過の証拠60形もroundtrip.jsonに残した。
  他言語のwinnerとそのcandidates（負けpt候補を含む）、it/el/laのphrase entryは不変。
- ROUNDTRIP_ENFORCED_LANGSは{nl}のまま。requiredを変更せず、ptの言語単位強制は無効のまま。

## ラベルとruntime

測定前mainのloaderにpt-taggedで載るのは267/270形。
各entryの全公式ソース×3テンプレートで該当bank段階を適用すると、268形・402entryで少なくとも一つの
期待文字列に一致した。うち1形は別言語tagで同じ文字列が載るので、268形のpt発火とは言わない。
テンプレート別の文字列一致形数は268 / 97 / 104。
文脈/pro-drop guardにより埋め込み文では発火しない場合がある。
これはapply_zh_de_phrases / apply_es_fr_tense段階の測定で、全pipeline評価ではない。
今回の往復はruntime列挙より広いラベル270形を対象にした。
除外後、不通過60形がpt-tagged候補としてこれら4loaderに残っていないことも確認した。
通過ラベル210形のうち209形がpt-taggedで載り、`/mês`だけはruntime estimatorでENに勝たず発火しない。
既存別bankの自然なfallthroughは止めていない。携帯電話は未変更のDE `Handy`
（o200k 1 token / 5 bytes、EN cell phone 2 / 10）に戻り、I will do itは既存の
短いrowが作用して `haré it`（3 / 8、EN最安短縮形3 / 10）となる。
これは削除entryの候補昇格や新規登録ではなく、他言語bankを変えずに保った結果である。

## AI可読性

810文すべてに判定表の英語glossが存在する。ただし英語として読めることと、公式ソースに厳密一致することは別。
厳密一致は630/810文（seed再使用を除く）であり、類義語や曖昧な人称・時制のnear-missも不一致扱い。
この3テンプレート以外の追加自由文でのAI可読性は **未測定**。

## 再現・生成物・テスト

- `uv run python scripts/pt_roundtrip.py --run`: 保存済みの270形から公式run()で再測定。
- `uv run python scripts/tense_matrix.py` / `--check`: 生成bank・report・md。
- calibrationは失敗した鮮度testに従い、公式 `uv run python scripts/calibrate_estimate.py --write` のみで再生成。
  o200k_calib.jsonのexceptionsが186→183（3key削除、追加・値変更なし）。手編集なし。
- `uv run python scripts/tokenizer_compat.py --compat` で採用cell 812→749に再生成。
  対象63cellの削除と集計値の更新。別tokenizerへの採用基準変更はない。
- 証拠JSON増大で既存setdefaultの引数がcache hitでも毎候補loadされる問題が顕在化したため、
  cache未登録時だけloadするよう変更。build開始時のcache clearや判定意味は不変で、
  1cache単位1loadの回帰testを追加した。
- `uv run python scripts/roundtrip.py --write-doc` で既存impact reportも公式再生成。
  lt100m仮想gateの差分表示は10→37件になったが、これはreport-onlyの仮想再ランキングで、
  コミットbankの次点昇格ではない（実bankで他言語winnerは完全不変）。
- 既存testは削除したdei/foi/farei/phone/blood-pressure等への期待を、英語維持・未変更bankへの
  fallthroughに更新し、通過形achara/achaなどの肯定例も追加した。
- 最初の全test試行は既知の期待値不一致とevidence再読込の遅さを確認後に中断し、
  次の全test試行で12件の生成物/削除形期待値不一致を把握して修正。最終全pytest結果は追記参照。
- 不変judge hash、810文の網羅、2430試行、全receiptの再採点、別ソース一致、偽造receipt拒否、
  不通過cellだけの削除、全他言語entry hash、it/el/la保持、nlだけの強制をfocused testで確認。

CloudAgent・ユーザーPC・他clone不使用。Issue #29本文、C層in favor of→proは未変更。
リモートpush・PR作成・merge・rebaseは行わず、ローカルcommitのみ。


### 最終検証

- `uv run pytest`: **5859 passed, 8 skipped, 1 xfailed**（407.62秒）。
- `uv run python scripts/tense_matrix.py --check`: up to date。
- `git diff --check`: 成功。
- `pt_blind.json` SHA256は指定値と一致。不通過60形を含む全270cohortは各9件・計2430完了。
- 初期mainから他言語のroundtrip records / required / 既存run historyに変更なし。
- calibrationは公式スクリプトでexceptionsのessayé / μέσω / πίεσηだけを削除。
- ローカルのみの日本語commit。push・PR作成・mergeは行っていない。
