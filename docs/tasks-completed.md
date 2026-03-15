# 完了済みタスク

詳細な実装経緯は各フェーズの ADR や PR を参照。

---

## Phase 1: ファイル作成 ✅

`.gitignore` / `package.json` / `tsconfig.json` / `src/sample.ts` / `.coderabbit.yaml` / `.github/workflows/fix-review.yml` を作成。

---

## Phase 2: GitHub リポジトリセットアップ ✅

`aloekun/auto-review-fix-sandbox` 作成、jj colocated 初期化、初期 push、`ANTHROPIC_API_KEY` シークレット設定、`needs-human-review` ラベル作成、CodeRabbit インストール。

---

## Phase 3: 基本動作検証 ✅（一部未達）

テスト PR を作成し CodeRabbit レビューが発火することを確認。

- ✅ CodeRabbit レビュー (`CHANGES_REQUESTED`) 確認
- ✅ Auto Fix Review ワークフロー発火確認
- ❌ 3.7 Claude Code Action による修正コミット: **GitHub Actions パーミッション拒否で未達** → ローカルデーモン方式に移行する契機となった

---

## Phase 4 & 5: ループ上限検証・クリーンアップ ⚠️ 廃止

GitHub Actions + Claude Code Action アプローチを廃止し、ローカルデーモン方式（Phase 6〜）に切り替えたため未実施。

---

## Phase 6: AI 自動修正品質改善 ✅

PR #20〜#21 で往復6回超に膨らんだ原因（context 不足・Fix ONLY 制約・自己検証なし）を改善。

| サブフェーズ | 内容 | PR |
|------------|------|----|
| 6.1 プロンプト改善 | `context_builder.py` 追加（変更ファイル全体・call graph・前回 diff）、Fix plan + Self-verification に変更 | #25 |
| 6.2 Patch Proposal Mode | 2段階実行（パッチ生成 → 検証 → commit）、`patch_proposal_mode` フラグ | #25 |
| 6.3 E2E テスト整備 | `test_full_flow.py`、synthetic review 注入、`docs/e2e-setup.md` | #27 |

---

## Phase 7: jj-start-change dirty tree guard (Layer 5) ✅

**PR #28**

前セッション残留ファイルの上に新作業を重ねてしまう問題を、作業開始時のチェックで防止。

- `.claude/scripts/jj-start-change.sh` 新規作成（dirty 検出 → fetch → `jj new main@origin`）
- `package.json` の `jj-start-change` スクリプトを新ファイルに向ける
- `ai/rules/VCS_JUJUTSU.md` にガード層構成・エラー対処法を追記

```text
Layer 1: git 直接実行ブロック           (validate-command.exe)
Layer 2: jj new main ブロック           (validate-command.exe)
Layer 3: jj edit main ブロック          (validate-command.exe)
Layer 4: push 前 ancestor guard        (jj-push-safe.sh)
Layer 5: start-change dirty tree guard  (jj-start-change.sh)
```

---

## Phase 8: フィードバックループ完結（request_review 抽象化） ✅

**PR #29**

自動修正コミット push 後に `@coderabbitai review` を自動投稿して再レビューを依頼するフローを実装。

- `GHClient.request_review()` 追加（`review_collector.py`）
- `_finalize_run()` に `reviewer_bot` 引数追加、commit 時に `request_review()` を呼び出し（max_attempts チェックより前）
- commit message に `[ai-autofix]` タグ付与
- `FakeGHClient` + ユニットテスト追加、E2E テストに検証3追加
- カバレッジ 85.90%

---

## Hotfix: jj-start-change.sh CRLF 修正 + 改行コード統一 ✅

**PR #30**

`jj-start-change.sh` の CRLF により bash エラーが発生していた問題を修正。
`.gitattributes` を追加しソースコード・設定・md → LF、その他テキスト → `text=auto` に統一。
既存 CRLF ファイル 62 件を一括 LF 変換。

---

## Hotfix: PR #30 見送りレビュー対応 ✅

**PR #31**

| 対象 | 内容 |
|------|------|
| `context_builder.py` | `diff_after.patch` を 50,000 文字で打ち切り、コンテキスト超過を防止 |
| `run_logger.py` | changed files / diff 取得を `HEAD` のみから `base_sha..HEAD` 範囲に変更 |
| `prompt_builder.py` | `xargs cat` → `xargs -0 cat`（スペース含むファイル名対応） |
| `test_context_builder.py` | 非除外関数の抽出をアサートしてテスト完全化 |
| `GIT_WORKFLOW.md` | コードブロック閉じフェンス追加 |
| `VCS_JUJUTSU.md` | `jj restore` → `pnpm jj-restore` に統一 |
| `tasks/todo.md` | Phase 8.2 の説明矛盾を修正 |

---

## Phase 9: multi-repo サポート ✅

**PR #37**

`config.yaml` の単一リポジトリ設定を廃止し、GitHub owner 配下の全リポジトリを対象に自動修正を実行できるよう拡張。

- `GHClient.list_repos(owner)` 追加（`gh repo list --source --no-archived --limit 9999`）
- `StateManager` キー形式を `pr_{N}` → `{owner}/{repo}/pr_{N}` に変更（旧キー検出時 stderr 警告）
- `run_logger` / `context_builder` のパスに `{owner}/{repo}` を追加（後方互換デフォルト付き）
- `orchestrator.run_once()` を multi-repo ループに全面改修（`repos.include` 空 = 全リポジトリ対象）
- `config.yaml` を `owner` + `repos.include` 形式に変更
- リポジトリ単位の try/except でエラー分離（1 リポジトリ失敗で全体停止しない）
- `_ensure_workspace()` でクローン前に `parent.mkdir(parents=True)` を追加
- `repos` / `repos.include` の型バリデーション追加（`reviewer_bots` と同方式）
- `FakeGHClient` に `repos_queried` / `list_repos_owners_called` 追跡フィールドを追加
- E2E conftest に `owner_scope` パラメータを追加して owner 伝播を検証可能に
- テスト 123 passed、ruff + mypy clean
