"""tests/unit/test_run_logger.py"""

import json
import subprocess

import pytest

from review_collector import Review
from run_logger import RunLogger, _format_reviews_text


@pytest.fixture
def git_repo(tmp_path):
    """git init 済みの一時ディレクトリ（ファイルなし + initial commit）を返す。"""
    env = {
        **__import__("os").environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "t@t.local",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "t@t.local",
    }
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, env=env)
    subprocess.run(["git", "config", "user.email", "t@t.local"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "init.txt").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, env=env)
    return tmp_path


@pytest.fixture
def sample_review():
    return Review("r1", "bot", "CHANGES_REQUESTED", "Fix this.", "2026-03-11T00:00:00Z")


@pytest.fixture
def logger():
    return RunLogger()


# --- save_run_artifacts ---

def test_save_artifacts_creates_run_dir(logger, git_repo, tmp_path, sample_review):
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    head_sha = result.stdout.strip()

    base_dir = tmp_path / "base"
    base_dir.mkdir()

    data = logger.save_run_artifacts(
        base_dir=base_dir,
        pr_number=1,
        attempt=1,
        prompt="test prompt",
        reviews=[sample_review],
        inline_comments=[],
        diff_before="diff content",
        workspace_dir=git_repo,
        original_head_sha=head_sha,
    )

    run_dir = base_dir / "runs" / "pr-1" / "attempt-1"
    assert run_dir.exists()
    assert (run_dir / "prompt.txt").read_text() == "test prompt"
    assert (run_dir / "diff_before.patch").read_text() == "diff content"
    assert data["committed"] is False  # no new commit was made


def test_save_artifacts_detects_new_commit(logger, git_repo, tmp_path, sample_review):
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    original_sha = result.stdout.strip()

    # Simulate a new commit
    env = {
        **__import__("os").environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "t@t.local",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "t@t.local",
    }
    (git_repo / "new_file.txt").write_text("new\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=git_repo, check=True)
    subprocess.run(["git", "commit", "-m", "fix"], cwd=git_repo, check=True, env=env)

    base_dir = tmp_path / "base"
    base_dir.mkdir()

    data = logger.save_run_artifacts(
        base_dir=base_dir,
        pr_number=1,
        attempt=1,
        prompt="test",
        reviews=[sample_review],
        inline_comments=[],
        diff_before="",
        workspace_dir=git_repo,
        original_head_sha=original_sha,
    )

    assert data["committed"] is True
    assert data["files_changed"] == ["new_file.txt"]
    assert (base_dir / "runs" / "pr-1" / "attempt-1" / "diff_after.patch").exists()


# --- save_structured_log ---

def test_save_structured_log_creates_json(logger, tmp_path):
    log_data = {"pr": 1, "attempt": 1, "committed": True, "files_changed": []}
    logger.save_structured_log(tmp_path, log_data)

    log_files = list((tmp_path / "logs").rglob("*.json"))
    assert len(log_files) == 1
    loaded = json.loads(log_files[0].read_text())
    assert loaded["pr"] == 1


# --- _format_reviews_text ---

def test_format_reviews_text_includes_review_body():
    review = Review("1", "bot", "CHANGES_REQUESTED", "Fix it.", "2026-01-01")
    text = _format_reviews_text([review], [])
    assert "Fix it." in text
    assert "bot" in text


def test_format_reviews_text_includes_inline_comments():
    review = Review("1", "bot", "CHANGES_REQUESTED", "", "2026-01-01")
    comment = {"path": "src/main.py", "line": 5, "body": "Missing type hint"}
    text = _format_reviews_text([review], [comment])
    assert "src/main.py" in text
    assert "Missing type hint" in text
