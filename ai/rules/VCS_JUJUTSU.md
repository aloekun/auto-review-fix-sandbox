# Version Control: Jujutsu (jj)

このプロジェクトでは **Jujutsu (jj)** をバージョン管理ツールとして使用する。
`git` コマンドの直接使用は `validate-command` フックによりブロックされる。

## なぜ jj か

- Working copy が自動的に変更を追跡する（`git add` 不要）
- コミットの書き換え・分割・移動が安全にできる
- Git リポジトリと完全に互換（`jj git push/fetch` で連携）

## 基本コマンド対応表

| 目的 | jj コマンド | (参考) git 相当 |
|------|------------|----------------|
| 状態確認 | `jj status` | `git status` |
| 差分確認 | `jj diff` | `git diff` |
| 履歴確認 | `jj log` | `git log` |
| 変更を記述 | `jj describe -m "message"` | `git commit -m "message"` |
| 新しい変更を開始 | `jj new` | (自動。次の作業開始) |
| ブックマーク作成 | `jj bookmark create <name>` | `git branch <name>` |
| ブックマーク移動 | `jj bookmark set <name>` | `git branch -f <name>` |
| リモートに push | `jj git push --bookmark <name>` | `git push` |
| リモートから fetch | `jj git fetch` | `git fetch` |
| 変更を親に統合 | `jj squash` | `git commit --amend` / `rebase -i` |

## ブランチ（ブックマーク）ワークフロー

### 新しい作業ブランチの作成

```bash
# 1. 作業開始（dirty tree guard → fetch → jj new main@origin を実行する）
pnpm jj-start-change
# 内部で: working copy の汚染チェック → jj git fetch → jj new main@origin を実行
# working copy に未記録の変更がある場合はエラーを出して中断する（第5層ガード）

# 2. 実装作業を行う（working copy に自動反映される）

# 3. 変更を記述
pnpm jj-describe -m "feat(scope): 説明"

# 4. ブックマークを作成（変更を記述した後に作成すること）
pnpm jj-bookmark create feature/N-description

# 5. リモートに push（初回は --allow-new が必要、祖先チェックも自動実行）
pnpm jj-push --bookmark feature/N-description --allow-new
```

**重要**: `jj new main`、`pnpm jj-new main`、`jj edit main`、`pnpm jj-edit main` はブロックされる。必ず `pnpm jj-start-change` を使うこと。
これにより working copy の汚染チェック後に origin/main を fetch してから change を作成するため、先祖返りと残留ファイルの混入を防止できる。

### 既存ブランチへの追加コミット

```bash
# 1. 変更を加える（working copy に自動反映）
# 2. 変更を記述
pnpm jj-describe -m "fix(scope): 追加修正"

# 3. 親コミットに統合する場合
pnpm jj-squash

# 4. ブックマークを現在の変更に移動
pnpm jj-bookmark set <name> --allow-backwards

# 5. push（祖先チェックも自動実行）
pnpm jj-push --bookmark <name>
```

### PR マージ後の次タスク開始

```bash
# 次の作業開始（fetch + origin/main からの change 作成を一括実行）
pnpm jj-start-change
```

### Stacked PR ワークフロー（複数 PR を順番に作成する場合）

PR を複数に分割して順番にレビュー・マージする場合（例: 機能 A → 機能 B → 機能 C）に使う。
各 PR は前の PR ブランチをベースにする。

**前提**: 次の PR の作業を始める前に、現在の PR ブランチを push 済みであること。

