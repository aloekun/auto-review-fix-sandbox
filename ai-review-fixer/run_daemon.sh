#!/bin/bash
# run_daemon.sh
# orchestrator.py を60秒ごとに繰り返し実行するデーモンスクリプト。
# Ctrl+C で停止する。
#
# 使い方:
#   cd ai-review-fixer
#   bash run_daemon.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[daemon] Starting AI Review Fixer daemon..."

while true; do
  echo "[daemon] $(date '+%Y-%m-%d %H:%M:%S') Running orchestrator..."
  python orchestrator.py || echo "[daemon] orchestrator.py exited with error, continuing..."
  echo "[daemon] Sleeping 60 seconds..."
  sleep 60
done
