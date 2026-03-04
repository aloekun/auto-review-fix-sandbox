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

- [ ] 2.1 リポジトリ作成
- [ ] 2.2 jj colocated 初期化
- [ ] 2.3 Phase 1 のファイルを main にプッシュ
- [ ] 2.4 GitHub Secret 設定 (`ANTHROPIC_API_KEY`)
- [ ] 2.5 Label 作成 (`needs-human-review`)
- [ ] 2.6 Code Rabbit インストール (GitHub App)

## Phase 3-5

docs/tasks.md を参照。
