# Branch / Commit / PR Guidelines for Claude Code

> **変更履歴**: [ADR 002](../../docs/adr/002-remote-based-branch-strategy.md) により
> `develop` ベースの旧規約からリモートブランチ（`@origin`）ベースに移行。

## 0. ブランチ構成

```text
main@origin   デフォルトブランチ（保護ブランチ）
  └── feat/xxx, fix/xxx ...   各タスクの作業ブランチ
```

| ブランチ | 役割 | マージ先 |
|---------|------|---------|
| `main` | デフォルトブランチ。全 PR はここに向ける | - |
| `feat/*`, `fix/*` 等 | 個別タスクの作業ブランチ | `main` |

- `develop` ブランチは**廃止**（理由は [ADR 002](../../docs/adr/002-remote-based-branch-strategy.md) を参照）
- `hotfix/*` は廃止。`main` 直接ベースのため `fix/*` で統一

## 1. ブランチ命名規則

### フォーマット
`<type>/<kebab-case-の説明>`

### typeの一覧

| type | 用途 |
|------|------|
| `feat` | 新機能・ワークフロー変更 |
| `fix` | バグ修正 |
| `refactor` | リファクタリング（振る舞い変更なし） |
| `docs` | ドキュメントのみの変更 |
| `test` | テスト・レビュー動作テスト |
| `chore` | ビルド・CI・依存関係などの変更 |

### 命名例
```
feat/setup-local-server
fix/session-error-after-password-reset
refactor/extract-auth-service
docs/update-readme-setup
chore/update-eslint-config
test/review-trigger-validation
```

### ブランチ作成ルール
- **必ずリモートの最新（`main@origin`）から切る**
- Stacked PR の場合は push 済みブランチ（`[branch]@origin`）から切る
- 1ブランチ = 1つの目的
- ブランチ名は小文字・ハイフン区切り（スペース・アンダースコア禁止）

### jj での作業開始
```bash
# 通常の作業開始（fetch + jj new main@origin を一括実行）
pnpm jj-start-change

# Stacked PR: push済みブランチをベースにする場合
pnpm jj-start-change feat/pr1-branch
```

**注意**: `jj new main`（ローカル main）はガードによりブロックされる。
詳細は [VCS_JUJUTSU.md](VCS_JUJUTSU.md) を参照。

## 2. コミットメッセージ規約

[Conventional Commits](https://www.conventionalcommits.org/) に準拠する。

### フォーマット
```
<type>(<scope>): <subject>

[任意: body - なぜこの変更が必要か]

[任意: footer - Breaking Change / Issue参照]
```

### typeの一覧

| type | 用途 |
|------|------|
| `feat` | 新機能 |
| `fix` | バグ修正 |
| `docs` | ドキュメントのみ |
| `style` | フォーマット・空白など（ロジック変更なし） |
| `refactor` | リファクタリング |
| `test` | テストの追加・修正 |
| `chore` | ビルド・CI・依存関係 |
| `perf` | パフォーマンス改善 |
| `revert` | コミットの取り消し |

### コミットメッセージの書き方

**subject（1行目）のルール：**
- 50文字以内を目安
- 現在形・命令形で書く（`修正する` / `add` / `fix`）
- 文末にピリオド不要
- 「何をしたか」より「**なぜしたか・何が変わるか**」を意識する

**body（任意）のルール：**
- 1行目と空行を1行挟む
- 「なぜこの変更が必要か」「何を考慮したか」を書く
- 72文字で折り返す

**良い例 / 悪い例：**

```bash
# 悪い例（何をしたか羅列するだけ）
"ボタンの色を変更した"
"fix bug"
"修正"

# 良い例（why + what が明確）
"feat(auth): パスワードリセット後の自動ログイン機能を追加

セキュリティポリシー変更により、リセット後は再認証を必須とする。
セッション継続を廃止し、ログイン画面へリダイレクトする。

Closes #456"

"fix(ui): CTAボタンのコントラスト比をWCAG AA基準に修正

blue-400では基準値4.5:1を下回っていたためblue-600に変更。
Closes #789"
```

### 1コミット = 1つの論理的変更
- 複数の変更を1コミットに詰め込まない
- jj では `jj squash` で変更を統合する

### Breaking Changeの書き方
```
feat(api)!: レスポンス形式をJSONに統一

BREAKING CHANGE: XMLレスポンスは廃止。
既存クライアントは移行ガイド(docs/migration.md)を参照。
```

## 3. Pull Request規約

### PR のマージ先

全ブランチ → `main`

### PR タイトル
Conventional Commits 形式

```
feat(server): ローカルサーバーの基盤を構築
fix(parser): ISBN正規化のハイフン処理を修正
```

### PR 本文テンプレート

```markdown
## 概要
<!-- このPRで何をしたかを2〜3文で説明 -->

## 背景・目的
<!-- なぜこの変更が必要か -->

## 変更内容
<!-- 主な変更点をリストアップ -->
-
-
-

## スコープ外（やっていないこと）
<!-- 今回あえて含めなかったことを明示 -->
-

## 動作確認方法
<!-- レビュアーがローカルで確認する手順 -->
1.
2.
3.

## チェックリスト
- [ ] セルフレビュー済み
- [ ] テストを追加・更新した
- [ ] 既存テストがすべて通る
- [ ] ドキュメントを更新した（必要な場合）
- [ ] Breaking Changeがある場合は明記した
```

### PRの品質基準

**差分のサイズ：**
- 理想は **400行以内**
- 400行超の場合は分割を検討する
- 機械的な変更（リネーム・フォーマット）は別PRに切り出す

**Draft PRの活用：**
- 実装開始直後にDraft PRを立てて方向性を共有する
- レビュー依頼前に `Ready for review` に変更する

**セルフレビューの徹底：**
- アサイン前に自分でdiffを全行確認する
- デバッグ用コード（`console.log`、`binding.pry`など）が残っていないか確認する
- コメントアウトされたコードが残っていないか確認する
