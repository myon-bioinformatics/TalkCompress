# 絵文字・記号の o200k 評価メモ

台帳（`ShorthandEdge/ledger/conventions.json`）への採用規則（cheapest-form rule: トークン優先、次にバイト）:
- o200k で英語より**トークンが少ない**、または
- **トークン同数で utf8 バイトが厳密に少ない**

トークンが増えるもの、同数でバイトも減らないものは台帳に入れず、このメモに記録します（オーナー決定により、同数でバイトが減るものは採用に変更）。

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

## 同数・バイト減の再採用（オーナー決定）
次の対応を runtime マップと台帳に戻した。トークンは英語と同数で、utf8 バイトが減る（括弧内は英語 B → 短形 B）。
- 記号:
  - percent → %（8→2）
  - degrees → °（8→3）
  - divided by → ÷（11→3）
  - vice versa → ⇄（11→4。E 層 MorphoZip 規則と台帳行の両方）
  - implies → ⇒（8→4）
  - sqrt → √（5→4）
  - proportional to / propto → ∝（16 / 7→4）
  - not equal / not equals → ≠（10 / 11→4）
- 絵文字:
  - star ★（5→4）
  - red heart ♡（10→4）
  - check ✓（6→4。check mark は 2→1 token で厳密減）
  - cross mark ✕（11→4）
  - eye emoji 👀（10→5）
  - wave hello 👋（11→5）
  - ok hand 👌（8→5）
  - thumbs down / thumbs-down 👎（12→5）
  - clapping 👏（9→5）
  - idea bulb 💡（10→5）
  - pin it 📌（7→5）
  - on fire 🔥（8→5）
  - laugh 😂（6→5）
  - thinking face 🤔（14→5）
- ≧ / ≦ は戻さない（≥ / ≤ が厳密減で置き換え済み）。
- 上の「不採用」節のうち、ここに挙げた項目は採用に変わった。infinity → ∞ などトークンが増えるものは引き続き不採用。
