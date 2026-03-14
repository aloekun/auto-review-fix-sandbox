"""
tests/e2e/conftest.py
E2E テスト用フィクスチャ。

E2E_GITHUB_REPO 環境変数（または ai-review-fixer/.env.e2e ファイル）が未設定の場合は
全 e2e テストをスキップする。

【GitHub 自己レビュー制限の回避について】
GitHub は PR 作者による自己レビューを禁止しているため、E2E テスト環境では
get_reviews() を差し替えてシンセティックレビューを注入する (_GHClientWithSyntheticReviews)。
review 取得以外のすべての操作（PR diff, PR comment 投稿, git clone/push）は実 API を使用する。
"""

from __future__ import annotations

import base64
import os
import subprocess
import time
from collections.abc import Generator
from pathlib import Path

import pytest

from interfaces import GHClientProtocol
from review_collector import GHClient, PRInfo, Review

# ---------------------------------------------------------------------------
# .env.e2e の自動読み込み
# ---------------------------------------------------------------------------

_ENV_FILE = Path(__file__).parent.parent.parent / ".env.e2e"

# プロジェクトルート（e2e ワークスペースの配置先として使用）
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_E2E_TMP_DIR = _PROJECT_ROOT / "tmp" / "e2e"


def _load_env_file() -> None:
    """ai-review-fixer/.env.e2e が存在すれば環境変数に読み込む（既存の値は上書きしない）。"""
    if not _ENV_FILE.exists():
        return
    for raw in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


# ---------------------------------------------------------------------------
# pytest コレクション時の skip 判定
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(items: list) -> None:
    """e2e マーカーを持つテストを E2E_GITHUB_REPO 未設定時にスキップする。"""
    e2e_repo = os.environ.get("E2E_GITHUB_REPO", "")
    if e2e_repo:
        return
    skip_marker = pytest.mark.skip(reason="E2E_GITHUB_REPO not set; skipping E2E tests")
    for item in items:
        if item.get_closest_marker("e2e"):
            item.add_marker(skip_marker)


# ---------------------------------------------------------------------------
# 基本フィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture
def e2e_repo() -> str:
    """テスト用 GitHub リポジトリ名 (owner/repo) を返す。"""
    repo = os.environ.get("E2E_GITHUB_REPO", "")
    if not repo:
        pytest.skip("E2E_GITHUB_REPO not set")
    return repo


def _rmtree_robust(path: Path) -> None:
    """Windows の読み取り専用ファイル（.git/objects 等）を含むディレクトリも削除する。"""
    import shutil
    import stat

    def _handle_error(func, err_path: str, _) -> None:  # type: ignore[no-untyped-def]
        os.chmod(err_path, stat.S_IWRITE)
        func(err_path)

    shutil.rmtree(path, onerror=_handle_error)


@pytest.fixture
def e2e_workspace() -> Generator[Path, None, None]:
    """
    E2E テスト用 git クローン先ディレクトリ。

    プロジェクトルートの tmp/e2e/workspace-<hex8>/ 配下に作成し、
    テスト後に削除する。tmp/ は gitignore 済みのため追跡されない。
    """
    import uuid

    workspace = _E2E_TMP_DIR / f"workspace-{uuid.uuid4().hex[:8]}"
    workspace.mkdir(parents=True, exist_ok=True)
    try:
        yield workspace
    finally:
        _rmtree_robust(workspace)


@pytest.fixture
def e2e_config(e2e_repo: str, e2e_workspace: Path) -> dict:
    """
    Orchestrator 用の設定辞書。

    workspace_dir に絶対パス (e2e_workspace / "clone") を指定する。
    Orchestrator 内部で Path(orchestrator.py の親) / workspace_dir が計算されるが、
    絶対パスが指定された場合は Python の Path 結合ルールにより絶対パスが優先される。
    """
    owner, name = e2e_repo.split("/", 1)
    workspace = e2e_workspace / "clone"
    return {
        "repo": {"owner": owner, "name": name},
        "daemon": {
            "poll_interval_seconds": 60,
            "max_fix_attempts": 3,
            "workspace_dir": str(workspace),
            "patch_proposal_mode": False,
        },
        "reviewer_bots": ["coderabbitai[bot]"],
    }


# ---------------------------------------------------------------------------
# テスト用 PR フィクスチャ
# ---------------------------------------------------------------------------

# テスト用ブランチに追加するコード（main との差分として PR diff に現れる）
_BRANCH_ADDITION = '''

def calculate_ratio(numerator, denominator):
    """Calculate the ratio of two numbers."""
    return numerator / denominator  # zero division risk when denominator is 0
'''


