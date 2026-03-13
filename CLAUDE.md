# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

「CodeRabbit レビュー → Local AI Agent が自動修正」のフローを実験・改善するサンドボックス。

**アーキテクチャ (現行):**

```
GitHub PR → CodeRabbit review → PR comments
                                      │
                              Local Daemon (orchestrator.py)
                                      │  ← 60秒ポーリング
                              Claude Code CLI (-p, --dangerously-skip-permissions)
                                      │
                              git commit + push (tmp/daemon-workspace/)
```

### ファイルの役割

| ファイル/ディレクトリ | 役割 |
|---------------------|------|
| `ai-review-fixer/` | ローカルデーモンの実装（orchestrator.py 等） |
| `ai-review-fixer/config.yaml` | リポジトリ設定・ポーリング間隔・最大試行回数 |
| `tmp/daemon-workspace/` | デーモンが使う専用 git clone（gitignore済み） |
| `.github/workflow_samples/` | 過去のワークフロー実装（参考・アーカイブ） |
| `.github/workflows/ci.yml` | TypeScript CI（維持） |
| `src/sample.ts` | レビューをトリガーするサンプルコード |
| `docs/adr/` | アーキテクチャ決定記録 |

### デーモンの起動方法

```bash
cd ai-review-fixer
pip install -r requirements.txt  # 初回のみ
bash run_daemon.sh               # Ctrl+C で停止
```

または一度だけ実行:

```bash
cd ai-review-fixer
python orchestrator.py
```

## コマンド

Bash コマンドは `pnpm` スクリプト経由で実行する（許可管理の簡素化のため）。`jj` や `gh` を直接実行せず、対応する `pnpm` スクリプトを使うこと。

| スクリプト | 実行内容 | 用途 |
|-----------|---------|------|
| `pnpm jj-status` | `jj status` | 状態確認 |
| `pnpm jj-log [opts]` | `jj log [opts]` | 履歴表示 |
| `pnpm jj-diff [opts]` | `jj diff [opts]` | 差分表示 |
| `pnpm jj-describe [opts]` | `jj describe [opts]` | 変更を記述 |
| `pnpm jj-new [target]` | `jj new [target]` | 新しい変更を作成 |
| `pnpm jj-squash` | `jj squash` | 変更を圧縮 |
| `pnpm jj-bookmark [opts]` | `jj bookmark [opts]` | ブックマーク操作 |
| `pnpm jj-rebase [opts]` | `jj rebase [opts]` | リベース |
| `pnpm jj-edit [rev]` | `jj edit [rev]` | リビジョン編集 |
| `pnpm jj-restore [opts]` | `jj restore [opts]` | ファイル復元 |
| `pnpm jj-fetch` | `jj git fetch` | リモート取得 |
| `pnpm jj-push [opts]` | `jj git push [opts]` | リモートへプッシュ |
| `pnpm gh-repo [opts]` | `gh repo [opts]` | リポジトリ操作 |
| `pnpm gh-pr [opts]` | `gh pr [opts]` | PR 操作 |
| `pnpm gh-run [opts]` | `gh run [opts]` | ワークフロー実行管理 |
| `pnpm gh-api [opts]` | `gh api [opts]` | GitHub API |
| `pnpm gh-secret [opts]` | `gh secret [opts]` | シークレット管理 |

## テスト

## バージョン管理 (Jujutsu)

**`git` コマンドは `.claude/validate-command.exe` フックによりブロックされる。** 代わりに `jj` を `pnpm` スクリプト経由で使用する。

```bash
pnpm jj-status                              # 状態確認
pnpm jj-diff                                # 差分
pnpm jj-log                                 # 履歴
pnpm jj-start-change                        # 作業開始（fetch + jj new main@origin を実行）
pnpm jj-describe -m "feat(scope): message"  # 変更を記述
pnpm jj-bookmark create feature/N-desc      # ブックマーク作成 (describe 後に実行)
pnpm jj-push --bookmark name                # push (初回は --allow-new 追加)
pnpm jj-fetch                               # fetch
pnpm gh-pr create --base main ...           # PR 作成 (gh CLI 使用)
```

**注意**: 作業開始時は必ず `pnpm jj-start-change` を使う。`jj new main` / `pnpm jj-new main` と `jj edit main` / `pnpm jj-edit main` は hook によりブロックされる（`jj new main@origin` は許可）。

詳細は [ai/rules/VCS_JUJUTSU.md](ai/rules/VCS_JUJUTSU.md) を参照。

## ブランチ・コミット規約

- ブランチ: `main` から切る（`develop` は使わない）
- 命名:
  - ワークフロー変更: `feat/説明` または `fix/説明`
  - レビュー動作テスト: `test/説明`
