#!/bin/bash
# 第4層: push 前にリモートブランチが @ の祖先にあるかチェックする
# main@origin または push 済み feature ブランチが祖先であれば push 許可
# stacked PR ワークフロー: PR N+1 は PR N のブランチ（push済み）をベースにできる

set -e

# リモートの最新状態を取得してからチェック（失敗時はスクリプト終了）
jj git fetch

result=$(jj log -r "ancestors(@) & remote_bookmarks()" --no-graph -T 'commit_id' 2>/dev/null)

if [ -z "$result" ]; then
  echo "ERROR: リモートブランチが @ の祖先にありません。"
  echo "作業は 'pnpm jj-start-change [base]' で開始してください:"
  echo "  pnpm jj-start-change              # main@origin をベースにする（通常の作業開始）"
  echo "  pnpm jj-start-change feat/pr1     # push済みのfeatureブランチをベースにする（stacked PR）"
  exit 1
fi

pnpm test:e2e
jj git push "$@"
