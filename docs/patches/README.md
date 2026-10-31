# Workflow patches

CI workflow は `.github/workflows/ci.yml` に適用済みです。以前ここにあった `ci.yml` のコピーは実際の workflow とずれていたため削除しました。CI を変えるときは `.github/workflows/ci.yml` を直接編集してください。

`.github/dependabot.yml` はまだ適用していない提案です。適用する場合（`workflow` スコープ付きトークン、または GitHub UI）:

```bash
mkdir -p .github
cp docs/patches/.github/dependabot.yml .github/dependabot.yml
git add .github/dependabot.yml
git commit -m "ci: enable Dependabot"
git push
```
