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
    # Only set Git Bash path on Windows if not already configured
    if sys.platform == "win32" and "CLAUDE_CODE_GIT_BASH_PATH" not in env:
        for candidate in [
            r"E:\Git\usr\bin\bash.exe",
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
        ]:
            if Path(candidate).exists():
                env["CLAUDE_CODE_GIT_BASH_PATH"] = candidate
                break

    # プロンプトは stdin 経由で渡す（コマンドライン引数はWindowsで32767文字制限があるため）
    with subprocess.Popen(
        ["claude", "-p", "--dangerously-skip-permissions"],
        cwd=workspace_dir,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    ) as proc:
        assert proc.stdin is not None
        assert proc.stdout is not None
        proc.stdin.write(prompt)
        proc.stdin.close()
        for line in proc.stdout:
            print(line, end="", flush=True)
        returncode = proc.wait()

    if returncode != 0:
        print(f"[claude_runner] Claude exited with code {returncode}", file=sys.stderr)

    return returncode
