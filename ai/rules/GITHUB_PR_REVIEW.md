# GitHub PR Review Comments - Reading Patterns

## Problem

`gh api` for PR review comments returns large JSON (80KB+).
Claude Code auto-saves oversized output to temp files on C drive, which are hard to read back (token limits).

## Solution

Use `--jq` flag to filter at the API level. Never fetch full JSON and parse after.

## Recommended Patterns

```bash
# List review comments (file path + truncated body)
gh api repos/{owner}/{repo}/pulls/{number}/comments \
  --jq '.[] | "=== \(.path) ===\n\(.body[0:800])\n"'

# Filter by specific file
gh api repos/{owner}/{repo}/pulls/{number}/comments \
  --jq '.[] | select(.path == "src/target.ts") | .body'

# General comments (summaries from bots like CodeRabbit)
gh api repos/{owner}/{repo}/issues/{number}/comments \
  --jq '.[] | select(.user.login == "coderabbitai[bot]") | .body[0:500]'
```

## Anti-patterns (avoid)

1. Fetching full JSON then trying to Read the auto-saved temp file
2. Delegating to sub-agents just to parse JSON
3. Using Python/scripts to parse when `--jq` suffices