- コミット: Conventional Commits (`feat`, `fix`, `refactor`, `docs`, `test`, `chore`)
- PR は `main` に向けて作成

---

## ワークフロー

### 1. 計画フェーズ（プランモード）
- 3ステップ以上 または 設計判断が必要なタスクは **必ずプランモードに入る**
- 途中で問題が発生したら **即座に作業を止めて再計画する**（無理に進めない）
- 構築だけでなく、検証ステップもプランモードで計画する
- 詳細な仕様をあらかじめ明文化して曖昧さを排除する

### 2. サブエージェント戦略
- メインのコンテキストウィンドウをクリーンに保つために **サブエージェントを積極活用する**
- リサーチ・コード探索・並列分析はサブエージェントに委譲する
- 複雑な問題には複数のサブエージェントを投入してより多くの計算リソースをかける
- 1サブエージェント = 1タスクで集中して実行させる

### 3. 自己改善ループ
- ユーザーから修正指摘を受けたら **必ず `tasks/lessons.md` にそのパターンを記録する**
- 同じミスを繰り返さないためのルールを自分向けに書く
- ミス率が下がるまでレッスンを徹底的に改善し続ける
- セッション開始時にそのプロジェクトに関連するレッスンをレビューする

### 4. 完了前の検証（必須）
- **動作を証明せずにタスク完了としない**
- 関連する場合は `main` と自分の変更の差分を確認する
- 「スタッフエンジニアがこれを承認するか？」と自問する
- テストを実行し、ログを確認し、正しさを実証する

### 5. エレガントさを追求する（バランス重視）
- 非自明な変更では「より優雅な方法はないか？」と立ち止まって考える
- 修正がハック的に感じたら：「今知っている全てを活かして、エレガントな解決策を実装する」
- 単純で明白な修正にはこれを省略する（過剰設計しない）
- 提示する前に自分のコードを批判的にレビューする

### 6. バグ修正の自律対応
- バグレポートが来たら **そのまま修正する**（手取り足取り聞かない）
- ログ・エラー・失敗テストを手がかりにして自力で解決する
- ユーザーのコンテキストスイッチをゼロにする
- 指示されなくても CI の失敗テストを修正しに行く

### 7. タスク完了フロー
品質チェック（テスト・lint・typecheck）が全てパスしたら、以下を **ユーザーの指示を待たずに** 実行する:
1. `tasks/todo.md` にレビューセクションを記録する
2. `jj new` で新しい変更を作成し、コミット・プッシュする
3. PR を作成する（`pnpm gh-pr create --base main`）
4. PR URL をユーザーに報告する

---

## タスク管理

進捗は **2箇所** で追跡する。

| 管理先 | 用途 | 更新タイミング |
|--------|------|---------------|
| **TodoWrite ツール** | Claude Code セッション内のリアルタイム進捗表示 | タスク着手時・完了時に即座に更新 |
| **`tasks/todo.md`** | セッションをまたいで残る永続的な記録 | 各ステップ完了時にチェック済みにする |

| ステップ | 内容 |
|----------|------|
| **計画を立てる** | `tasks/todo.md` にチェック可能な項目でプランを書き、TodoWrite にも同期する |
| **計画を確認する** | 実装開始前にチェックインする |
| **進捗を追跡する** | TodoWrite で即時更新し、`tasks/todo.md` のチェックボックスも完了時に更新する |
| **変更を説明する** | 各ステップでハイレベルなサマリーを提示する |
| **結果を記録する** | `tasks/todo.md` にレビューセクションを追加する |
| **レッスンを残す** | 修正指摘を受けたら `tasks/lessons.md` を更新する |
| **コミット・PR** | 品質チェック通過後、コミット・プッシュ・PR 作成まで一気に実施する |

---

## 基本原則

**シンプルさを最優先**: あらゆる変更を可能な限りシンプルにする。影響するコードを最小限に留める。
**手を抜かない**: 根本原因を突き止める。一時しのぎの修正はしない。シニアエンジニアの水準で臨む。
**影響を最小化する**: 変更は必要な箇所だけに留める。バグを新たに持ち込まない。

## 詳細ルール参照

| ルールファイル | 内容 |
|--------------|------|
| [ai/rules/VCS_JUJUTSU.md](ai/rules/VCS_JUJUTSU.md) | jj の操作・ブックマークワークフロー |
| [ai/rules/GIT_WORKFLOW.md](ai/rules/GIT_WORKFLOW.md) | ブランチ命名・コミット規約・PR テンプレート |
| [ai/rules/GITHUB_PR_REVIEW.md](ai/rules/GITHUB_PR_REVIEW.md) | PR レビューコメントの `--jq` フィルタパターン |