@pytest.fixture
def e2e_test_pr(e2e_repo: str) -> Generator[int, None, None]:
    """
    テスト用ブランチ (e2e/test-<timestamp>) を作成して PR を開く。
    テスト後に PR をクローズしてブランチを削除する。
    """
    owner, repo = e2e_repo.split("/", 1)
    branch = f"e2e/test-{int(time.time())}"
    pr_number: int | None = None

    def _gh_api(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["gh", "api", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )

    try:
        # main の HEAD SHA を取得
        res = _gh_api(
            f"repos/{owner}/{repo}/git/refs/heads/main",
            "--jq", ".object.sha",
        )
        main_sha = res.stdout.strip()

        # テスト用ブランチを作成
        _gh_api(
            f"repos/{owner}/{repo}/git/refs",
            "-X", "POST",
            "-f", f"ref=refs/heads/{branch}",
            "-f", f"sha={main_sha}",
        )

        # main の sample.py の内容と SHA を取得
        res = _gh_api(
            f"repos/{owner}/{repo}/contents/sample.py",
            "--jq", "{sha: .sha, content: .content}",
        )
        import json
        file_info = json.loads(res.stdout)
        file_sha = file_info["sha"]
        # GitHub API は base64 + 改行混じりで返す。パディング正規化してデコードする
        raw_b64 = file_info["content"].replace("\n", "")
        # base64 パディング補正
        padding = 4 - len(raw_b64) % 4
        if padding != 4:
            raw_b64 += "=" * padding
        current_content = base64.b64decode(raw_b64).decode("utf-8")

        # テスト用関数を末尾に追加してコミット
        new_content_bytes = (current_content + _BRANCH_ADDITION).encode("utf-8")
        new_content_b64 = base64.b64encode(new_content_bytes).decode("ascii")

        _gh_api(
            f"repos/{owner}/{repo}/contents/sample.py",
            "-X", "PUT",
            "-f", "message=feat: add calculate_ratio function (E2E test)",
            "-f", f"content={new_content_b64}",
            "-f", f"sha={file_sha}",
            "-f", f"branch={branch}",
        )

        # PR を作成
        res = subprocess.run(
            [
                "gh", "pr", "create",
                "--repo", f"{owner}/{repo}",
                "--title", "[E2E Test] Auto-fix test PR",
                "--body", "Automated test PR created by the E2E test suite.",
                "--base", "main",
                "--head", branch,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        # 出力は PR URL: https://github.com/owner/repo/pull/123
        pr_url = res.stdout.strip()
        pr_number = int(pr_url.rstrip("/").split("/")[-1])

        yield pr_number

    finally:
        if pr_number is not None:
            # PR をクローズ（--delete-branch でブランチも削除）
            subprocess.run(
                [
                    "gh", "pr", "close", str(pr_number),
                    "--repo", f"{owner}/{repo}",
                    "--delete-branch",
                    "--comment", "Closed by E2E test cleanup.",
                ],
                check=False,
                capture_output=True,
            )
        else:
            # PR 作成前に失敗した場合はブランチだけ削除
            subprocess.run(
                [
                    "gh", "api",
                    f"repos/{owner}/{repo}/git/refs/heads/{branch}",
                    "-X", "DELETE",
                ],
                check=False,
                capture_output=True,
            )


# ---------------------------------------------------------------------------
# シンセティックレビュー（GitHub 自己レビュー禁止の回避）
# ---------------------------------------------------------------------------

_SYNTHETIC_REVIEW = Review(
    id="e2e-synthetic-review-1",
    user_login="coderabbitai[bot]",
    state="CHANGES_REQUESTED",
    body=(
        "**[E2E Test Review]** "
        "The `calculate_ratio` function is missing a zero-division check. "
        "Please handle the case where `denominator == 0` to avoid `ZeroDivisionError`."
    ),
    submitted_at="2026-03-12T00:00:00Z",
)


class _GHClientWithSyntheticReviews:
    """
    実 GHClient のラッパー。get_reviews() のみシンセティックデータを返す。

    GitHub は PR 作者による自己レビューを禁止しているため、
    E2E テスト環境では get_reviews() を差し替えてテストレビューを注入する。
    それ以外のすべての操作は実 API を使用する。

    open_prs_override を指定すると get_open_prs() もオーバーライドされ、
    テスト対象 PR だけを返す（他のオープン PR に誤って適用されることを防ぐ）。
    """

    def __init__(
        self,
        real: GHClient,
        reviews: list[Review],
        open_prs_override: list[int] | None = None,
    ) -> None:
        self._real = real
        self._reviews = reviews
        self._open_prs_override = open_prs_override

    def get_open_prs(self, owner: str, repo: str) -> list[int]:
        if self._open_prs_override is not None:
            return self._open_prs_override
        return self._real.get_open_prs(owner, repo)

    def get_pr_info(self, owner: str, repo: str, pr_number: int) -> PRInfo:
        return self._real.get_pr_info(owner, repo, pr_number)

    def get_reviews(self, _owner: str, _repo: str, _pr_number: int) -> list[Review]:
        return self._reviews

    def get_review_comments(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict]:
        return self._real.get_review_comments(owner, repo, pr_number)

    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        return self._real.get_pr_diff(owner, repo, pr_number)

    def post_pr_comment(
        self, owner: str, repo: str, pr_number: int, body: str
    ) -> None:
        self._real.post_pr_comment(owner, repo, pr_number, body)

    def request_review(
        self, owner: str, repo: str, pr_number: int, reviewer_bot: str
    ) -> None:
        self._real.request_review(owner, repo, pr_number, reviewer_bot)


@pytest.fixture
def e2e_gh_client(e2e_test_pr: int) -> GHClientProtocol:
    """
    実 GHClient にシンセティックレビューを注入した E2E 用クライアント。
    open_prs_override でテスト対象 PR のみを返し、他の PR に誤適用されることを防ぐ。
    """
    return _GHClientWithSyntheticReviews(
        real=GHClient(),
        reviews=[_SYNTHETIC_REVIEW],
        open_prs_override=[e2e_test_pr],
    )
