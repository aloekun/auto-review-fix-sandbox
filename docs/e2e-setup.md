# E2E テストセットアップガイド

E2E テストは実際の GitHub リポジトリと `claude` CLI を使ってフルフローを検証する。

---

## テスト戦略における位置づけ

| 層 | GitHub | git | LLM |
|----|--------|-----|-----|
| Unit | FakeGHClient / subprocess mock | MagicMock | FakeClaudeRunner |
| Integration | FakeGHClient | 実 git（tmp repo） | FakeClaudeRunner |
| **E2E** | **実 GitHub API** | **実 git** | **実 claude CLI** |

> E2E のみ `get_reviews()` をシンセティックデータに差し替える。GitHub が PR 作者による自己レビューを禁止しているため（[詳細は conftest.py のコメント参照](../ai-review-fixer/tests/e2e/conftest.py)）。

---

## 事前準備

### 1. テスト用 GitHub リポジトリの作成

テスト用リポジトリ（例: `<owner>/test-review-fix-sandbox`）を GitHub 上で作成し、
`main` ブランチに 1 件以上のファイルを push しておく。

推奨設定（任意）:
- Squash merge を有効化
- 「Automatically delete head branches」を有効化

### 2. gh CLI 認証

```bash
gh auth status
# → Logged in to github.com as <owner>
```

未認証の場合:

```bash
gh auth login
```

### 3. claude CLI の確認

```bash
claude --version
```

未インストールの場合は [Claude Code のインストール手順](https://docs.anthropic.com/ja/docs/claude-code) を参照。

### 4. .env.e2e ファイルの作成

`ai-review-fixer/.env.e2e` を作成する（gitignore 済みのためコミットされない）。

```bash
# ai-review-fixer/.env.e2e
E2E_GITHUB_REPO=<owner>/test-review-fix-sandbox
```

このファイルは `conftest.py` のモジュール読み込み時に自動的に環境変数へ展開される。
毎セッション `export` を実行する必要はない。

---

## テストの実行

```bash
pnpm py-test:e2e
```

内部では以下が実行される:

```bash
pytest ai-review-fixer/tests/e2e/ -m e2e -v -s -r s
```

### 実行フロー

1. `e2e_test_pr` fixture がテスト用ブランチ `e2e/test-<timestamp>` を作成して PR を開く
2. Orchestrator が `tmp/` 配下の一時ディレクトリにリポジトリをクローン
3. シンセティックレビュー（`calculate_ratio` のゼロ除算チェック）を注入して `run_once()` を実行
4. `claude` CLI がレビュー内容を読んでコードを修正し、commit & push する
5. テストが以下を検証する:
   - PR ブランチの HEAD SHA が変化した（コミットが push された）
   - PR に "AI Auto Fix Report" を含むコメントが投稿された
6. fixture teardown が PR をクローズしてブランチを削除する

---

## クリーンアップが失敗した場合の手動対応

fixture teardown の失敗などで PR やブランチが残留した場合:

```bash
# オープン中の E2E テスト PR を一覧表示
gh pr list --repo <owner>/test-review-fix-sandbox --head "e2e/"

# PR をクローズ（ブランチも削除）
gh pr close <PR番号> --repo <owner>/test-review-fix-sandbox --delete-branch

# ブランチが残っている場合は個別に削除
gh api repos/<owner>/test-review-fix-sandbox/git/refs/heads/e2e/<ブランチ名> -X DELETE
```

---

## よくある問題

| 症状 | 原因 | 対処 |
|------|------|------|
| `SKIPPED: E2E_GITHUB_REPO not set` | `.env.e2e` が未作成 | 「事前準備 4」を実行する |
| `Could not find 'claude' in PATH` | claude CLI 未インストール | Claude Code をインストールする |
| SHA が変化しない | Claude が push しなかった | `ai-review-fixer/runs/` のログを確認する |
| `gh pr create` が失敗 | gh 認証切れ | `gh auth login` を再実行する |
