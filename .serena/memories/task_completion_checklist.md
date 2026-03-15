# Task Completion Checklist

Every task must pass ALL of the following before being marked complete:

## 1. Quality Checks (mandatory, no skipping)
```bash
pnpm py-lint          # ruff + mypy — must pass with zero errors
pnpm py-test          # unit/integration tests — must all pass
pnpm py-test:e2e      # E2E tests — auto-skips if .env.e2e missing
```

## 2. Report Format
Report results in this format:
```markdown
### 検証結果
| チェック | 結果 |
|---------|------|
| lint / type-check | ✅ or ❌ (error count) |
| テスト | ✅ XXX passed or ❌ |
| E2Eテスト | ✅ XXX passed or ❌ or ⏭ スキップ |
```

## 3. Post-Check Steps
After all checks pass:
1. Record review section in `tasks/todo.md`
2. Create new jj change, commit, and push
3. Create PR (`pnpm gh-pr create --base main`)
4. Report PR URL to user
