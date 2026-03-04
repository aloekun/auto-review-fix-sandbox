# Auto Review Fix MVP: 最小構成プロジェクト設計

Code Rabbit + Claude Code Action の自動レビュー修正を検証するための最小構成プロジェクト。
techbook-ledger とは別の新規リポジトリで試行錯誤する。

## 決定事項

| # | 項目 | 決定 | 理由 |
|---|------|------|------|
| 1 | Workflow定義 | techbook-ledger から移植・簡略化 | 実績のあるベースを活用 |
| 2 | Claude設定 | 最小限の指示のみ (CLAUDE.md) | MVP で素早く検証開始 |
| 3 | トリガー | pull_request_review のみ | シンプルさ優先 |
| 4 | リトライ上限後 | ラベル付与 + コメントのみ | MVP に十分、ノイズが少ない |
| 5 | 権限スコープ | 明示的に最小権限を定義 | 横展開時の透明性確保 |
| 6 | VCS連携 | CI は純粋 git、ローカルのみ jj | CI のシンプルさ優先 |
| 7 | 横展開方針 | MVP 検証後に検討 | フォーカスを維持 |
| 8 | CR スコープ | 全ファイル対象 (デフォルト) | 設定不要でシンプル |
| 9 | コミット形式 | fix: プレフィックス固定 | 一貫性のあるコミット履歴 |
| 10 | エラー処理 | ワークフローのデフォルトに任せる | MVP で過剰な対応不要 |
| 11 | APIコスト | 制限なし (リトライ上限のみ) | MVP なのでシンプルに |
| 12 | 検証シナリオ | 初回 PR で問題コードを追加 | Code Rabbit が diff をレビューする自然なフロー |
| 13 | 同時実行制御 | concurrency グループで制御 | 無駄な実行を防ぐ |
| 14 | カウント追跡 | PR body の HTML コメント | 追加ツール不要 |
| 15 | レビュー区別 | Code Rabbit のみに限定 | 人間のレビューでの誤発火を防止 |

## 方針

- 最小限のファイルで Auto Review Fix のフロー全体を検証する
- CI チェック (lint/typecheck/test) は含めない。branch protection も最小
- VCS は jj (colocated) を使用。CI 内では純粋な git を使用
- 横展開テンプレート化は MVP 検証完了後に別途検討

## リポジトリ構成

```
auto-review-fix-sandbox/
  .github/
    workflows/
      fix-review.yml          # Auto Review Fix ワークフロー
  .claude/
    CLAUDE.md                  # Claude Code Action への指示
  .coderabbit.yaml             # Code Rabbit 設定
  src/
    sample.ts                  # Code Rabbit がレビューする対象コード (main では空)
  package.json                 # 最低限のプロジェクト定義
  tsconfig.json                # TypeScript 設定 (Code Rabbit の型指摘用)
  .gitignore
```

## 各ファイルの内容

### .github/workflows/fix-review.yml

techbook-ledger のワークフローをベースに簡略化。主な変更点:

- **トリガー**: `pull_request_review` (submitted, state: changes_requested) のみ
- **レビュアーフィルタ**: `coderabbitai[bot]` からのレビューのみで発火
- **権限**: 明示的に最小権限を定義 (contents:write, pull-requests:write, issues:write)
- **同時実行制御**: PR 番号ごとの concurrency group + cancel-in-progress: true
- **カウント追跡**: PR body の `<!-- claude-autofix-count:N -->` で追跡
- **リトライ上限**: 3回。到達時は `needs-human-review` ラベル付与 + コメント投稿
- **コミット形式**: `fix: address review comment - {summary}` 固定

```yaml
name: Auto Review Fix

on:
  pull_request_review:
    types: [submitted]

concurrency:
  group: auto-review-fix-${{ github.event.pull_request.number }}
  cancel-in-progress: true

permissions:
  contents: write
  pull-requests: write
  issues: write

jobs:
  auto-fix:
    if: >
      github.event.review.state == 'changes_requested' &&
      github.event.review.user.login == 'coderabbitai[bot]'
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.ref }}
          fetch-depth: 0

      - name: Get autofix count
        id: count
        run: |
          BODY=$(gh pr view ${{ github.event.pull_request.number }} --json body -q .body)
          COUNT=$(echo "$BODY" | grep -oP '<!-- claude-autofix-count:\K[0-9]+' || echo "0")
          echo "current=$COUNT" >> "$GITHUB_OUTPUT"
          echo "next=$((COUNT + 1))" >> "$GITHUB_OUTPUT"
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Check retry limit
        if: steps.count.outputs.current >= 3
        run: |
          gh pr edit ${{ github.event.pull_request.number }} --add-label "needs-human-review"
          gh pr comment ${{ github.event.pull_request.number }} --body "Auto-fix reached retry limit (3). Manual review required."
          exit 0
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: Run Claude Code Action
        if: steps.count.outputs.current < 3
        uses: anthropics/claude-code-action@beta
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}

      - name: Update autofix count
        if: steps.count.outputs.current < 3
        run: |
          BODY=$(gh pr view ${{ github.event.pull_request.number }} --json body -q .body)
          NEW_BODY=$(echo "$BODY" | sed 's/<!-- claude-autofix-count:[0-9]* -->//' | sed '$ a <!-- claude-autofix-count:${{ steps.count.outputs.next }} -->')
          gh pr edit ${{ github.event.pull_request.number }} --body "$NEW_BODY"
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

> 注: 上記は設計段階のドラフト。実装時に techbook-ledger の実ワークフローと照合して調整する。

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

### .claude/CLAUDE.md

Claude Code Action への最小限の指示。MVP では簡潔にする。

```markdown
# Auto Review Fix

Code Rabbit のレビューコメントに従ってコードを修正する。

- レビューで指摘された問題のみを修正する
- 指摘されていない箇所は変更しない
- コミットメッセージは `fix: address review comment - {修正内容の要約}` 形式にする
```

### src/sample.ts

main ブランチには空ファイルを配置。PR で意図的に問題を含むコードを追加する。

**main ブランチ (空ファイル):**

```typescript
// sample module
```

**PR で追加する問題コード:**

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

main には空の `src/sample.ts` がある状態で、PR で問題コードを追加する。
これにより Code Rabbit が diff に対してレビューを行う自然なフローを再現。

```bash
jj new main
# src/sample.ts に問題コードを追加 (上記の「PR で追加する問題コード」を参照)
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
