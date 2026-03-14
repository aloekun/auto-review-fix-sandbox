"""tests/unit/test_orchestrator.py"""

import pytest

from orchestrator import Orchestrator
from review_collector import PRInfo, Review
from state_manager import StateManager
from tests.fakes.fake_claude_runner import FakeClaudeRunner
from tests.fakes.fake_gh_client import FakeGHClient


@pytest.fixture
def base_config():
    return {
        "repo": {"owner": "test-owner", "name": "test-repo"},
        "daemon": {
            "max_fix_attempts": 3,
            "workspace_dir": "../tmp/daemon-workspace",
            "poll_interval_seconds": 60,
            "patch_proposal_mode": False,
        },
        "reviewer_bots": ["coderabbitai[bot]"],
    }


@pytest.fixture
def sample_review():
    return Review(
        id="r1",
        user_login="coderabbitai[bot]",
        state="CHANGES_REQUESTED",
        body="Fix this.",
        submitted_at="2026-03-11T00:00:00Z",
    )


@pytest.fixture
def sample_pr_info(tmp_git_repo):
    import subprocess

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_git_repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return PRInfo(
        number=1,
        head_ref="main",
        head_sha=result.stdout.strip(),
        title="Test PR",
        head_repo_url="https://github.com/test-owner/test-repo",
    )


def make_orchestrator(
    config,
    tmp_path,
    gh_client,
    claude_runner,
    state_file=None,
):

    sm = StateManager(state_file=state_file or tmp_path / "state.json")
    # GitClient が git コマンドを実行するが、workspace_dir のクローン/フェッチは
    # ensure_workspace が担うため、ここでは mock_git で迂回する
    mock_git = _make_mock_git()
    return Orchestrator(
        config=config,
        gh_client=gh_client,
        git_client=mock_git,
        claude_runner=claude_runner,
        state_manager=sm,
    )


def _make_mock_git():
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    return mock


# --- no open PRs ---

def test_run_once_does_nothing_when_no_open_prs(base_config, tmp_path):
    gh = FakeGHClient(open_prs=[])
    orch = make_orchestrator(base_config, tmp_path, gh, FakeClaudeRunner())
    orch.run_once()  # should not raise


# --- max attempts guard ---

def test_run_once_skips_pr_when_max_attempts_reached(
    base_config, tmp_path, sample_review, sample_pr_info, tmp_git_repo
):
    gh = FakeGHClient(
        open_prs=[1],
        pr_infos={1: sample_pr_info},
        reviews={1: [sample_review]},
        review_comments={1: []},
        pr_diffs={1: ""},
    )
    sm = StateManager(state_file=tmp_path / "state.json")
    # max_fix_attempts = 3 に達したと見なす
    for _ in range(3):
        sm.record_fix(1, ["r1"])

    claude = FakeClaudeRunner()
    mock_git = _make_mock_git()
    orch = Orchestrator(
        config=base_config,
        gh_client=gh,
        git_client=mock_git,
        claude_runner=claude,
        state_manager=sm,
    )
    orch.run_once()

    # Claude は呼ばれないはず
    assert claude.prompts_received == []


# --- no new reviews ---

def test_run_once_skips_when_no_new_reviews(
    base_config, tmp_path, sample_review, sample_pr_info
):
    # すでに処理済みのレビューのみ
    sm = StateManager(state_file=tmp_path / "state.json")
    sm.record_fix(1, [sample_review.id])

    gh = FakeGHClient(
        open_prs=[1],
        pr_infos={1: sample_pr_info},
        reviews={1: [sample_review]},
        review_comments={1: []},
        pr_diffs={1: ""},
    )
    claude = FakeClaudeRunner()
    mock_git = _make_mock_git()
    orch = Orchestrator(
        config=base_config,
        gh_client=gh,
        git_client=mock_git,
        claude_runner=claude,
        state_manager=sm,
    )
    orch.run_once()

    assert claude.prompts_received == []


# --- claude failure ---

def test_run_once_records_attempt_when_claude_fails(
    base_config, tmp_path, sample_review, sample_pr_info, tmp_git_repo
):
    """Claude が非ゼロ exit を返した場合も attempt をカウントして無限リトライを防ぐ。"""
    gh = FakeGHClient(
        open_prs=[1],
        pr_infos={1: sample_pr_info},
        reviews={1: [sample_review]},
        review_comments={1: []},
        pr_diffs={1: ""},
    )
    sm = StateManager(state_file=tmp_path / "state.json")
    claude = FakeClaudeRunner(returncode=1)
    mock_git = _make_mock_git()

    orch = Orchestrator(
        config=base_config,
        gh_client=gh,
        git_client=mock_git,
        claude_runner=claude,
        state_manager=sm,
    )
    orch.run_once()

    # 失敗でも attempt をカウントする（無限リトライ防止）
    assert sm.get_fix_attempts(1) == 1


# --- request_review ---

