# Suggested Commands

All commands use `pnpm` scripts. Direct `git` commands are blocked by hooks.

## Development
```bash
pnpm py-install-dev          # Install all dependencies (first time)
pnpm daemon                  # Run orchestrator once
pnpm daemon:loop             # Run orchestrator in polling loop
```

## Quality Checks (run before completing any task)
```bash
pnpm py-lint                 # ruff + mypy (lint + type-check)
pnpm py-lint:fix             # Auto-fix ruff issues
pnpm py-test                 # Unit/integration tests (excludes e2e)
pnpm py-test:e2e             # E2E tests (auto-skips if .env.e2e missing)
pnpm py-test:cov             # Tests with coverage (80% threshold)
```

## Version Control (Jujutsu via pnpm)
```bash
pnpm jj-status               # Status
pnpm jj-diff                 # Show diff
pnpm jj-log                  # Show history
pnpm jj-start-change         # Start new work (fetch + jj new main@origin)
pnpm jj-start-change feat/pr1-branch  # Stacked PR: base on an already pushed branch
pnpm jj-describe -m "msg"    # Describe change (Conventional Commits)
pnpm jj-bookmark create X    # Create bookmark
pnpm jj-push --bookmark X    # Push (add --allow-new for first push)
pnpm jj-fetch                # Fetch from remote
```

## GitHub CLI (via pnpm)
```bash
pnpm gh-pr create --base main ...   # Create PR
pnpm gh-pr list                      # List PRs
pnpm gh-run list                     # List workflow runs
pnpm gh-api ...                      # Raw GitHub API calls
```

## System Utilities (Windows with bash shell)
- Shell: bash (Unix syntax, not Windows CMD)
- Use forward slashes in paths
- `/dev/null` not `NUL`
