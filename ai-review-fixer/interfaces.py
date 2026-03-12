"""
interfaces.py
依存注入で使う Protocol（構造的サブタイピング）を定義する。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from review_collector import PRInfo, Review


class GHClientProtocol(Protocol):
    def get_open_prs(self, owner: str, repo: str) -> list[int]: ...

    def get_pr_info(self, owner: str, repo: str, pr_number: int) -> PRInfo: ...

    def get_reviews(self, owner: str, repo: str, pr_number: int) -> list[Review]: ...

    def get_review_comments(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict]: ...

    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str: ...

    def post_pr_comment(
        self, owner: str, repo: str, pr_number: int, body: str
    ) -> None: ...

    def request_review(
        self, owner: str, repo: str, pr_number: int, reviewer_bot: str
    ) -> None: ...


class GitClientProtocol(Protocol):
    def run(
        self,
        args: list[str],
        cwd: Path | None = None,
        **kwargs: object,
    ) -> subprocess.CompletedProcess: ...


class ClaudeRunnerProtocol(Protocol):
    def run(self, prompt: str, workspace_dir: Path) -> int: ...


class StateManagerProtocol(Protocol):
    def get_fix_attempts(self, pr_number: int) -> int: ...

    def get_processed_review_ids(self, pr_number: int) -> list[str]: ...

    def record_fix(self, pr_number: int, review_ids: list) -> int: ...

    def reset_pr(self, pr_number: int) -> None: ...
