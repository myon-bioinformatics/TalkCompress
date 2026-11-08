# ZIP1 read compatibility, RPC1 writes

This compatibility reader preserves the rename and
RPC1 encoder, salt, fingerprint, and explicit key input from PR #157.

The decoder accepts ZIP1 and RPC1. It selects exactly one scrypt salt from the
magic and verifies the MAC using that same magic before returning plaintext.
There is no retry under another salt, key, normalization mode, or AAD. Replacing
one magic with the other does not authenticate. Unknown formats remain rejected.
The original three ZIP1 fixtures are preserved byte-for-byte separately from the
new RPC1 vectors. Historical non-empty-AAD/NFD vectors are also tested.

New output and fingerprints remain RPC1. Old peers cannot read new output, and
old fingerprints do not equal new fingerprints. This is read compatibility, not
bidirectional protocol compatibility. Key environment variables remain removed.

An operator may explicitly decode an authenticated old envelope and encode its
plaintext with the current encoder and a fresh random nonce. Migration must keep
the original until the new output has been verified. No automatic rewrite or
plaintext file is added by the decoder. Normalization and AAD must be supplied
exactly as originally used; lost keys cannot be recovered.

Tradeoff: dual-read keeps historical ciphertext readable and adds a small legacy
cryptographic domain to maintain. If accepting old frames in ordinary decoding
is undesirable, an explicitly invoked offline migration reader can isolate this
code, leaving ordinary decode RPC1-only. That needs a separate command/interface,
secure output handling, and operator action before retiring the old reader. Do
not regenerate historical fixtures merely to make a rename appear compatible.

This preserves existing cryptographic behavior; it is not a security audit of
the project's custom stream/MAC construction or fixed-salt password KDF.
