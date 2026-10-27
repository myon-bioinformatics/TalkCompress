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

軽量ローカルモデル（**llama.cpp または同等の軽量 GGUF** スタック；同クラス。既定では重いフル精度サーバは使わない）で継続会話を回し、間隔をおいてエージェントが独自の共有表現・スラング（RuleBook 成長）を発明するかを観察する想定。二者だけの脆い構成より、**複数エージェントを並列のグループ**として回す方を優先。ランナー実装は未着手（方針メモのみ）。

**Zipilogue (A)** は **DensityZip (D)** / **MorphoZip (E)** とは別サブプロジェクト（単独の「Zip」表記は使わない）。

