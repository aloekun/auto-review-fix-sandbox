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
        "owner": "test-owner",
        "repos": {"include": ["test-repo"]},
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
    gh = FakeGHClient(open_prs=[], repos=["test-repo"])
    orch = make_orchestrator(base_config, tmp_path, gh, FakeClaudeRunner())
    orch.run_once()  # should not raise


# --- no repos found ---


def test_run_once_does_nothing_when_no_repos_found(base_config, tmp_path):
    """list_repos が空リストを返すとき何もしない。"""
    gh = FakeGHClient(repos=[])  # list_repos returns []
    claude = FakeClaudeRunner()
    orch = make_orchestrator(base_config, tmp_path, gh, claude)
    orch.run_once()
    assert claude.prompts_received == []
    # リポジトリが存在しないため get_open_prs は一度も呼ばれない
    assert gh.repos_queried == []
    # list_repos は設定された owner で呼ばれること
    assert gh.list_repos_owners_called == ["test-owner"]


# --- multi-repo iteration ---


def test_run_once_iterates_multiple_repos(base_config, tmp_path):
    """repos.include を指定しないとき、list_repos で返ったリポジトリを全て処理する。"""
    all_repos_config = {
        **base_config,
        "repos": {"include": []},  # empty = all repos
    }
    # 2つのリポジトリ、どちらもオープン PR なし
    gh = FakeGHClient(open_prs=[], repos=["repo-a", "repo-b"])
    claude = FakeClaudeRunner()
    orch = make_orchestrator(all_repos_config, tmp_path, gh, claude)
    orch.run_once()
    # 両リポジトリの PR リストが照会されたことを確認する
    queried_repos = [repo for _, repo in gh.repos_queried]
    assert sorted(queried_repos) == ["repo-a", "repo-b"]
    # list_repos は設定された owner で呼ばれること
    assert gh.list_repos_owners_called == ["test-owner"]


def test_run_once_filters_repos_with_include(base_config, tmp_path):
    """repos.include が指定されているとき、含まれるリポジトリのみ処理する。"""
    # list_repos は 3つを返すが include は test-repo のみ
    gh = FakeGHClient(open_prs=[], repos=["test-repo", "other-repo", "another-repo"])
    claude = FakeClaudeRunner()
    orch = make_orchestrator(base_config, tmp_path, gh, claude)
    orch.run_once()
    # test-repo のみ照会され、other-repo / another-repo は除外されること
    queried_repos = [repo for _, repo in gh.repos_queried]
    assert queried_repos == ["test-repo"]
    # list_repos は設定された owner で呼ばれること
    assert gh.list_repos_owners_called == ["test-owner"]


# --- repo-level error isolation ---


def test_run_once_continues_after_repo_level_error(base_config, tmp_path):
    """1つのリポジトリで ensure_workspace が失敗しても残りのリポジトリを処理し続ける。"""
    from unittest.mock import MagicMock

    all_repos_config = {**base_config, "repos": {"include": []}}
    gh = FakeGHClient(open_prs=[], repos=["repo-a", "repo-bad", "repo-b"])
    claude = FakeClaudeRunner()
    sm = StateManager(state_file=tmp_path / "state.json")

    # repo-bad のときだけ clone で例外を投げる mock_git を作る
    def _git_side_effect(args, cwd=None, **_kwargs):  # noqa: ARG001
        result = MagicMock(returncode=0, stdout="", stderr="")
        if "clone" in args and "repo-bad" in args[-1]:
            raise RuntimeError("clone failed for repo-bad")
        return result

    mock_git = MagicMock()
    mock_git.run.side_effect = _git_side_effect

    orch = Orchestrator(
        config=all_repos_config,
        gh_client=gh,
        git_client=mock_git,
        claude_runner=claude,
        state_manager=sm,
    )
    # 例外が伝播しないこと
    orch.run_once()

    # repo-a と repo-b は get_open_prs まで到達していること
    queried_repos = [repo for _, repo in gh.repos_queried]
    assert "repo-a" in queried_repos
    assert "repo-b" in queried_repos
    # repo-bad はエラーで脱落しているため get_open_prs に到達しない
    assert "repo-bad" not in queried_repos


# --- max attempts guard ---


def test_run_once_skips_pr_when_max_attempts_reached(
    base_config, tmp_path, sample_review, sample_pr_info, tmp_git_repo
):
    gh = FakeGHClient(
        open_prs=[1],
        repos=["test-repo"],
        pr_infos={1: sample_pr_info},
        reviews={1: [sample_review]},
        review_comments={1: []},
        pr_diffs={1: ""},
    )
    sm = StateManager(state_file=tmp_path / "state.json")
    # max_fix_attempts = 3 に達したと見なす
    for _ in range(3):
        sm.record_fix("test-owner", "test-repo", 1, ["r1"])

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


