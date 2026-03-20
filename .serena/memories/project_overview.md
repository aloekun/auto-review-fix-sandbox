# Project Overview: auto-review-fix-vc

## Purpose
A sandbox for experimenting with automated code review fixing: "CodeRabbit review → Local AI Agent auto-fix" workflow.

## Architecture
```
GitHub PR → CodeRabbit review → PR comments
                                      │
                              Local Daemon (orchestrator.py)
                                      │  ← 60-second polling
                              Claude Code CLI (-p, --dangerously-skip-permissions)
                                      │
                              git commit + push (tmp/daemon-workspace/)
```

## Tech Stack
- **Language**: Python 3.10+ (main codebase), TypeScript (sample/CI)
- **Dependencies**: PyYAML
- **Dev tools**: pytest, hypothesis, ruff, mypy, pytest-cov, pytest-mock
- **VCS**: Jujutsu (jj) — git commands are blocked by hooks
- **CI**: GitHub Actions
- **Code review**: CodeRabbit
- **Task runner**: pnpm scripts (package.json)

## Key Modules (ai-review-fixer/)
| File | Role |
|------|------|
| `orchestrator.py` | Main daemon, polls for reviews and orchestrates fixes |
| `review_collector.py` | GHClient for fetching PR reviews (Review, PRInfo classes) |
| `interfaces.py` | Protocol classes (GHClientProtocol, GitClientProtocol, etc.) |
| `git_client.py` | Git operations |
| `claude_runner.py` | Claude Code CLI invocation |
| `prompt_builder.py` | Builds prompts for Claude |
| `context_builder.py` | Builds context for fixes |
| `state_manager.py` | Tracks processing state |
| `report_builder.py` | Generates fix reports |
| `run_logger.py` | Logs daemon runs |
| `config.yaml` | Configuration (repos, polling interval, max retries) |

## Test Structure
- `tests/unit/` — Unit tests
- `tests/integration/` — Integration tests with fakes
- `tests/property/` — Property-based tests (Hypothesis)
- `tests/e2e/` — End-to-end tests (requires `.env.e2e`)
- `tests/fakes/` — Fake implementations for testing
