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
