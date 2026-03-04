# Auto Review Fix MVP: 最小構成プロジェクト設計

Code Rabbit + Claude Code Action の自動レビュー修正を検証するための最小構成プロジェクト。
techbook-ledger とは別の新規リポジトリで試行錯誤する。

## 方針

- 最小限のファイルで Auto Review Fix のフロー全体を検証する
- CI チェック (lint/typecheck/test) は含めない。branch protection も最小
- VCS は jj (colocated) を使用
- 動作確認できたら、他プロジェクトへの横展開テンプレートとする

## リポジトリ構成

```
auto-review-fix-sandbox/
  .github/
    workflows/
      fix-review.yml          # Auto Review Fix ワークフロー
  .coderabbit.yaml             # Code Rabbit 設定
  src/
    sample.ts                  # Code Rabbit がレビューする対象コード
  package.json                 # 最低限のプロジェクト定義
  tsconfig.json                # TypeScript 設定 (Code Rabbit の型指摘用)
  .gitignore
```

## 各ファイルの内容

### .github/workflows/fix-review.yml

docs/auto-review-fix.md の Workflow Example をそのまま使用する。
変更不要。

### .coderabbit.yaml

```yaml
# yaml-language-server: $schema=https://coderabbit.ai/integrations/schema.v2.json
reviews:
  auto_review:
    enabled: true
    base_branches:
      - "main"
  request_changes_workflow: true
```

- `base_branches` は `main` (このプロジェクトのデフォルトブランチ)
- `request_changes_workflow: true` で `CHANGES_REQUESTED` 状態のレビューを出す

### src/sample.ts

意図的に問題を含むコード。Code Rabbit がフラグする内容にする。

```typescript
export function divide(a: number, b: number) {
  return a / b;
}

export function parseAge(input: any): number {
  return parseInt(input);
}

export function getItems(data: any[]) {
  var result = [];
  for (var i = 0; i < data.length; i++) {
    result.push(data[i]);
  }
  return result;
}

export function toUpperCase(value: string | undefined) {
  return value!.toUpperCase();
}
```

問題点: ゼロ除算チェックなし、`any` 型、`parseInt` の radix 引数なし、`var` 使用、non-null assertion

### package.json

```json
{
  "name": "auto-review-fix-sandbox",
  "version": "0.0.1",
  "private": true
}
```

### tsconfig.json

```json
{
  "compilerOptions": {
    "strict": true,
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "noEmit": true
  },
  "include": ["src"]
}
```

### .gitignore

```
node_modules/
dist/
*.log
.DS_Store
Thumbs.db
.claude/settings.local.json
```

## GitHub 側の設定

### 1. リポジトリ作成

```bash
gh repo create aloekun/auto-review-fix-sandbox --private --clone
cd auto-review-fix-sandbox
jj git init --colocate
```

### 2. Secrets

| Secret | 内容 |
|--------|------|
| `ANTHROPIC_API_KEY` | Anthropic API キー |

`GITHUB_TOKEN` はワークフロー実行時に自動提供される。

### 3. Labels

```bash
gh label create "needs-human-review" --description "Auto-fix reached retry limit, manual review required" --color "d93f0b"
```

### 4. Code Rabbit

リポジトリに Code Rabbit をインストールする (GitHub App)。

### 5. Branch protection

最小構成では設定不要。動作確認後に必要に応じて追加。

## 検証手順

### Step 1: 初期セットアップ

1. リポジトリ作成 + 上記ファイルを main にプッシュ
2. GitHub Secrets 設定
3. Labels 作成
4. Code Rabbit インストール

### Step 2: テスト用 PR 作成

```bash
jj new main
# src/sample.ts を編集 (問題コードを追加)
jj describe -m "test: add sample code with intentional issues"
jj bookmark create test/verify-auto-review-fix
jj git push --bookmark test/verify-auto-review-fix --allow-new
gh pr create --base main --title "test: verify auto review fix" --body "Auto Review Fix の動作確認用 PR"
```

### Step 3: 動作確認

| チェック項目 | 確認方法 |
|-------------|---------|
| Code Rabbit のレビューが発火する | PR の Reviews タブ |
| レビュー状態が `CHANGES_REQUESTED` | `gh api repos/{owner}/{repo}/pulls/{pr}/reviews --jq '.[-1].state'` |
| Auto Fix Review ワークフローが発火 | Actions タブ / `gh run list` |
| Claude Code Action が修正コミットをプッシュ | PR の Commits タブ |
| ループカウントが PR body に記録される | PR body に `<!-- claude-autofix-count:1 -->` |

### Step 4: ループ上限テスト

1. PR body の `claude-autofix-count` を `2` に手動設定
2. 次の修正サイクルでカウントが 3 に到達することを確認
3. `needs-human-review` ラベルが付与されることを確認
4. 上限到達コメントが投稿されることを確認

### Step 5: クリーンアップ

テスト PR をクローズ。必要に応じてリポジトリを削除またはアーカイブ。

## 知見 (techbook-ledger での学び)

詳細は docs/auto-review-fix-lessons.md を参照。特に注意すべき点:

- `.claude/settings.local.json` は必ず `.gitignore` に入れる (CI で PreToolUse フックが失敗する)
- `needs-human-review` ラベルは事前作成必須 (未作成だとワークフローが failure)
- Code Rabbit は同一コミットを再レビューしない (新しいプッシュが必要)
- `pull_request_review` イベントはベースブランチのワークフローを参照する
