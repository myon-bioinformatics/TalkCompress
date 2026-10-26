# Workflow patches

GitHub OAuth トークンに `workflow` スコープがないと `.github/workflows/**` を push できません。

適用（workflow スコープ付きトークン、または GitHub UI）:

```bash
mkdir -p .github/workflows
cp docs/patches/.github/workflows/ci.yml .github/workflows/ci.yml
cp docs/patches/.github/dependabot.yml .github/dependabot.yml
git add .github
git commit -m "ci: enable TalkCompress CI workflow"
git push
```

親 reusable のピン: `myon-bioinformatics/myon-bioinformatics@8ec3402011d74eddc163c44218937e742b21ce4f`
