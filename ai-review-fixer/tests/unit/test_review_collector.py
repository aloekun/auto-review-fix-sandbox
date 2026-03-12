"""tests/unit/test_review_collector.py"""

import json

import pytest

from review_collector import GHClient


@pytest.fixture
def client():
    return GHClient()


def _mock_run(mocker, stdout: str, returncode: int = 0):
    """subprocess.run をモックして指定の stdout を返すヘルパー。"""
    mock = mocker.patch("review_collector.subprocess.run")
    mock.return_value.stdout = stdout
    mock.return_value.returncode = returncode
    return mock


# --- get_open_prs ---

def test_get_open_prs_returns_numbers(client, mocker):
    _mock_run(mocker, json.dumps([{"number": 1}, {"number": 2}]))
    result = client.get_open_prs("owner", "repo")
    assert result == [1, 2]


def test_get_open_prs_empty(client, mocker):
    _mock_run(mocker, json.dumps([]))
    assert client.get_open_prs("owner", "repo") == []


# --- get_pr_info ---

def test_get_pr_info_parses_fields(client, mocker):
    data = {
        "number": 42,
        "headRefName": "feature/x",
        "headRefOid": "abc123",
        "title": "My PR",
        "headRepository": {"url": "https://github.com/owner/repo"},
    }
    _mock_run(mocker, json.dumps(data))
    info = client.get_pr_info("owner", "repo", 42)
    assert info.number == 42
    assert info.head_ref == "feature/x"
    assert info.head_sha == "abc123"
    assert info.title == "My PR"


def test_get_pr_info_fallback_url(client, mocker):
    data = {
        "number": 1,
        "headRefName": "main",
        "headRefOid": "sha",
        "title": "T",
        "headRepository": None,
    }
    _mock_run(mocker, json.dumps(data))
    info = client.get_pr_info("owner", "repo", 1)
    assert info.head_repo_url == "https://github.com/owner/repo"


# --- get_reviews ---

def test_get_reviews_parses_list(client, mocker):
    item = {
        "id": 111,
        "user": {"login": "coderabbitai[bot]"},
        "state": "CHANGES_REQUESTED",
        "body": "Fix this.",
        "submitted_at": "2026-01-01",
    }
    # gh api --paginate --jq '.[]' outputs one JSON object per line
    _mock_run(mocker, json.dumps(item))
    reviews = client.get_reviews("owner", "repo", 1)
    assert len(reviews) == 1
    assert reviews[0].user_login == "coderabbitai[bot]"
    assert reviews[0].state == "CHANGES_REQUESTED"
    assert reviews[0].id == "111"


# --- get_review_comments ---

def test_get_review_comments_returns_list(client, mocker):
    item = {"path": "src/main.py", "body": "comment"}
    # gh api --paginate --jq '.[]' outputs one JSON object per line
    _mock_run(mocker, json.dumps(item))
    comments = client.get_review_comments("owner", "repo", 1)
    assert comments[0]["path"] == "src/main.py"


# --- get_pr_diff ---

def test_get_pr_diff_returns_string(client, mocker):
    _mock_run(mocker, "diff --git a/f b/f\n")
    diff = client.get_pr_diff("owner", "repo", 1)
    assert diff.startswith("diff")


# --- post_pr_comment ---

def test_post_pr_comment_calls_gh(client, mocker):
    mock = mocker.patch("review_collector.subprocess.run")
    client.post_pr_comment("owner", "repo", 1, "hello")
    mock.assert_called_once()
    args = mock.call_args[0][0]
    assert "gh" in args
    assert "hello" in args


# --- request_review ---

def test_request_review_coderabbitai_posts_comment(client, mocker):
    """reviewer_bot == 'coderabbitai[bot]' のとき @coderabbitai review コメントを投稿する。"""
    mock = mocker.patch("review_collector.subprocess.run")
    client.request_review("owner", "repo", 1, "coderabbitai[bot]")
    mock.assert_called_once()
    args = mock.call_args[0][0]
    assert "@coderabbitai review" in args


def test_request_review_unknown_bot_does_nothing(client, mocker):
    """未知の reviewer_bot のときは何も実行しない。"""
    mock = mocker.patch("review_collector.subprocess.run")
    client.request_review("owner", "repo", 1, "unknown-bot")
    mock.assert_not_called()
