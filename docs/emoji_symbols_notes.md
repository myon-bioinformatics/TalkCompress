# 絵文字・記号の o200k 評価メモ

台帳（`ShorthandEdge/ledger/conventions.json`）に採用するのは、o200k で英語より**トークンが厳密に減る**記号・絵文字だけです。減らないもの（同数・増加）は台帳に入れず、このメモに記録します。

## 計測方法
- `tiktoken` の `o200k_base` で、文中を想定して**先頭に半角スペースを付けた**文字列（例: `" heart"` と `" ❤"`）を数える
- 絵文字は EN pivot と比べる。記号は台帳 sample（先頭の形）と比べ、行内の各形も個別に判定する

## 結論（絵文字）
- o200k では、**単語の英語に対して厳密に勝つ絵文字はない**
- 同数（tie）で utf8 だけ減るのは、主に BMP の旧来記号（✓ ★ ❤ ♥）
- VS16（U+FE0F）付きは、トークンかバイトのどちらかが増える（ℹ️ 3、⚠️ 3、✉️ 3、❤️ は 1 token だが 7 bytes）
- VS16 を外しても勝てないものがある（ℹ は 2 token で、information の 1 token に負ける）
- 例外は複合語の pivot。`thumbs up`（2）→ 👍（1）だけが厳密に減るため、台帳に残す唯一の絵文字

| 対象 | 英語 (tok) | 短形 (tok) | 判定 |
|---|---|---|---|
| thumbs up → 👍 | 2 | 1 | **採用** |
| heart → ❤ / ♡ / ❤️ | 1 | 1 / 2 / 1 | 不採用（❤ は tie・utf8 減） |
| check → ✓ | 1 | 1 | 不採用（tie） |
| star → ★ | 1 | 1 | 不採用（tie） |
| laugh → 😂 | 1 | 1 | 不採用（tie） |
| thumbs down → 👎 / thinking face → 🤔 / ok hand → 👌 | 2 | 2 | 不採用（tie） |
| cross mark → ✕ / incorrect | 2 / 1 | 2 | 不採用（× は 1 token だが乗算記号と衝突） |
| information → ℹ️ / ℹ | 1 | 3 / 2 | 不採用 |
| warning → ⚠ | 1 | 2 | 不採用 |
| fire 🔥, idea 💡, eyes 👀, clap 👏, wave 👋, bell 🔔, link 🔗, pin 📌, money 💰, rocket 🚀, party 🎉, skull 💀, wrench 🔧, pray 🙏, hundred 💯, cry/sad 😢, mail ✉, email ✉ | 1 | 2 | 不採用 |
| time ⏱, alarm ⏰, hourglass ⏳, bug 🐛 | 1–2 | 3 | 不採用 |

## 記号
採用（台帳あり）:

| 対象 | 英語 (tok) | 短形 (tok) |
|---|---|---|
| at least / or more → ≥（旧 ≧） | 2 | 1（≧ は 2） |
| at most / or less / up to → ≤（旧 ≦） | 2 | 1（≦ は 2） |
| much less than → ≪ | 3 | 2 |
| there is no → ∄ | 3 | 2 |
| plus or minus → ± | 3 | 1 |
| パーセント / per cent → % | 4 / 2 | 1 |
| implies that → ⇒ | 2 | 1 |
| if and only if → ⇔ | 4 | 2 |
| square root → √ | 2 | 1 |
| multiplied by → × | 2 | 1 |

不採用（台帳から削除、メモのみ）:
- not equal → ≠（2 = 2）
- infinity → ∞（1 < 2）
- degrees → °（1 = 1）
- proportional to → ∝（2 = 2）
- divided by → ÷（2 = 2）
- vice versa → ⇄（2 = 2。E 層の MorphoZip 規則も削除済み。⇄ の復号のみ互換のため残置）
- 行内の単独形 percent / implies / iff / sqrt（1 = 1）

## more than / less than
- `more than → >`、`less than → <` は追加していない
- この 2 句は、既存の比較クラス（MorphoZip `COMPARE_ALIAS_TO_CANONICAL` と `_PHRASE_GRAMMAR`）で ≥ / ≤ の source として登録済みで、衝突する
- `>` は E 層で `greater than → >` に使用済み
