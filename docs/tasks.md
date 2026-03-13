# Auto Review Fix MVP: タスクリスト

設計書: [design.md](design.md)

完了済みタスク: [tasks-completed.md](tasks-completed.md)

---

## 進行中・予定タスク

---

## Phase 9: multi-repo サポート

**目的**: `config.yaml` の単一リポジトリ設定を廃止し、GitHub owner 配下の全リポジトリを対象に自動レビュー修正を実行できるよう拡張する。

**ブランチ戦略**: `feat/multi-repo-support` を起点に、4つの PR を main に順次マージ。

**設計決定**:
- リポジトリ列挙: `gh repo list {owner} --source --no-archived --limit 9999`（fork・archived 除外、上限9999件）+ `repos.include` 任意フィルタ
- パス設計: workspace / runs / logs すべてに `{owner}/{repo}` を含める
- state.json: キー形式を `{owner}/{repo}/pr_{N}` に変更（破壊的変更・旧キー検出時に警告ログ）
- 将来対応: parallel processing / `updated_at` フィルタの TODO コメントを追加

### PR 1: `GHClient.list_repos()` 追加
**スコープ**: 純粋な機能追加、既存テスト全通過

- [ ] `ai-review-fixer/review_collector.py`: `list_repos(owner)` 追加（`--source --no-archived`）
- [ ] `ai-review-fixer/interfaces.py`: `GHClientProtocol.list_repos()` 追加
- [ ] `ai-review-fixer/tests/fakes/fake_gh_client.py`: `repos` フィールド + `list_repos()` 追加
- [ ] `ai-review-fixer/tests/e2e/conftest.py`: `_GHClientWithSyntheticReviews.list_repos()` 追加
- [ ] `ai-review-fixer/tests/unit/test_review_collector.py`: `list_repos` 新規テスト追加
- [ ] 品質チェック通過 → PR 作成

### PR 2: `StateManager` multi-repo キー変更
**スコープ**: 破壊的変更（既存 state.json 無効化）、全テスト通過

- [ ] `ai-review-fixer/state_manager.py`: 全メソッドに `owner, repo` 追加、キー形式変更、旧キー検出警告
- [ ] `ai-review-fixer/interfaces.py`: `StateManagerProtocol` シグネチャ変更
- [ ] `ai-review-fixer/orchestrator.py`: `self._state.*` 呼び出し更新
- [ ] `ai-review-fixer/tests/unit/test_state_manager.py`: 全テスト更新
- [ ] `ai-review-fixer/tests/property/test_state_manager_props.py`: 全テスト更新
- [ ] `ai-review-fixer/tests/unit/test_orchestrator.py`: state 呼び出し箇所更新
- [ ] `ai-review-fixer/tests/integration/test_orchestrator_integration.py`: state 呼び出し箇所更新
- [ ] 品質チェック通過 → PR 作成

### PR 3: `run_logger` + `context_builder` owner/repo namespacing
**スコープ**: 後方互換 default 付き引数追加、既存テスト全通過

- [ ] `ai-review-fixer/run_logger.py`: `owner, repo` 引数追加、パスに `{owner}/{repo}` を含める
- [ ] `ai-review-fixer/context_builder.py`: `get_previous_fix_diff()` に `owner, repo` 追加
- [ ] `ai-review-fixer/tests/unit/test_run_logger.py`: owner/repo 付き/なしのパステスト追加
- [ ] `ai-review-fixer/tests/unit/test_context_builder.py`: `get_previous_fix_diff` テスト更新
- [ ] 品質チェック通過 → PR 作成

### PR 4: `config.yaml` + `orchestrator.py` multi-repo ループ（最終統合）
**スコープ**: 全機能の結合、全テスト通過

- [ ] `ai-review-fixer/config.yaml`: `repo.owner/name` 削除 → `owner` + `repos.include` に変更
- [ ] `ai-review-fixer/orchestrator.py`: `run_once()` を multi-repo ループに全面改修
- [ ] `ai-review-fixer/tests/unit/test_orchestrator.py`: config 更新 + multi-repo テスト追加
- [ ] `ai-review-fixer/tests/integration/test_orchestrator_integration.py`: config + パス更新
- [ ] `ai-review-fixer/tests/e2e/conftest.py`: `e2e_config` 更新 + `repos_override` 追加
- [ ] 品質チェック通過 → PR 作成