def test_request_review_called_when_committed(
    base_config, tmp_path, sample_review
):
    """committed=True のとき request_review が1回呼ばれる。

    mock_git は stdout="" を返すため commit_hash="" となり、
    original_head_sha="aabbcc" と不一致 → committed=True。
    """
    pr_info = PRInfo(
        number=1,
        head_ref="main",
        head_sha="aabbcc",
        title="Test PR",
        head_repo_url="https://github.com/test-owner/test-repo",
    )
    gh = FakeGHClient(
        open_prs=[1],
        pr_infos={1: pr_info},
        reviews={1: [sample_review]},
        review_comments={1: []},
        pr_diffs={1: ""},
    )
    sm = StateManager(state_file=tmp_path / "state.json")
    claude = FakeClaudeRunner(returncode=0, file_changes={})
    mock_git = _make_mock_git()

    orch = Orchestrator(
        config=base_config,
        gh_client=gh,
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
        reviewer_bots=["coderabbitai[bot]"],
        workspace_dir=tmp_path,
    )

    assert gh.review_requests == [(1, "coderabbitai[bot]")]


def test_request_review_called_for_each_bot_when_committed(
    base_config, tmp_path, sample_review
):
    """複数 reviewer_bots 設定時、commit 後に全ボットへ request_review が呼ばれる。"""
    pr_info = PRInfo(
        number=1,
        head_ref="main",
        head_sha="aabbcc",
        title="Test PR",
        head_repo_url="https://github.com/test-owner/test-repo",
    )
    # chatgpt-codex-connector のレビューも用意
    codex_review = Review(
        id="r2",
        user_login="chatgpt-codex-connector",
        state="CHANGES_REQUESTED",
        body="Fix that.",
        submitted_at="2026-03-11T00:00:00Z",
    )
    multi_config = {
        **base_config,
        "reviewer_bots": ["coderabbitai[bot]", "chatgpt-codex-connector"],
    }
    gh = FakeGHClient(
        open_prs=[1],
        pr_infos={1: pr_info},
        reviews={1: [sample_review, codex_review]},
        review_comments={1: []},
        pr_diffs={1: ""},
    )
    sm = StateManager(state_file=tmp_path / "state.json")
    claude = FakeClaudeRunner(returncode=0, file_changes={})
    mock_git = _make_mock_git()

    orch = Orchestrator(
        config=multi_config,
        gh_client=gh,
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
        reviewer_bots=["coderabbitai[bot]", "chatgpt-codex-connector"],
        workspace_dir=tmp_path,
    )

    assert set(gh.review_requests) == {
        (1, "coderabbitai[bot]"),
        (1, "chatgpt-codex-connector"),
    }


def test_reviews_from_other_bots_are_ignored(
    base_config, tmp_path, sample_pr_info
):
    """reviewer_bots に含まれないボットのレビューは処理されない。"""
    other_review = Review(
        id="r-other",
        user_login="some-other-bot",
        state="CHANGES_REQUESTED",
        body="Unrelated.",
        submitted_at="2026-03-11T00:00:00Z",
    )
    gh = FakeGHClient(
        open_prs=[1],
        pr_infos={1: sample_pr_info},
        reviews={1: [other_review]},
        review_comments={1: []},
        pr_diffs={1: ""},
    )
    claude = FakeClaudeRunner()
    mock_git = _make_mock_git()
    sm = StateManager(state_file=tmp_path / "state.json")
    orch = Orchestrator(
        config=base_config,
        gh_client=gh,
        git_client=mock_git,
        claude_runner=claude,
        state_manager=sm,
    )
    orch.run_once()

    assert claude.prompts_received == []


def test_request_review_not_called_when_no_commit(
    base_config, tmp_path, sample_review
):
    """committed=False のとき request_review は呼ばれない。

    mock_git が original_head_sha と同じ値を返すため committed=False。
    """
    from unittest.mock import MagicMock

    fixed_sha = "aabbcc"
    pr_info = PRInfo(
        number=1,
        head_ref="main",
        head_sha=fixed_sha,
        title="Test PR",
        head_repo_url="https://github.com/test-owner/test-repo",
    )
    gh = FakeGHClient(
        open_prs=[1],
        pr_infos={1: pr_info},
        reviews={1: [sample_review]},
        review_comments={1: []},
        pr_diffs={1: ""},
    )
    sm = StateManager(state_file=tmp_path / "state.json")
    claude = FakeClaudeRunner(returncode=0, file_changes={})

    # git log -1 --format=%H が fixed_sha を返すよう設定 → committed=False
    mock_git = MagicMock()
    mock_git.run.return_value = MagicMock(
        returncode=0, stdout=fixed_sha + "\n", stderr=""
    )

    orch = Orchestrator(
        config=base_config,
        gh_client=gh,
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
        reviewer_bots=["coderabbitai[bot]"],
        workspace_dir=tmp_path,
    )

    assert gh.review_requests == []


# --- reviewer_bots type validation ---


def test_run_once_raises_when_reviewer_bots_missing(base_config, tmp_path):
    """reviewer_bots キーがない場合は KeyError を送出する。"""
    bad_config = dict(base_config)
    del bad_config["reviewer_bots"]

    gh = FakeGHClient(open_prs=[])
    orch = make_orchestrator(bad_config, tmp_path, gh, FakeClaudeRunner())
    with pytest.raises(KeyError):
        orch.run_once()


def test_run_once_raises_when_reviewer_bots_is_string(base_config, tmp_path):
    """reviewer_bots がスカラー文字列の場合は TypeError を送出する。"""
    bad_config = dict(base_config)
    bad_config["reviewer_bots"] = "coderabbitai[bot]"

    gh = FakeGHClient(open_prs=[])
    orch = make_orchestrator(bad_config, tmp_path, gh, FakeClaudeRunner())
    with pytest.raises(TypeError, match="must be a list"):
        orch.run_once()
