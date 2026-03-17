#!/bin/bash
# pnpm gh-api ラッパー: jq フィルタの引数を正しく gh api に渡す
# pnpm の直接マッピング ("gh-api": "gh api") では --jq 内の \(...) 等が
# 引数パースで壊れるため、bash の "$@" で引数を保護して渡す。
exec gh api "$@"
