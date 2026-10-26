# Zipilogue（A）

**層1 — 機械同士。** 共有パスフレーズ前提の認証付き符号化。人間非可読でよい。

## 方式（stdlib のみ）

- KDF: `hashlib.scrypt` → 32-byte key
- ストリーム: HMAC-SHA256 カウンタ鍵ストリーム XOR
- MAC: HMAC-SHA256（改ざん検知）
- 封筒: `ZIP1` + ver + nonce(16) + ciphertext + mac → **base64url（パディングなし）**
- **AAD（任意）**: `--aad` / チャネルラベルを MAC 入力に折り込む。封筒には書かない。同じ平文+鍵でもラベルが違えば検証失敗（空 AAD は従来 MAC と互換）

## CLI

```bash
uv run python Zipilogue/zipilogue.py encode --key 'shared-secret' --text 'hello'
uv run python Zipilogue/zipilogue.py encode --key 'shared-secret' --aad 'chat-room' --file plain.bin --out env.txt
uv run python Zipilogue/zipilogue.py decode --key-file ./key.txt --aad 'chat-room' --file env.txt --out plain.bin
uv run python Zipilogue/zipilogue.py decode --key-file ./key.txt   # stdin: envelope
```

秘密鍵をリポジトリに置かないこと。

## Fingerprint / dry-run

`key_fingerprint(passphrase)` → short hex of SHA-256(derived key). CLI: `fingerprint` mode. `--dry-run` on encode prints envelope length (with `--stats`, JSON on stderr) without dumping binary.

