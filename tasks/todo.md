# Auto Review Fix MVP: 進捗

## Phase 1: ファイル作成 (ローカル)

- [x] 1.1 `.gitignore` を作成
- [x] 1.2 `package.json` を作成
- [x] 1.3 `tsconfig.json` を作成
- [x] 1.4 `src/sample.ts` を作成 (空ファイル: `// sample module` のみ)
- [x] 1.5 `.coderabbit.yaml` を作成
- [x] 1.6 `.github/workflows/fix-review.yml` を作成

### Phase 1 レビュー

**ワークフロー (fix-review.yml) の設計判断:**

| 項目 | 設計ドラフト | techbook-ledger | 採用 |
|------|-------------|----------------|------|
| トリガー状態 | `changes_requested` のみ | `changes_requested` + `commented` | techbook-ledger (CR は commented で返すこともある) |
| concurrency | あり | なし | 設計ドラフト (無駄な実行防止) |
| action バージョン | `@beta` | `@64c7a0ef...` (v1 ピン留め) | techbook-ledger (再現性重視) |
| prompt | `.claude/CLAUDE.md` に分離 | workflow 内 inline | techbook-ledger (シンプル・1ファイル完結) |
| allowed_bots | なし | あり | techbook-ledger (明示的なボットフィルタ) |
| カウント処理 | 別ステップで get/update | 既存/新規を分岐する堅牢な処理 | techbook-ledger (実績のあるパターン) |

## Phase 2: GitHub リポジトリセットアップ

- [x] 2.1 リポジトリ作成 (`aloekun/auto-review-fix-sandbox` private)
- [x] 2.2 jj colocated 初期化 (既存)
- [x] 2.3 Phase 1 のファイルを main にプッシュ (develop も作成済み)
- [x] 2.4 GitHub Secret 設定 (`ANTHROPIC_API_KEY`)
- [x] 2.5 Label 作成 (`needs-human-review`)
- [x] 2.6 Code Rabbit インストール (GitHub App)
- [x] 2.7 リポジトリを public に変更 (CodeRabbit 無料プラン要件)

## Phase 3: 基本動作検証

- [x] 3.1 テスト用ブランチ作成 (`jj new main`)
- [x] 3.2 `src/sample.ts` に問題コードを追加
- [x] 3.3 ブランチをプッシュしてPR作成 → https://github.com/aloekun/auto-review-fix-sandbox/pull/1
- [x] 3.4 Code Rabbit のレビューが発火することを確認
- [x] 3.5 レビュー状態が `CHANGES_REQUESTED` であることを確認
- [x] 3.6 Auto Fix Review ワークフローが発火することを確認
- [ ] 3.7 Claude Code Action が修正コミットをプッシュすることを確認 → **失敗: 32回のパーミッション拒否**
- [x] 3.8 PR body に `<!-- claude-autofix-count:1 -->` が記録されることを確認

### Phase 3 レビュー