def test_run_once_skips_when_no_new_reviews(base_config, tmp_path, sample_review, sample_pr_info):
    # すでに処理済みのレビューのみ
    sm = StateManager(state_file=tmp_path / "state.json")
    sm.record_fix("test-owner", "test-repo", 1, [sample_review.id])

    gh = FakeGHClient(
        open_prs=[1],
        repos=["test-repo"],
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
        repos=["test-repo"],
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
    assert sm.get_fix_attempts("test-owner", "test-repo", 1) == 1


# --- request_review ---


def test_request_review_called_when_committed(base_config, tmp_path, sample_review):
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


def test_request_review_called_for_each_actual_reviewer(base_config, tmp_path, sample_review):
    """複数ボットが CHANGES_REQUESTED を出した場合、両方に再レビューを依頼する。"""
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


def test_request_review_only_for_actual_reviewer_not_all_bots(base_config, tmp_path, sample_review):
    """2ボット登録でも1ボットだけがレビューした場合、そのボットにのみ再レビューを依頼する。"""
    pr_info = PRInfo(
        number=1,
        head_ref="main",
        head_sha="aabbcc",
        title="Test PR",
        head_repo_url="https://github.com/test-owner/test-repo",
    )
    # reviewer_bots に2ボット登録するが、CHANGES_REQUESTED は coderabbitai のみ
    multi_config = {
        **base_config,
        "reviewer_bots": ["coderabbitai[bot]", "chatgpt-codex-connector"],
    }
    gh = FakeGHClient(
        open_prs=[1],
        pr_infos={1: pr_info},
        reviews={1: [sample_review]},  # coderabbitai のみ
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

    # coderabbitai のみに再レビューが依頼され、codex には依頼されないこと
    assert gh.review_requests == [(1, "coderabbitai[bot]")]


def test_reviews_from_other_bots_are_ignored(base_config, tmp_path, sample_pr_info):
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
        repos=["test-repo"],
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


def test_request_review_not_called_when_no_commit(base_config, tmp_path, sample_review):
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
    mock_git.run.return_value = MagicMock(returncode=0, stdout=fixed_sha + "\n", stderr="")

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


# --- repos config validation ---


def test_run_once_raises_when_repos_is_not_mapping(base_config, tmp_path):
    """repos が mapping でない場合は TypeError を送出する。"""
    bad_config = {**base_config, "repos": ["test-repo"]}
    gh = FakeGHClient(open_prs=[])
    orch = make_orchestrator(bad_config, tmp_path, gh, FakeClaudeRunner())
    with pytest.raises(TypeError, match="'repos' must be a mapping"):
        orch.run_once()


def test_run_once_raises_when_repos_include_is_not_list(base_config, tmp_path):
    """repos.include がリストでない場合は TypeError を送出する。"""
    bad_config = {**base_config, "repos": {"include": "test-repo"}}
    gh = FakeGHClient(open_prs=[])
    orch = make_orchestrator(bad_config, tmp_path, gh, FakeClaudeRunner())
    with pytest.raises(TypeError, match="'repos.include' must be a list"):
        orch.run_once()


# --- workspace parent directory creation ---


def test_ensure_workspace_creates_parent_dirs(base_config, tmp_path):
    """_ensure_workspace は owner ディレクトリが存在しなくてもクローンできる。"""
    from unittest.mock import MagicMock

    mock_git = MagicMock()
    mock_git.run.return_value = MagicMock(returncode=0, stdout="", stderr="")

    gh = FakeGHClient(open_prs=[], repos=["test-repo"])
    sm = StateManager(state_file=tmp_path / "state.json")
    orch = Orchestrator(
        config=base_config,
        gh_client=gh,
        git_client=mock_git,
        claude_runner=FakeClaudeRunner(),
        state_manager=sm,
    )

    # owner ディレクトリが存在しない深いパスを workspace_dir として渡す
    deep_workspace = tmp_path / "ws" / "test-owner" / "test-repo"
    assert not deep_workspace.parent.exists()

    orch._ensure_workspace(deep_workspace, "test-owner", "test-repo")

    # 親ディレクトリが作成されていること
    assert deep_workspace.parent.exists()
    # git clone が呼ばれていること
    clone_call_args = mock_git.run.call_args[0][0]
    assert clone_call_args[0] == "git"
    assert clone_call_args[1] == "clone"