```bash
# PR 1 の作業を完了して push
pnpm jj-describe -m "feat(scope): PR 1 の内容"
pnpm jj-bookmark create feat/pr1-description
pnpm jj-push --bookmark feat/pr1-description --allow-new
# → GitHub で PR 1 を作成（base: main）

# PR 2 の作業を始める（PR 1 ブランチをベースにする）
pnpm jj-start-change feat/pr1-description
# 内部で: dirty tree チェック → fetch → feat/pr1-description@origin の存在確認 → jj new

# PR 2 の作業
pnpm jj-describe -m "feat(scope): PR 2 の内容"
pnpm jj-bookmark create feat/pr2-description
pnpm jj-push --bookmark feat/pr2-description --allow-new
# → GitHub で PR 2 を作成（base: main ※ PR 1 マージ後に自動的に main に届く）

# PR 3 以降も同様
pnpm jj-start-change feat/pr2-description
```

**注意**: `pnpm jj-start-change [base]` で指定するブランチはリモートに存在する必要がある。
ローカルのみのブランチは指定できない（先に `pnpm jj-push --allow-new` が必要）。

### 誤って main 上で作業した場合の復旧

```bash
# 1. main の親から新しい変更を作成
pnpm jj-new @-

# 2. 誤って main に入れた feature ファイルを新しい変更にコピー
pnpm jj-restore --from <main_change_id> -- <feature_files...>

# 3. main ブックマークをリモートの位置に戻す（忘れると競合の原因になる）
pnpm jj-bookmark set main -r main@origin

# 4. 以降は通常の feature ブランチ手順で進める
pnpm jj-describe -m "feat(scope): 説明"
pnpm jj-bookmark create feature/N-description
```

## ガード層の構成

| 層 | 場所 | 役割 |
|----|------|------|
| Layer 1 | `validate-command.exe` | `git` コマンド直接実行をブロック |
| Layer 2 | `validate-command.exe` | `jj new main` をブロック |
| Layer 3 | `validate-command.exe` | `jj edit main` をブロック |
| Layer 4 | `.claude/scripts/jj-push-safe.sh` | push 前にリモートブランチ（`main@origin` または push済みfeatureブランチ）が祖先かチェック |
| Layer 5 | `.claude/scripts/jj-start-change.sh` | 作業開始前に working copy が clean かチェック |

### dirty tree guard（第5層）でエラーになった場合

```text
ERROR: Working copy is dirty (uncommitted changes remain).
前セッションのファイルが残っています。
```

このエラーは、前のセッションで編集したファイルが working copy に残ったまま新しいタスクを開始しようとしたときに発生する。

**変更を捨ててよい場合:**

```bash
pnpm jj-abandon @   # 変更を破棄して前の change に戻る（取り消し不可）
# または
pnpm jj-restore     # ファイルを元に戻す（変更は消去するが change は残る）
```

**変更を保持して続けたい場合（途中作業を PR にしたい等）:**

```bash
pnpm jj-describe -m 'feat(scope): description'
pnpm jj-bookmark create feature/N-description
pnpm jj-push --bookmark feature/N-description --allow-new
# 以降は通常通り pnpm jj-start-change で新タスク開始
```

## 注意事項

### ブックマーク作成のタイミング

`jj bookmark create` は **変更を `jj describe` した後** に実行する。
先に作成すると空コミットにブックマークが付き、後で移動する際に `--allow-backwards` が必要になる。

### 初回 push には --allow-new が必要

リモートに存在しないブックマークを push する際は `--allow-new` フラグが必須。
jj の安全機構で、意図しないリモートブックマーク作成を防いでいる。

### jj git push はユーザー承認が必要

`jj git push` は allow リストに含めていない。
最終的な push 判断はユーザーが行うため、実行時に承認プロンプトが表示される。

### PR 作成は gh CLI を使う

```bash
pnpm gh-pr create --base main --head <bookmark-name> --title "..." --body "..."
```

jj は GitHub PR を直接作成する機能を持たないため、`gh` CLI を使用する。

## フックによる git ブロック

`.claude/hooks-rs/src/main.rs` の `validate-command` フックが全ての Bash コマンドを検証する。
`&&`, `;`, `||`, `&` でチェーンされた git コマンドもブロック対象。

ブロック対象外:
- `jj git push` / `jj git fetch` など jj 経由の操作
- `gh` CLI（GitHub API 操作）
