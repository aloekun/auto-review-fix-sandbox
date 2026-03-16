# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

「レビュー → Local AI Agent が自動修正」のフローを実験・改善するサンドボックス。

## コマンド

Bash コマンドは `pnpm` スクリプト経由で実行する（許可管理の簡素化のため）。`jj` や `gh` を直接実行せず、対応する `pnpm` スクリプトを使うこと。

詳細は [package.json](package.json) を参照。

## バージョン管理 (Jujutsu)

**`git` コマンドは `.claude/validate-command.exe` フックによりブロックされる。** 代わりに `jj` を `pnpm` スクリプト経由で使用する。

詳細は [ai/rules/VCS_JUJUTSU.md](ai/rules/VCS_JUJUTSU.md) を参照。

## ブランチ・コミット規約

詳細は [docs\adr\002-remote-based-branch-strategy.md](docs\adr\002-remote-based-branch-strategy.md) を参照。

## タスク管理

詳細 [docs\adr\003-dual-track-task-management.md](docs\adr\003-dual-track-task-management.md) を参照。

---

## 詳細ルール参照

| ルールファイル | 内容 |
|--------------|------|
| [ai/rules/GIT_WORKFLOW.md](ai/rules/GIT_WORKFLOW.md) | ブランチ命名・コミット規約・PR テンプレート |
| [ai/rules/GITHUB_PR_REVIEW.md](ai/rules/GITHUB_PR_REVIEW.md) | PR レビューコメントの `--jq` フィルタパターン |
