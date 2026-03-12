# Sub-agent: PR 未対応レビュー確認

## いつ使うか

メインコンテキストが大きくなっている場合や、レビュー確認をメインの作業と並列化したい場合に
Explore サブエージェントへ委譲する。

## サブエージェントへのプロンプト

```
Run the following command from the project root and return the complete stdout:

  python scripts/list_unresolved.py <PR_NUMBER>

Do NOT read any files, do NOT make additional API calls.
Just run the command and return its output exactly as-is.
```

## サブエージェントが返すべき情報

1. コマンドの stdout 全文（すでにコンパクト）
2. Exit code（0 = 未対応なし、1 = 未対応あり）

返却フォーマット例:

```
PR #26 (aloekun/auto-review-fix-sandbox): 3 unresolved / 15 total

[1] id=PRRT_kwDO...
    File: ai-review-fixer/orchestrator.py:42
    [coderabbitai] Fix the null dereference here...

[2] id=PRRT_kwDO...
    File: scripts/fetch_pr_reviews.py:15
    [coderabbitai] Add error handling for empty response...

[3] id=PRRT_kwDO... [outdated]
    File: docs/tasks.md:30
    [coderabbitai] Label this fenced block...
```

## 利用可能なコマンド

| コマンド | 用途 |
|---------|------|
| `pnpm gh-unresolved <N>` | 未対応スレッドのみ stdout に出力（サブエージェント向け） |
| `pnpm gh-reviews <N>` | 全スレッドをファイルに保存（`tmp/pr<N>_reviews.txt`） |

## スレッドの解決（メインエージェントで実行）

サブエージェントには解決操作を委譲しない。修正後は必ずメインエージェントが実行する:

```bash
gh api graphql -f query='mutation {
  resolveReviewThread(input: {threadId: "PRRT_kwDO..."}) {
    thread { id isResolved }
  }
}'
```

## Agent ツール呼び出し例

```
Agent(
  subagent_type="Explore",
  description="List unresolved PR reviews",
  prompt="Run the following command from the project root and return the complete stdout: python scripts/list_unresolved.py 26\nDo NOT read any files or make additional API calls."
)
```

## アンチパターン（避けること）

1. メインコンテキストで `gh api` を直接呼んでレビュー JSON を取得する
2. サブエージェントに `gh api graphql resolveReviewThread` を実行させる
3. サブエージェントに tmp/ ファイルを読ませる（コマンド1回で足りる）
