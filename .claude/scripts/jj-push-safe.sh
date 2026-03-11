#!/bin/bash
# 第4層: push 前に main@origin が @ の祖先にあるかチェックする
# main@origin がベースでない change を誤って push することを防ぐ

# リモートの最新状態を取得してからチェック
jj git fetch

result=$(jj log -r "ancestors(@) & main@origin" --no-graph -T 'commit_id' 2>/dev/null)

if [ -z "$result" ]; then
  echo "ERROR: main@origin が @ の祖先にありません。"
  echo "作業は 'pnpm jj-start-change' で開始してください（fetch + jj new main@origin を実行します）。"
  exit 1
fi

jj git push "$@"
