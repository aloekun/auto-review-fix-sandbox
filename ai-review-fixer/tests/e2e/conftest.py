"""
tests/e2e/conftest.py
E2E テスト用フィクスチャ。
E2E_GITHUB_REPO 環境変数が未設定の場合はすべてのテストをスキップする。
"""

import os

import pytest


def pytest_collection_modifyitems(items: list) -> None:
    """e2e マーカーを持つテストを E2E_GITHUB_REPO 未設定時にスキップする。"""
    e2e_repo = os.environ.get("E2E_GITHUB_REPO", "")
    if e2e_repo:
        return
    skip_marker = pytest.mark.skip(reason="E2E_GITHUB_REPO not set; skipping E2E tests")
    for item in items:
        if item.get_closest_marker("e2e"):
            item.add_marker(skip_marker)


@pytest.fixture
def e2e_repo() -> str:
    """テスト用 GitHub リポジトリ名 (owner/repo) を返す。"""
    repo = os.environ.get("E2E_GITHUB_REPO", "")
    if not repo:
        pytest.skip("E2E_GITHUB_REPO not set")
    return repo
