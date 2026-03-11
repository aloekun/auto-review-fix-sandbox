# GitHub PR Review Comments - Reading Patterns

## Problem

`gh api` for PR review comments returns large JSON (80KB+).
Claude Code auto-saves oversized output to temp files on C drive, which are hard to read back (token limits).

## Solution

Use `scripts/fetch_pr_reviews.py` via `pnpm gh-reviews` to fetch all review threads at once and save a compact summary to a local file. Read the local file instead of hitting the GitHub API multiple times.

## Standard Workflow

```bash
# Fetch all review threads for PR #<N>
# → デフォルト出力先: <project-root>/tmp/pr<N>_reviews.txt
pnpm gh-reviews <N>

# 出力先を明示したい場合
pnpm gh-reviews <N> --out tmp/pr<N>_reviews.txt

# Then read the local file (no further API calls needed)
# → shows Total / Unresolved / Resolved count + file:line + 200-char body preview per thread
```

## Output Format

```text
=== PR #<N> Review Threads ===
Total: 31 | Unresolved: 6 | Resolved: 25

--- UNRESOLVED ---
[1] UNRESOLVED [outdated]  id=PRRT_kwDO...
    File: some/file.py:42
    [coderabbitai] Short preview of the review comment body...

--- RESOLVED ---
[1] RESOLVED  id=PRRT_kwDO...
    File: other/file.ts:10
    [coderabbitai] Short preview...
```

## Resolving Threads via GraphQL

After fixing an issue, resolve the thread with its `id`:

```bash
gh api graphql -f query='mutation {
  resolveReviewThread(input: {threadId: "PRRT_kwDO..."}) {
    thread { id isResolved }
  }
}'
```

## Anti-patterns (avoid)

1. Calling `gh api` multiple times to read different parts of the review
2. Fetching full JSON and trying to read the auto-saved oversized temp file
3. Delegating to sub-agents just to parse JSON
4. Using raw `gh api --jq` patterns when `pnpm gh-reviews` already handles pagination and formatting
