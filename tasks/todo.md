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

## Phase 4-5

docs/tasks.md を参照。
