"""
tests/conftest.py
全テスト共通のフィクスチャ。
"""

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    """初期コミット済みの一時 git リポジトリを返す。"""
    env = {
        **__import__("os").environ,
        "GIT_AUTHOR_NAME": "Test User",
        "GIT_AUTHOR_EMAIL": "test@test.local",
        "GIT_COMMITTER_NAME": "Test User",
        "GIT_COMMITTER_EMAIL": "test@test.local",
    }

    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, env=env)
    subprocess.run(
        ["git", "config", "user.email", "test@test.local"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
    )

    # 初期ファイルを追加してコミット
    (tmp_path / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=tmp_path,
        check=True,
        env=env,
    )

    return tmp_path
