# Zipilogue（A）

**層1 — 機械同士。** 送受信が**共有ルール台帳（RuleBook）**を積み上げて短くするチャネル。鍵付き MAC 封筒は任意の輸送層。

## ねらい（オーナー意図）

- 送信者と受信者が同じルール／アサーションを認識できていればよい。
- 使う文字・規則性・長さは自由（人間可読である必要はない）。
- 最初の数十〜数百往復は「このときはこう書く」と長く、頻出パターンがスラングのように短いトークン（`r1`, `r2`, …）へ育つ。
- 「鍵があれば任意の不透明 blob」ではない。中核は**両者がロードする共有台帳**。

## RuleBook（共有ルール台帳）

JSON 状態例:

```json
{
  "version": 1,
  "turn": 12,
  "threshold": 3,
  "rules": [{"id": "r1", "long": "ready and waiting", "short": "r1", "count": 5, "created_turn": 3}],
  "counts": {"ready and waiting": 5},
  "proposals": [],
  "next_id": 2
}
```

- **宣言**: `rule: long => short` または `:: long = short`（CLI `--long` / `--short` でも可）
- **観察**: 反復フレーズ（≥2 語 or 長いトークン）を数え、既定 **3 回**で自動採用（`--threshold` / `--no-auto-adopt`）
- **符号化**: 最長一致で long→short。復号は short→long
- **鍵あり**: rule 符号化のあと既存 Zipilogue 封筒でラップ可能

### CLI

```bash
# 宣言
uv run python Zipilogue/zipilogue.py rule-declare --state book.json \
  --long 'ready and waiting' --short r1

# 観察（回数を増やし、閾値で自動採用。変換後テキスト + stderr JSON）
uv run python Zipilogue/zipilogue.py rule-observe --state book.json \
  --text 'please stay ready and waiting now'

# 符号化 / 復号（--key があれば封筒も）
uv run python Zipilogue/zipilogue.py rule-encode --state book.json --text '...'
uv run python Zipilogue/zipilogue.py rule-decode --state book.json --text '...'

# コーパス行ごとに observe+encode（短縮の育ちをデモ）
uv run python Zipilogue/zipilogue.py rule-sim --state book.json --corpus turns.txt
```

DensityZip からは `--layer A --rule-state book.json`（鍵は任意）。

## 任意: MAC 封筒（stdlib のみ）

- KDF: `hashlib.scrypt` → 32-byte key
- ストリーム: HMAC-SHA256 カウンタ鍵ストリーム XOR
- MAC: HMAC-SHA256（改ざん検知）
- 封筒: `ZIP1` + ver + nonce(16) + ciphertext + mac → **base64url（パディングなし）**
- **AAD（任意）**: `--aad` / チャネルラベルを MAC 入力に折り込む

```bash
uv run python Zipilogue/zipilogue.py encode --key 'shared-secret' --text 'hello'
uv run python Zipilogue/zipilogue.py decode --key-file ./key.txt --aad 'chat-room' --file env.txt
uv run python Zipilogue/zipilogue.py fingerprint --key 'shared'
```

秘密鍵をリポジトリに置かないこと。

## Round-4

`rule-export` / `rule-import` / `rule-threshold` / `rule-negotiate` — ルール共有・閾値調整・複数ピア合流。

## 実験方針（2026-10-27）

軽量ローカルモデル（**llama.cpp または同等の軽量 GGUF** スタック；同クラス。既定では重いフル精度サーバは使わない）で継続会話を回し、間隔をおいてエージェントが独自の共有表現・スラング（RuleBook 成長）を発明するかを観察する想定。二者だけの脆い構成より、**複数エージェントを並列のグループ**として回す方を優先。最小の制御実験ランナーは `dialogue_lab.py`（下記）。自由な言語創発を確認したものではありません。

**Zipilogue (A)** は **DensityZip (D)** / **MorphoZip (E)** とは別サブプロジェクト（単独の「Zip」表記は使わない）。


## LLM 同士の共有表現の実験ランナー

`dialogue_lab.py` は上記の方針を最小の制御実験にしたものです。送信者が
学習用8メッセージから略号を提案し、独立した文脈の受信者peerが批評・承認します。
peer 0は否定・条件、peer 1は衝突・曖昧性を監査します。合意したRuleBookを凍結し、
学習時に見せていない20通りのタスクを新しい受信者呼び出しで評価します。

```bash
# llama-server は別途、同じ実行環境で起動する（外部推論APIは不要）。
python Zipilogue/dialogue_lab.py --base-url http://127.0.0.1:8080 \
  --groups 2 --peers 2 --rounds 2 --output /tmp/dialogue-report.json
```

- 既定は2群、各群は送信者1＋監査peer 2。CPU実行では逐次処理します。
  群名とpeerの観点は変えますが、同じ重み・温度0での複数群は統計的に独立な反復ではありません。
