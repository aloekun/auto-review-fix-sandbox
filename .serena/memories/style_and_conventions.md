# Code Style and Conventions

## Python
- **Target**: Python 3.10+
- **Line length**: 100 characters
- **Linter**: ruff (rules: E, F, W, I, UP, B, SIM)
- **Type checker**: mypy (ignore_missing_imports=true)
- **Naming**: snake_case for functions/variables, PascalCase for classes
- **Architecture**: Protocol-based interfaces (interfaces.py defines contracts)
- **Ignored rules**: B904 (raise-without-from in daemon loop)

## Commit Messages
- Conventional Commits: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- Format: `type(scope): description`

## Branch Naming
- Feature: `feat/description` or `fix/description`
- Test: `test/description`
- Default: branch from `main` (no `develop` branch)
- Exception: for stacked PRs, base from the pushed parent branch using `pnpm jj-start-change <parent-branch>`

## Design Patterns
- Protocol classes for dependency injection (GHClientProtocol, GitClientProtocol, etc.)
- Fake implementations in tests/fakes/ for testing
- Property-based testing with Hypothesis
- State tracking via JSON (state.json)
