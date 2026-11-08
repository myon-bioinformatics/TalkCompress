# 往復チェック強制時の影響（report-only）

生成: `uv run python scripts/roundtrip.py --write-doc`（採点は o200k_base）。

## 往復チェック必須の nl 過去形（現在完了セル）

nl（1億人未満）の現在完了セル採用 0 件は `fixtures/roundtrip.json` の `required` に登録。強制は report-only。

| id | EN | 採用 | lt100m 強制時 |
|---|---|---|---|

## 全件（`--impact lt100m`、0件）

```
```
