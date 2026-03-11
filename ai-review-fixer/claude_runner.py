"""
claude_runner.py
Claude Code CLI を非対話モードで呼び出す。
tmp/daemon-workspace/ 内で実行し、git コマンドが自由に使える環境を提供する。
"""

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

# Claude プロセスの最大実行時間（秒）。ハングアップ時にデーモンが止まらないようにする。
_CLAUDE_TIMEOUT_SECS = 600  # 10 minutes


class ClaudeRunner:
    """Claude Code CLI を stdin 経由のプロンプトで非対話実行する。"""

    def run(self, prompt: str, workspace_dir: Path) -> int:
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
        claude_bin = shutil.which("claude")
        if claude_bin is None:
            print(
                "[claude_runner] Could not find 'claude' in PATH",
                file=sys.stderr,
                flush=True,
            )
            return 127

        try:
            popen_proc = subprocess.Popen(
                [claude_bin, "-p", "--dangerously-skip-permissions"],
                cwd=workspace_dir,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            print(
                f"[claude_runner] Failed to launch claude: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return 1

        with popen_proc as proc:
            assert proc.stdin is not None
            assert proc.stdout is not None

            writer_error: list[Exception] = []

            def _write_stdin() -> None:
                try:
                    proc.stdin.write(prompt)
                except Exception as exc:
                    writer_error.append(exc)
                finally:
                    try:
                        proc.stdin.close()
                    except Exception as exc:
                        writer_error.append(exc)

            def _read_stdout() -> None:
                for line in proc.stdout:
                    print(line, end="", flush=True)

            # stdin 書き込みと stdout 読み取りを別スレッドで行いデッドロックを防ぐ。
            # 両スレッドにタイムアウトを設けてハングアップ時にデーモンが止まらないようにする。
            writer = threading.Thread(target=_write_stdin, daemon=True)
            reader = threading.Thread(target=_read_stdout, daemon=True)
            writer.start()
            reader.start()

            reader.join(timeout=_CLAUDE_TIMEOUT_SECS)
            # stdout が閉じれば stdin ライターも間もなく終了するので短いタイムアウトで十分
            writer.join(timeout=30)

            if reader.is_alive() or writer.is_alive():
                proc.kill()
                proc.wait()
                print(
                    f"[claude_runner] Claude timed out after {_CLAUDE_TIMEOUT_SECS}s",
                    file=sys.stderr,
                    flush=True,
                )
                return 1

            if writer_error:
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
                print(
                    "[claude_runner] Failed to send prompt to Claude",
                    file=sys.stderr,
                    flush=True,
                )
                return 1

            try:
                returncode = proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                print(
                    "[claude_runner] proc.wait() timed out",
                    file=sys.stderr,
                    flush=True,
                )
                return 1

        if returncode != 0:
            print(f"[claude_runner] Claude exited with code {returncode}", file=sys.stderr)

        return returncode
