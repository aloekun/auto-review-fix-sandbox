"""
fake_claude_runner.py
テスト用の ClaudeRunner 偽実装。
実際に claude CLI を呼ばず、指定されたファイル変更 + git commit をシミュレートする。
"""

import subprocess
from pathlib import Path


class FakeClaudeRunner:
    """
    ClaudeRunnerProtocol の偽実装。

    - returncode=0 の場合: workspace_dir 内のファイルを変更して git commit する
    - returncode!=0 の場合: 何もせず指定コードを返す
    """

    def __init__(
        self,
        returncode: int = 0,
        file_changes: dict[str, str] | None = None,
        commit_message: str = "fix: auto-fix by FakeClaudeRunner",
    ) -> None:
        self.returncode = returncode
        default_changes = {"fixed.txt": "auto-fixed content\n"}
        self.file_changes = file_changes if file_changes is not None else default_changes
        self.commit_message = commit_message
        self.prompts_received: list[str] = []

    def run(self, prompt: str, workspace_dir: Path) -> int:
        self.prompts_received.append(prompt)

        if self.returncode != 0:
            return self.returncode

        if not self.file_changes:
            return 0

        # ファイルを変更する
        for rel_path, content in self.file_changes.items():
            target = workspace_dir / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        # git add + commit
        subprocess.run(["git", "add", "-A"], cwd=workspace_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", self.commit_message],
            cwd=workspace_dir,
            check=True,
            env={
                **__import__("os").environ,
                "GIT_AUTHOR_NAME": "FakeClaudeRunner",
                "GIT_AUTHOR_EMAIL": "fake@test.local",
                "GIT_COMMITTER_NAME": "FakeClaudeRunner",
                "GIT_COMMITTER_EMAIL": "fake@test.local",
            },
        )
        return 0
