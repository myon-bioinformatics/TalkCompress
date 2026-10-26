# Zipilogue（A）

**層1 — 機械同士。** 共有パスフレーズ前提の認証付き符号化。人間非可読でよい。

## 方式（stdlib のみ）

- KDF: `hashlib.scrypt` → 32-byte key
- ストリーム: HMAC-SHA256 カウンタ鍵ストリーム XOR
- MAC: HMAC-SHA256（改ざん検知）
- 封筒: `ZIP1` + ver + nonce(16) + ciphertext + mac → **base64url（パディングなし）**

## CLI

```bash
uv run python Zipilogue/zipilogue.py encode --key 'shared-secret' --text 'hello'
uv run python Zipilogue/zipilogue.py decode --key-file ./key.txt   # stdin: envelope
```

秘密鍵をリポジトリに置かないこと。
