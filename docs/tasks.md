# Auto Review Fix MVP: タスクリスト

設計書: [design.md](design.md)

## Phase 1: ファイル作成 (ローカル)

- [ ] 1.1 `.gitignore` を作成
- [ ] 1.2 `package.json` を作成
- [ ] 1.3 `tsconfig.json` を作成
- [ ] 1.4 `src/sample.ts` を作成 (空ファイル: `// sample module` のみ)
- [ ] 1.5 `.coderabbit.yaml` を作成
- [ ] 1.6 `.claude/CLAUDE.md` を作成 (最小限の指示)
- [ ] 1.7 `.github/workflows/fix-review.yml` を作成
  - techbook-ledger のワークフローを参照し、ドラフトと照合・調整
  - レビュアーフィルタ (`coderabbitai[bot]`)
  - concurrency group (PR 番号ごと、cancel-in-progress: true)
  - 権限定義 (contents:write, pull-requests:write, issues:write)
  - カウント追跡 (PR body HTML コメント)
  - リトライ上限チェック (3回)

## Phase 2: GitHub リポジトリセットアップ

- [ ] 2.1 リポジトリ作成 (`gh repo create aloekun/auto-review-fix-sandbox --private --clone`)
- [ ] 2.2 jj colocated 初期化 (`jj git init --colocate`)
- [ ] 2.3 Phase 1 のファイルを main にプッシュ
- [ ] 2.4 GitHub Secret 設定 (`ANTHROPIC_API_KEY`)
- [ ] 2.5 Label 作成 (`needs-human-review`)
- [ ] 2.6 Code Rabbit インストール (GitHub App)

## Phase 3: 基本動作検証

- [ ] 3.1 テスト用ブランチ作成 (`jj new main`)
- [ ] 3.2 `src/sample.ts` に問題コードを追加
- [ ] 3.3 ブランチをプッシュしてPR作成
- [ ] 3.4 Code Rabbit のレビューが発火することを確認
- [ ] 3.5 レビュー状態が `CHANGES_REQUESTED` であることを確認
- [ ] 3.6 Auto Fix Review ワークフローが発火することを確認
- [ ] 3.7 Claude Code Action が修正コミットをプッシュすることを確認
- [ ] 3.8 PR body に `<!-- claude-autofix-count:1 -->` が記録されることを確認

## Phase 4: ループ上限検証

- [ ] 4.1 PR body の `claude-autofix-count` を `2` に手動設定
- [ ] 4.2 次の修正サイクルでカウントが 3 に到達することを確認
- [ ] 4.3 `needs-human-review` ラベルが付与されることを確認
- [ ] 4.4 上限到達コメントが投稿されることを確認

## Phase 5: クリーンアップ・振り返り

- [ ] 5.1 テスト PR をクローズ
- [ ] 5.2 検証結果を記録 (成功/失敗、問題点、改善案)
- [ ] 5.3 横展開に向けた知見を整理
