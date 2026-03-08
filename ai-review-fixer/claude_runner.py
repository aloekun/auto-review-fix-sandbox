"""
claude_runner.py
Claude Code CLI を非対話モードで呼び出す。
tmp/daemon-workspace/ 内で実行し、git コマンドが自由に使える環境を提供する。
"""

import os
import subprocess
import sys
from pathlib import Path


def run_claude(prompt: str, workspace_dir: Path) -> int:
    """
    Claude Code CLI を print モード + dangerously-skip-permissions で実行する。

    Returns:
        returncode (0 = 成功)
    """
    print(f"[claude_runner] Running Claude Code in {workspace_dir}", flush=True)

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env.setdefault("CLAUDE_CODE_GIT_BASH_PATH", r"D:\Git\bin\bash.exe")

    result = subprocess.run(
        ["claude", "-p", prompt, "--dangerously-skip-permissions"],
        cwd=workspace_dir,
        text=True,
        encoding="utf-8",
        env=env,
    )

    if result.returncode != 0:
        print(f"[claude_runner] Claude exited with code {result.returncode}", file=sys.stderr)

    return result.returncode