- 受信者は原文・正解・学習会話を見ません。`raw`（原文）、`shared`（圧縮＋辞書）、
  `unshared`（圧縮のみ）の3条件を比較します。正解は外側の採点器だけが持ちます。
- action/service/environment/condition/retries/keep_backup の全フィールド一致が成功条件。
  不正JSON・unknown・途中終了・数値とBooleanの取り違えは成功にしません。
- `/tokenize` の実トークンを使い、辞書を一度送る仮定のwire費用と交渉費用を計上します。
  実際のstatelessなモデル呼び出しでは毎回辞書を送るため、`prompt_content_tokens`も別に記録します。
  これはチャットテンプレートを除く本文の数で、APIの実`usage`は全呼び出しログに残します。
- 反復上限内に承認されない場合は`no_agreement`、モデル呼び出し失敗は別状態として記録。
  生成された文章・コード・ツール呼び出しは一切実行しません。

短いコードを与える実験を人間側が設計しているので、これは**LLMが交渉した置換規則の実験**です。
手書き辞書やテスト用の応答を自律言語の創発と呼びません。`positive_evidence`は未見入力の全件成功・
対照との差・交渉と辞書を含めたwire純削減を要求する厳しい補助指標であり、
自然に言語が発生したことや、statelessモデルの総推論費用削減の証明ではありません。

学習と評価は架空のデプロイ指示のみです。

初回実測 `results/qwen25-1p5b-rounds2.json`（Qwen2.5-1.5B Q4_K_M、seed 42、
温度0、1群・2peer・2round）は4回のモデル呼び出しで `no_agreement` でした。
最初の全文章置換案は検証で拒否され、次の7規則案にはpeer 0が賛成、peer 1が
曖昧性を理由に反対しました。合意していないため未見20件の評価は実施せず、
成功率・削減率も算出していません。これは初回条件での失敗結果です。

追加の4round条件 `results/qwen25-1p5b-rounds4.json` も10呼び出しで不合意でした。
round 1〜3で提案コードを修正しましたが、peer 1の曖昧性指摘は解消しませんでした。
これは初回を見てから反復上限だけ増やした追加条件で、独立した成功再現実験ではありません。
未見入力の復号成功・対照との差・費用削減はどちらの実測でも未検証です。
対照と費用計測はランナーの実装とテストで確認した機能であり、実モデルで検証済みの成果とは区別します。

交渉の実費（llama-server `usage`、チャットテンプレート込み）は初回が入力1,438＋出力530＝1,968 tokens、
追加条件が入力3,738＋出力967＝4,705 tokensでした。呼び出し所要時間の合計はそれぞれ約41秒・76秒です。
未合意のため圧縮後ペイロードがなく、wireの損益分岐メッセージ数は未定義です。

MiniCPM5-2B Q4_K_Mの既定テンプレート＋thinking無効条件は、最初の呼び出しで
HTTP 400になりました。`json_object` のgrammar開始位置と空think prefillが食い違う
ランタイム互換性エラーであり、モデルの圧縮能力を測った失敗ではありません。
元のJSON・起動条件は `results/minicpm5-default-*` に保持しています（サーバーログはリポジトリから削除済みです）。

限定的な互換再試験では `templates/minicpm5_json_nonthinking.jinja` を明示指定し、
MiniCPMのbos/ChatML区切りを保ってthink prefillを省き、`--reasoning off` にしました。
JSON制約・実験ロジック・承認基準は変更していません。これは既定テンプレートの結果とは別条件です。
400は解消しましたが、4roundとも全文章の置換案を繰り返し、検証で拒否されました。
4呼び出し、入力1,301＋出力984＝2,285 tokens、約62秒で `no_agreement` です。
peer承認と未見20件の復号評価には到達していません。結果・起動条件は
`results/minicpm5-nonthinking-v1-*` に保持しています（サーバーログはリポジトリから削除済みです）。

この負の結果は現在のプロトコルでの限定的な結果です。sender promptは繰り返し句を
要求しますが、検証器の4..100文字上限は明示せず、長さ違反も学習内出現違反と同じ
エラー文で返します。このフィードバックの不十分さが提案修正を妨げた可能性があり、
モデルの一般的能力や、共有圧縮方式が不可能であることを示しません。
この所見を受けたv2では制約と拒否理由を正確に提示します。条件自体は緩めません。
v1のreceiptとsource hashは保持し、v2は別の測定として記録します。

再現時のMiniCPM追加サーバー引数:

```bash
--jinja --reasoning-format none --reasoning off \
  --chat-template-file Zipilogue/templates/minicpm5_json_nonthinking.jinja
```

**現段階では共有表現は確立していません。** QwenとMiniCPMという別の重みを試しましたが、
各試行の送信者と監査peerは同じ重みを異なる文脈で呼び出しています。
交渉した不透明な略号の検証を目指す制御実験であり、自然発生した私的言語の証明ではありません。

