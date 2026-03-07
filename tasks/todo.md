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

### Phase 4.1: インフラ整備（main マージ）

- [x] 4.1.1 `.github/workflows/ci.yml` 作成（TypeScript CI）
- [x] 4.1.2 `.github/workflows/claude-ci-fix.yml` 作成（workflow_samples からコピー＋改善）
- [x] 4.1.3 `package.json` に `typecheck` スクリプト追加
- [x] 4.1.4 PR 作成 → main にマージ (PR #6)
- [x] 4.1.5 `ref: head_sha` → `ref: head_branch` 修正 + `Bash(npx:*),Bash(npm:*)` 追加 (PR #8)

### Phase 4.2: シナリオ A（基本動作確認）

- [x] 4.2.1 テストブランチ作成（`test/ci-fix-scenario-a`）
- [x] 4.2.2 `src/sample.ts` に TypeScript エラーを追加してプッシュ
- [x] 4.2.3 PR 作成 → CI 失敗確認 (PR #7)
- [x] 4.2.4 `claude-ci-fix.yml` の発火確認 → **発火確認** (runs 22799210447, 22799216563)
- [x] 4.2.5 デバッグログで `github.actor` / `workflow_run.actor.login` を記録
  - 人間 push 時: `github.actor=aloekun`, `workflow_run.actor=aloekun`
- [x] 4.2.6 Claude Code Action が修正をプッシュするか確認 → **成功** (12 turns, $0.20)

### Phase 4.3: シナリオ B（Claude push 後の挙動確認）

- [x] 4.3.1 Claude の修正コミット後に走った CI のログを確認
  - Claude fix: `fix(sample): correct type annotation for _ciTestError` (by claude[bot])
  - CI: **SUCCESS** (12:44:20-35 UTC)
- [x] 4.3.2 `claude-ci-fix.yml` が再発火したか確認
  - 再発火: **YES** (runs 22799284243, 22799285352)
  - 結果: **SKIPPED** (CI conclusion == 'success' のため)
- [ ] 4.3.3 `workflow_run.actor.login` の値を記録（`claude[bot]` か否か）
  - Claude push → CI SUCCESS → SKIPPED のため、Claude push 後の`workflow_run.actor` は未観察
  - Scenario B 完全テスト: 「Claude push → CI FAIL → claude-ci-fix 発火 → Claudeが実行されるか？」は未実施
- [ ] 4.3.4 `allowed_bots` なしで Claude が実行されるか確認 → **未検証**（Scenario B 未実施のため）

### Phase 4.4: 結果に応じた対応

- [x] 4.4.1 `claude-ci-fix.yml` の修正点を main にマージ済み (PR #8)

### Phase 4 レビュー

**シナリオ A の結果:**

| 観察項目 | 結果 |
|---------|------|
| `claude-ci-fix.yml` 発火 | OK（CI failure で発火） |
| デバッグログ `github.actor` | `aloekun`（人間のpushの場合） |
| デバッグログ `workflow_run.actor` | `aloekun`（人間のpushの場合） |
| Claude Code Action の実行 | OK（12ターン, $0.20, 7 permission denials） |
| Claude の修正 push | **OK**（`fix(sample): correct type annotation for _ciTestError`） |
| CI after Claude fix | **SUCCESS** |
| Claude push 後の claude-ci-fix 発火 | SKIPPED（CI が success のため正常） |

**シナリオ B（未実施）: allowed_bots 要否**

Claude push → CI fail → `claude-ci-fix.yml` 発火 → `claude-code-action` が実行されるか？
- 現状: Claude の fix が CI を PASS させたため、failure ケースが発生しなかった
- `allowed_bots: "claude[bot]"` の要否は **未検証**
- 検証には「Claude の fix が CI を fail させる」シナリオが必要

**インフラ修正（PR #8）の教訓:**

初回実行での 7 permission denials は npx/npm ツール不足と detached HEAD が原因と推定。
ただし、修正前でも Claude は実際に fix をプッシュできていたため、影響は限定的だった。

## Phase 5

docs/tasks.md を参照。
