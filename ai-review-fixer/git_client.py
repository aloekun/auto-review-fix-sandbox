"""
git_client.py
subprocess.run による git コマンド実行をカプセル化する。
"""

import subprocess
from pathlib import Path


class GitClient:
    """subprocess で git コマンドを実行する具象実装。"""

    def run(
        self,
        args: list[str],
        cwd: Path | None = None,
        **kwargs: object,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(args, cwd=cwd, **kwargs)
