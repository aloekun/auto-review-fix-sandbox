"""
tests/integration/test_orchestrator_integration.py
FakeGHClient + FakeClaudeRunner を使った Orchestrator の統合テスト。
実際の git リポジトリ上で動作する。
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from orchestrator import Orchestrator
from review_collector import PRInfo
from state_manager import StateManager
from tests.fakes.fake_claude_runner import FakeClaudeRunner

pytestmark = pytest.mark.integration

# git の setup 系コマンドのみモックし、log/show 等クエリ系は本物の subprocess に委譲する
_SETUP_SUBCMDS = {"fetch", "checkout", "reset", "clean", "clone"}


def _make_passthrough_git(workspace_dir: Path):
    """prepare_branch 系の git コマンドはモック、log 等クエリ系は実際に実行する。"""
    mock = MagicMock()

    def _side_effect(args, cwd=None, **kwargs):
        subcmd = args[1] if len(args) >= 2 else ""
        if subcmd in _SETUP_SUBCMDS:
            return MagicMock(returncode=0, stdout="", stderr="")
        return subprocess.run(args, cwd=cwd or workspace_dir, **kwargs)

    mock.run.side_effect = _side_effect
    return mock



@pytest.fixture
def base_config(integration_repo):
    """integration_repo を workspace として使う config。"""
    return {
        "repo": {"owner": "test-owner", "name": "test-repo"},
        "daemon": {
            "max_fix_attempts": 3,
            "workspace_dir": str(integration_repo),
            "poll_interval_seconds": 60,
            "patch_proposal_mode": False,
        },
        "reviewer_bot": "coderabbitai[bot]",
    }


@pytest.fixture
def head_sha(integration_repo):
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=integration_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# 正常フロー: レビューあり → コミット → state 更新 → PR コメント投稿
# ---------------------------------------------------------------------------

def test_normal_flow_commits_and_records_state(
    base_config, integration_repo, fake_gh, fake_claude, head_sha, tmp_path
):
    # PR info の head_sha を最新 HEAD に合わせる
    fake_gh.pr_infos[1] = PRInfo(
        number=1,
        head_ref="main",
        head_sha=head_sha,
        title="Test PR",
        head_repo_url="https://github.com/test/repo",
    )

    sm = StateManager(state_file=tmp_path / "state.json")

    # prepare_branch 系はモック、log 等クエリは実際に実行してコミット検出を正確にする
    mock_git = _make_passthrough_git(integration_repo)

    orch = Orchestrator(
        config=base_config,
        gh_client=fake_gh,
        git_client=mock_git,
        claude_runner=fake_claude,
        state_manager=sm,
    )

    # FakeClaudeRunner が integration_repo 内にファイルを作成してコミットする
    # ただし workspace_dir は config から解決されるため、_process_pr 内で
    # integration_repo が渡されるよう workspace_dir を直接置き換える
    # → _process_pr を直接呼ぶ
    orch._process_pr(
        pr_number=1,
        owner="test-owner",
        repo="test-repo",
        max_attempts=3,
        reviewer_bot="coderabbitai[bot]",
        workspace_dir=integration_repo,
    )

    # FakeClaudeRunner が実際にコミットを作成したことを確認する
    new_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=integration_repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert new_sha != head_sha, "FakeClaudeRunner should have created a new commit"
    assert sm.get_fix_attempts(1) == 1
    assert len(fake_gh.posted_comments) >= 1


# ---------------------------------------------------------------------------
# コミットなしのケース: state は更新される（無限リトライ防止）
# ---------------------------------------------------------------------------

def test_no_commit_does_not_update_state(
    base_config, integration_repo, fake_gh, head_sha, tmp_path
):
    fake_gh.pr_infos[1] = PRInfo(
        number=1,
        head_ref="main",
        head_sha=head_sha,
        title="Test PR",
        head_repo_url="https://github.com/test/repo",
    )

    sm = StateManager(state_file=tmp_path / "state.json")
    # FakeClaudeRunner(returncode=0) だがコミットしない（file_changes 空）
    no_commit_claude = FakeClaudeRunner(returncode=0, file_changes={})

    # パススルー git で log 等クエリを実 subprocess に委譲する。
    # 全モック（stdout=""）だと committed = "" != head_sha → True になり
    # no-commit ブランチに到達しない。
    mock_git = _make_passthrough_git(integration_repo)

    orch = Orchestrator(
        config=base_config,
        gh_client=fake_gh,
        git_client=mock_git,
        claude_runner=no_commit_claude,
        state_manager=sm,
    )
    orch._process_pr(
        pr_number=1,
        owner="test-owner",
        repo="test-repo",
        max_attempts=3,
        reviewer_bot="coderabbitai[bot]",
        workspace_dir=integration_repo,
    )

    # No-op runs now count the attempt to prevent infinite retry loops.
    assert sm.get_fix_attempts(1) == 1
    # no-commit 専用のコメントが投稿されているはず
    assert any(
        "without creating a commit" in c[1] or "no commit" in c[1].lower()
        for c in fake_gh.posted_comments
    )


# ---------------------------------------------------------------------------
# max_attempts 超過: PR スキップ
# ---------------------------------------------------------------------------

def test_max_attempts_skips_pr(
    base_config, integration_repo, fake_gh, head_sha, tmp_path
):
    fake_gh.pr_infos[1] = PRInfo(
        number=1,
        head_ref="main",
        head_sha=head_sha,
        title="Test PR",
        head_repo_url="https://github.com/test/repo",
    )

    sm = StateManager(state_file=tmp_path / "state.json")
    for i in range(3):
        sm.record_fix(1, [f"r{i}"])

    claude = FakeClaudeRunner()
    from unittest.mock import MagicMock
    mock_git = MagicMock()
    mock_git.run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    orch = Orchestrator(
        config=base_config,
        gh_client=fake_gh,
        git_client=mock_git,
        claude_runner=claude,
        state_manager=sm,
    )
    orch._process_pr(
        pr_number=1,
        owner="test-owner",
        repo="test-repo",
        max_attempts=3,
        reviewer_bot="coderabbitai[bot]",
        workspace_dir=integration_repo,
    )

    assert claude.prompts_received == []


# ---------------------------------------------------------------------------
# retry シナリオ: 2回目は previous_fix_diff がプロンプトに含まれる
# ---------------------------------------------------------------------------

def test_retry_includes_previous_fix_diff(
    base_config, integration_repo, fake_gh, head_sha, tmp_path
):
    fake_gh.pr_infos[1] = PRInfo(
        number=1,
        head_ref="main",
        head_sha=head_sha,
        title="Test PR",
        head_repo_url="https://github.com/test/repo",
    )

    sm = StateManager(state_file=tmp_path / "state.json")
    sm.record_fix(1, ["r0"])  # attempt 1 完了済み

    # tmp_path を base_dir にして runs/ 成果物をソースツリー外に置く
    patch_dir = tmp_path / "runs" / "pr-1" / "attempt-1"
    patch_dir.mkdir(parents=True, exist_ok=True)
    (patch_dir / "diff_after.patch").write_text("previous diff content", encoding="utf-8")

    claude = FakeClaudeRunner(returncode=0, file_changes={"new.txt": "new\n"})
    from unittest.mock import MagicMock
    mock_git = MagicMock()
    mock_git.run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    orch = Orchestrator(
        config=base_config,
        gh_client=fake_gh,
        git_client=mock_git,
        claude_runner=claude,
        state_manager=sm,
        base_dir=tmp_path,
    )
    orch._process_pr(
        pr_number=1,
        owner="test-owner",
        repo="test-repo",
        max_attempts=3,
        reviewer_bot="coderabbitai[bot]",
        workspace_dir=integration_repo,
    )

    assert len(claude.prompts_received) == 1
    assert "previous diff content" in claude.prompts_received[0]