v2で上限の明示と長さ違反理由の分離を修正し、同じMiniCPM互換テンプレート・4roundで
1回再測定しました。4回とも長さ違反の全文章案で不合意となり、未見評価には未到達です。
入力1,438＋出力985＝2,423 tokens、約74秒でした（`results/minicpm5-nonthinking-v2-*`）。
v1 runner SHA256は `4ce0a0441c1426b61cecb4e00bcf707d727da8d75f32fdbfe09e0825ebacf05f`、
v2は `d8425e9e896ff8e093b15132e422b1b391479100ecb001f6b7833dc9df836950`。
条件上限を維持した修正であり、既存の負の結果は置き換えていません。

### Unicode パスフレーズと既存データ

| 入力経路 | 鍵導出前の処理 | NFC/NFD |
| --- | --- | --- |
| Python API `str` | NFC → UTF-8 | 同じ鍵 |
| CLI `--key` | NFC → UTF-8 | 同じ鍵 |
| 環境変数 `TALKCOMPRESS_ZIP_KEY` | NFC → UTF-8 | 同じ鍵 |
| Python API `bytes` | そのまま | 異なるバイト列は異なる鍵 |
| `--key-file` | 末尾の CR/LF を全除去、それ以外はそのまま | 正規化しない |

NFKC は使わず、互換文字（例 `ﬁ` と `fi`）を同一視しません。
`fingerprint`、フレーム処理、鍵付き rule モードにも同じ方針が適用されます。

**互換性:** #107 より前の API は文字列を正規化せず UTF-8 にしていました。
#107 は API の `str` だけを NFC 化しました。この後続修正では CLI `--key` と
環境変数も NFC 化するため、それらで以前 NFD などの非NFC文字列を指定した
暗号文は、同じ文字列入力では MAC 検証に失敗します。フィンガープリントも変わります。
ASCII・既にNFCの文字列、および bytes の鍵導出は変更ありません。
封筒に正規化方式の識別情報はなく、自動で旧方式を再試行しません。

**旧データの回復:** 元のパスフレーズの正確なコードポイントが分かっていれば、
API で `decode(envelope, key=old_passphrase.encode("utf-8"))` と指定します。
CLI では元の UTF-8 バイト列を鍵ファイルに保存し、
`python Zipilogue/zipilogue.py decode --key-file old-key.bin --file envelope.txt --out recovered.bin`
で復号します。実際の秘密鍵ファイルをコミットしないでください。
元の末尾 CR/LF も鍵の一部だった API データは、鍵ファイルではなく API の bytes で回復します。
元の正確な文字列が不明な場合は、見た目が同じだけでは回復を保証できません。

移行する場合は元データを保持したまま旧 bytes 鍵で復号し、新しい文字列鍵で再暗号化します。
AAD がある場合は復号時にも元と同じ値を渡してください。
`tests/fixtures/zipilogue_legacy_keys.json` は #107 直前の commit
`84b28be729bf3d51d3e8a054cb0ab63edecb90a4` のコードを実行して生成した、
ASCII/NFC/NFD の固定暗号文とフィンガープリントです（公開のテスト用鍵）。


## GitHub Actions からの交渉・往復実測

Actions の **dialogue-lab → Run workflow** でモデルを選ぶと、固定重みの取得・
SHA-256 検証、CPU llama.cpp の起動、共有表現の交渉、合意できた場合の未見20件の
raw/shared/unshared比較、証跡アップロードまで実行します。モデル候補と固定コンテナは
SVG L3 と共通です。既定は Qwen2.5-0.5B、`all` は全候補を最大3並列で試します。
モデルの構築・学習ではなく、既存GGUFを起動する推論実験です。

1群・2 peer・4 round・seed 42・temperature 0、HTTP要求ごとの待ち時間600秒、
CPU 2・メモリ6GiB・context 4096で実行します。ジョブ上限は240分です。
台帳合意なし・不完全な計数などではCLIの終了コード1を維持するため、ワークフローは
失敗表示になります。artifact の `dialogue-report.json` の各 `status` と
`positive_evidence` を確認してください。緑表示だけで意味保持・費用削減の成功とは判定しません。
モデル起動失敗やジョブ打切りではレポートがない場合もあり、サーバーログで切り分けます。

artifactにはレポート（生の要求・応答を含む）、実験ログ、終了コード、重みの来歴、
モデルカタログ、ソースコミット、コンテナ設定・ログを30日保存します。
専用の依存インストールを行わずPython標準ライブラリで実験側を動かしますが、
このワークフローは既存Docker起動方式です。別途進行中のナノ環境・Docker非依存起動の
完成を意味しません。まず比較用の実行基準として使います。

ローカルでも起動済みの llama-server に対して同じ入口を使えます。

```bash
python -m Zipilogue.dialogue_lab --base-url http://127.0.0.1:8080 \
  --groups 1 --peers 2 --rounds 4 --timeout 600 --seed 42 \
  --model-label qwen-0.5b --output out/dialogue-report.json
```

`--model-label` は証跡用の名称であり、サーバーのモデルを変更しません。
実際のモデルは起動設定と重みのハッシュで確認します。
