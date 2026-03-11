"""
tests/integration/conftest.py
統合テスト用フィクスチャ: tmp_git_repo + FakeGHClient + FakeClaudeRunner を組み合わせる。
"""

import subprocess
from pathlib import Path

import pytest

from review_collector import PRInfo, Review
from tests.fakes.fake_claude_runner import FakeClaudeRunner
from tests.fakes.fake_gh_client import FakeGHClient


@pytest.fixture
def integration_repo(tmp_git_repo: Path) -> Path:
    """
    統合テスト用の git リポジトリ。
    FakeClaudeRunner がコミットできるよう origin なしで動作する。
    """
    return tmp_git_repo


@pytest.fixture
def sample_review() -> Review:
    return Review(
        id="111",
        user_login="coderabbitai[bot]",
        state="CHANGES_REQUESTED",
        body="Please add type hints to `calculate` function.",
        submitted_at="2026-03-11T00:00:00Z",
    )


@pytest.fixture
def sample_pr_info(integration_repo: Path) -> PRInfo:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=integration_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    head_sha = result.stdout.strip()
    return PRInfo(
        number=1,
        head_ref="main",  # matches the actual temp repo branch
        head_sha=head_sha,
        title="Test PR",
        head_repo_url="https://github.com/test/repo",
    )


@pytest.fixture
def fake_gh(sample_review: Review, sample_pr_info: PRInfo) -> FakeGHClient:
    return FakeGHClient(
        open_prs=[1],
        pr_infos={1: sample_pr_info},
        reviews={1: [sample_review]},
        review_comments={1: []},
        pr_diffs={
            1: (
                "diff --git a/src/main.py b/src/main.py\n"
                "--- a/src/main.py\n"
                "+++ b/src/main.py\n"
                "@@ -1,3 +1,3 @@ def calculate\n"
                "-def calculate(x, y):\n"
                "+def calculate(x: int, y: int) -> int:\n"
                "     return x + y\n"
            )
        },
    )


@pytest.fixture
def fake_claude(integration_repo: Path) -> FakeClaudeRunner:
    return FakeClaudeRunner(
        returncode=0,
        file_changes={"src/main.py": "def calculate(x: int, y: int) -> int:\n    return x + y\n"},
    )
