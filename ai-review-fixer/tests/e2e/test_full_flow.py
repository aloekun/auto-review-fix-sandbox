"""
tests/e2e/test_full_flow.py
E2E テスト: 実際の GitHub リポジトリと Claude Code CLI を使ったフルフロー検証。

【事前準備 (ユーザー作業)】
1. テスト用 GitHub リポジトリを作成し main ブランチにコードを push する。

2. ai-review-fixer/.env.e2e を作成する（gitignore 済み）:
   E2E_GITHUB_REPO=<owner>/test-review-fix-sandbox

3. gh auth login で認証済みであることを確認する。

4. claude コマンドがインストール済みであることを確認する。

【実行方法】
   pnpm py-test:e2e
"""

import subprocess
from pathlib import Path

import pytest

from orchestrator import Orchestrator
from state_manager import StateManager

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------


def _get_pr_head_sha(owner: str, repo: str, pr_number: int) -> str:
    """PR ブランチの最新コミット SHA を GitHub API から取得する。"""
    res = subprocess.run(
        [
            "gh", "api",
            f"repos/{owner}/{repo}/pulls/{pr_number}",
            "--jq", ".head.sha",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return res.stdout.strip()


def _get_pr_issue_comments(owner: str, repo: str, pr_number: int) -> list[str]:
    """PR のイシューコメント本文一覧を GitHub API から取得する。"""
    res = subprocess.run(
        [
            "gh", "api",
            "--paginate",
            "--jq", ".[].body",
            f"repos/{owner}/{repo}/issues/{pr_number}/comments",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return [line for line in res.stdout.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# E2E テスト
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_full_flow(
    e2e_config: dict,
    e2e_test_pr: int,
    e2e_gh_client,
    tmp_path: Path,
) -> None:
    """
    フルフロー E2E テスト。

    1. e2e_test_pr fixture がテスト用ブランチを作成して PR を開く。
    2. Orchestrator を実際の ClaudeRunner + シンセティックレビューで実行する。
       - get_reviews() のみシンセティックデータを注入（GitHub 自己レビュー禁止の回避）
       - clone / checkout / commit / push はすべて実 git を使用する。
    3. PR ブランチに fix コミットが push されたことを検証する。
    4. PR コメントに "AI Auto Fix Report" が含まれることを検証する。
    """
    owner = e2e_config["owner"]
    repos_include = e2e_config["repos"]["include"]
    if not repos_include:
        pytest.fail("e2e_config['repos']['include'] is empty — cannot determine test repo name")
    repo = repos_include[0]

    # PR 作成直後の HEAD SHA を記録する
    initial_sha = _get_pr_head_sha(owner, repo, e2e_test_pr)
    print(f"\n[e2e] PR #{e2e_test_pr} initial SHA: {initial_sha}")

    # Orchestrator を構築して 1 サイクル実行する
    state = StateManager(state_file=tmp_path / "state.json")
    orchestrator = Orchestrator(
        config=e2e_config,
        gh_client=e2e_gh_client,
        state_manager=state,
        base_dir=tmp_path,
    )
    orchestrator.run_once()

    # 検証 1: PR ブランチに新しいコミットが push された
    final_sha = _get_pr_head_sha(owner, repo, e2e_test_pr)
    print(f"[e2e] PR #{e2e_test_pr} final SHA:   {final_sha}")
    assert final_sha != initial_sha, (
        f"Expected a new commit on PR #{e2e_test_pr} after Orchestrator ran, "
        f"but HEAD SHA did not change (still {initial_sha}). "
        "Claude may not have committed or pushed."
    )

    # 検証 2: PR コメントに "AI Auto Fix Report" が含まれる
    comments = _get_pr_issue_comments(owner, repo, e2e_test_pr)
    report_comments = [c for c in comments if "AI Auto Fix Report" in c]
    assert report_comments, (
        f"Expected a PR comment containing 'AI Auto Fix Report' on PR #{e2e_test_pr}, "
        f"but none was found. Posted comments: {comments!r}"
    )
    print(f"[e2e] Fix report comment found on PR #{e2e_test_pr}.")

    # 検証 3: "@coderabbitai review" コメントが投稿された（再レビュー依頼）
    review_request_comments = [c for c in comments if "@coderabbitai review" in c]
    assert review_request_comments, (
        f"Expected a PR comment containing '@coderabbitai review' on PR #{e2e_test_pr}, "
        f"but none was found. Posted comments: {comments!r}"
    )
    print(f"[e2e] Re-review request comment found on PR #{e2e_test_pr}.")
