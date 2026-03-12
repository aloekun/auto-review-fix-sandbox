#!/usr/bin/env bash
# 第5層: 作業開始前に working copy が clean か確認する
# 前セッションの残留ファイルによる汚染を防ぐ
#
# 問題の構造:
#   旧 change（前セッション残留ファイルあり）
#       └── 新セッション: そのまま編集
#                 ↓ push 時に第4層 guard に弾かれる
#                 ↓ jj rebase で履歴だけ修正 ← 抜け穴
#                 ↓ push 通過（内容は汚染済み）
#
# 解決策: 作業開始時に working copy が clean であることを強制する

set -e

# Working copy に未記録の変更があれば中断する（description の有無に関係なくチェック）
changes=$(jj diff --stat 2>/dev/null || true)
if [ -n "$changes" ]; then
  echo "ERROR: Working copy is dirty (uncommitted changes remain)."
  echo "前セッションのファイルが残っています。"
  echo ""
  echo "変更ファイル:"
  jj diff --stat 2>/dev/null || true
  echo ""
  echo "解決方法:"
  echo "  jj abandon @   # 変更を破棄して前の change に戻る（取り消し不可）"
  echo "  jj restore     # ファイルを元に戻す（変更は消去するが change は残る）"
  echo ""
  echo "変更を保持して新タスクを開始したい場合は、先に変更を commit してください:"
  echo "  jj describe -m 'feat(scope): description'"
  echo "  jj bookmark create feature/N-description"
  echo "  pnpm jj-push --bookmark feature/N-description --allow-new"
  exit 1
fi

# origin/main を fetch してから新しい change を作成する
jj git fetch
jj new main@origin