**ワークフロー実行結果 (Run #22668567806):**

| 項目 | 結果 |
|------|------|
| Code Rabbit レビュー | OK - CHANGES_REQUESTED |
| ワークフロー発火 | OK |
| Claude Code Action 実行 | 実行された (39ターン, $1.03) |
| 修正コミット | **NG - パーミッション拒否 32回** |
| ループカウント記録 | OK - `<!-- claude-autofix-count:1 -->` |

**問題点:** Claude Code Action がツール実行時に 32回パーミッション拒否された。修正コミットがプッシュされていない。

**原因候補:**
1. Claude Code Action の `allowed_tools` 設定不足
2. `.claude/settings.json` でのツール許可設定が必要
3. GITHUB_TOKEN のパーミッション不足 (contents:write はある)

**次のアクション:** パーミッション拒否の原因を調査し、Claude Code Action が修正をコミット・プッシュできるようにする。

## Phase 4: claude-ci-fix.yml テスト

### Phase 4.1: インフラ整備（main マージ）→ PR #6

- [x] 4.1.1 `.github/workflows/ci.yml` 作成（TypeScript CI）
- [x] 4.1.2 `.github/workflows/claude-ci-fix.yml` 作成（workflow_samples からコピー＋改善）
- [x] 4.1.3 `package.json` に `typecheck` スクリプト追加
- [x] 4.1.4 PR 作成 → main にマージ（PR #6, #8, #10 で改善含む）

### Phase 4.2: シナリオ A（基本動作確認）→ PR #7

- [x] 4.2.1 テストブランチ作成（`test/ci-fix-scenario-a`）
- [x] 4.2.2 `src/sample.ts` に TypeScript エラーを追加してプッシュ
- [x] 4.2.3 PR 作成 → CI 失敗確認
- [x] 4.2.4 `claude-ci-fix.yml` の発火確認（発火済み）
- [x] 4.2.5 デバッグログで `github.actor` / `workflow_run.actor.login` を記録 → `aloekun`
- [x] 4.2.6 Claude Code Action が修正をプッシュするか確認 → **成功**（3回目の実行で成功）

### Phase 4.3: シナリオ B（Claude push 後の挙動確認）→ PR #11

- [x] 4.3.1 Claude の修正コミット後に走った CI を確認 → CI success（22803538740, 22803539040）
- [x] 4.3.2 `claude-ci-fix.yml` が再発火したか確認 → **SKIPPED**（conclusion=success のため）
- [x] 4.3.3 `workflow_run.actor.login` の値を記録 → **`claude[bot]`**（GitHub API で確認）
- [x] 4.3.4 `allowed_bots` なしで Claude が実行されるか確認 → N/A（SKIPPED のため実行なし）

**シナリオ B 実行結果:**

| 項目 | 結果 |
|------|------|
| claude-ci-fix.yml 発火（aloekun push） | OK × 2（22803499050, 22803505035） |
| Claude 修正コミット | OK（`fix: remove intentional TypeScript error for scenario B CI test`） |
| 修正後 CI | SUCCESS（22803538740, 22803539040） |
| claude-ci-fix.yml 再発火 | SKIPPED × 2（conclusion=success のため） |
| SKIPPED ランの actor | **`claude[bot]`**（GitHub API `actor.login` で確認） |
| permission_denials_count | Run #1: 7, Run #2: 6 |
| --debug フラグ効果 | `show_full_output: false` のため詳細不明 → `show_full_output: true` が必要 |
| 無限ループ | **なし**（CI success → SKIPPED） |

### Phase 4.4: 結果に応じた対応

- [x] 4.4.1 観察結果を記録
- [x] 4.4.2 Claude 実行トレースを CI アーティファクトとしてアップロード（`Upload Claude trace` ステップ追加済み）

### Phase 4 レビュー

**主要な知見:**
1. Claude push 後の `claude-ci-fix.yml` ランの `actor = claude[bot]` を GitHub API で確認
2. Claude の修正で CI が成功する場合、claude-ci-fix.yml は SKIPPED → 無限ループなし
3. Claude の修正で CI が失敗する場合、`allowed_bots: "claude[bot]"` がないと Claude は実行されない（未実験）
4. `--debug` フラグだけでは不十分 → `show_full_output: true` でツール呼び出し詳細を可視化できる

## Phase 5: Local AI Agent Daemon への移行

### Phase 5.1: アーキテクチャ移行（main マージ）

- [x] 5.1.1 ADR 作成 (`docs/adr/001-move-to-local-daemon.md`)
- [x] 5.1.2 既存 GH Actions ワークフロー削除 (`fix-review.yml`, `claude-ci-fix.yml`)
- [x] 5.1.3 `.gitignore` 更新 (`ai-review-fixer/state.json` 追加)
- [x] 5.1.4 `ai-review-fixer/` 実装（config.yaml, requirements.txt, state_manager.py, review_collector.py, prompt_builder.py, claude_runner.py, orchestrator.py, run_daemon.sh）
- [x] 5.1.5 ドキュメント更新 (CLAUDE.md, docs/design.md, docs/knowledge.md)
- [ ] 5.1.6 PR 作成 → main にマージ

### Phase 5.2: 動作検証

- [ ] 5.2.1 `pip install -r requirements.txt` で依存インストール確認
- [ ] 5.2.2 `review_collector.py` 単体動作確認（実際の PR に対して）
- [ ] 5.2.3 テスト用 PR に CodeRabbit レビューがある状態で `orchestrator.py` を一度実行
- [ ] 5.2.4 `tmp/daemon-workspace/` に変更がコミットされ GitHub に push されることを確認
- [ ] 5.2.5 `run_daemon.sh` でデーモン起動・ループ動作を確認

### Phase 5.3: ループ上限テスト

- [ ] 5.3.1 `state.json` の `fix_attempts` を手動で `max_fix_attempts - 1` に設定
- [ ] 5.3.2 次のサイクルで上限到達コメントが PR に投稿されることを確認
- [ ] 5.3.3 上限後はデーモンがそのPRをスキップすることを確認

## Phase 6: テスト整備 + Ruff 導入 (完了)

- [x] 6.1 `pyproject.toml` 作成 (pytest / coverage / ruff 設定)
- [x] 6.2 `requirements-dev.txt` 作成 (pytest-cov, hypothesis, pytest-mock, ruff)
- [x] 6.3 DI リファクタリング: `interfaces.py` (Protocol 定義)
- [x] 6.4 DI リファクタリング: `git_client.py` (GitClient クラス)
- [x] 6.5 DI リファクタリング: `review_collector.py` → GHClient クラス化
- [x] 6.6 DI リファクタリング: `claude_runner.py` → ClaudeRunner クラス化
- [x] 6.7 DI リファクタリング: `state_manager.py` → StateManager クラス化
- [x] 6.8 DI リファクタリング: `context_builder.py` → ContextBuilder クラス化
- [x] 6.9 DI リファクタリング: `run_logger.py` → RunLogger クラス化
- [x] 6.10 DI リファクタリング: `orchestrator.py` → Orchestrator クラス化
- [x] 6.11 テストインフラ: `tests/` ディレクトリ構造作成
- [x] 6.12 テストインフラ: `FakeGHClient`, `FakeClaudeRunner` 実装
- [x] 6.13 ユニットテスト: 全8モジュール (93テスト)
- [x] 6.14 プロパティテスト: report_builder, state_manager, prompt_builder (Hypothesis)
- [x] 6.15 統合テスト: orchestrator (正常/コミットなし/max_attempts/retry)
- [x] 6.16 E2E テストスケルトン (E2E_GITHUB_REPO 未設定時はスキップ)
- [x] 6.17 CI 更新: python-lint-and-test ジョブ追加
- [x] 6.18 `package.json` に py-* スクリプト追加

### Phase 6 レビュー

| 指標 | 結果 |
|------|------|
| テスト数 | 93 passed (e2e 1件 deselected) |
| カバレッジ | 92.06% (要件 80% クリア) |
| Ruff | All checks passed |
| Python バージョン | 3.10 互換 (timezone.utc 使用) |

## Phase 7: jj-start-change dirty tree guard

- [x] 7.1 `.claude/scripts/jj-start-change.sh` 新規作成
- [x] 7.2 dirty tree 検出ロジック実装・エラーメッセージ整備
- [x] 7.3 `package.json` の `jj-start-change` を `bash .claude/scripts/jj-start-change.sh` に変更
- [x] 7.4 動作確認（dirty ケース: ERROR で停止を確認済み）
- [x] 7.5 `ai/rules/VCS_JUJUTSU.md` 更新（ガード層構成表・エラー対処法を追加）

## Phase 8: フィードバックループ完結（request_review 抽象化）

**前提条件: Phase 7 (PR #28) のマージ後に着手 → マージ済み**

- [x] 8.1 `GHClient.request_review()` を追加（`ai-review-fixer/review_collector.py`）
  - `reviewer_bot == "coderabbitai[bot]"` → `@coderabbitai review` コメントを投稿
  - 将来の拡張用の else pass で OK
- [x] 8.2 `_finalize_run()` に呼び出しを追加（`ai-review-fixer/orchestrator.py`）
  - `reviewer_bot` 引数を追加し、committed=True の場合のみ `request_review()` を呼ぶ
  - max_attempts 到達時は `request_review()` を呼ばない
- [x] 8.3 commit message に `[ai-autofix]` タグ付与（`ai-review-fixer/prompt_builder.py`）
  - `build_prompt` / `build_patch_verification_prompt` の commit 指示部分を更新
- [x] 8.4 `FakeGHClient` に `request_review` stub を追加し、ユニットテスト更新
  - `tests/unit/test_orchestrator.py` — committed=True/False 両ケース追加
  - `tests/unit/test_review_collector.py` — coderabbitai/unknown-bot 両ケース追加
  - `interfaces.py` の `GHClientProtocol` にも `request_review` 追加
  - 97 passed, 1 deselected (e2e) / coverage 85.90%
- [x] 8.5 E2E テストで `@coderabbitai review` コメントが投稿されることを確認
  - `tests/e2e/test_full_flow.py` に検証3として追加

### Phase 8 レビュー

| 指標 | 結果 |
|------|------|
| テスト数 | 97 passed (e2e 1件 deselected) |
| カバレッジ | 85.90% (要件 80% クリア) |
| Ruff | All checks passed |

### Phase 8 CodeRabbit 指摘対応

- [x] **Major**: `orchestrator.py` `_finalize_run()` — `request_review()` を max_attempts チェックより前に移動し、成功コミット時は常に呼ばれるよう修正。try/except で非致命的エラーをハンドリング。
