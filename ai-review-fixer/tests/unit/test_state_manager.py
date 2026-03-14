"""tests/unit/test_state_manager.py"""

import pytest

from state_manager import StateManager


@pytest.fixture
def sm(tmp_path):
    return StateManager(state_file=tmp_path / "state.json")


# --- owner/repo/pr_number API ---

def test_initial_fix_attempts_is_zero(sm):
    assert sm.get_fix_attempts("owner", "repo", 1) == 0


def test_initial_processed_review_ids_is_empty(sm):
    assert sm.get_processed_review_ids("owner", "repo", 1) == []


def test_record_fix_increments_attempts(sm):
    sm.record_fix("owner", "repo", 1, ["r1"])
    assert sm.get_fix_attempts("owner", "repo", 1) == 1


def test_record_fix_returns_new_attempt_count(sm):
    result = sm.record_fix("owner", "repo", 1, ["r1"])
    assert result == 1
    result2 = sm.record_fix("owner", "repo", 1, ["r2"])
    assert result2 == 2


def test_record_fix_accumulates_review_ids(sm):
    sm.record_fix("owner", "repo", 1, ["r1"])
    sm.record_fix("owner", "repo", 1, ["r2"])
    ids = sm.get_processed_review_ids("owner", "repo", 1)
    assert "r1" in ids
    assert "r2" in ids


def test_record_fix_deduplicates_review_ids(sm):
    sm.record_fix("owner", "repo", 1, ["r1"])
    sm.record_fix("owner", "repo", 1, ["r1"])
    ids = sm.get_processed_review_ids("owner", "repo", 1)
    assert ids.count("r1") == 1


def test_different_prs_are_independent(sm):
    sm.record_fix("owner", "repo", 1, ["r1"])
    assert sm.get_fix_attempts("owner", "repo", 2) == 0
    assert sm.get_processed_review_ids("owner", "repo", 2) == []


def test_different_repos_are_independent(sm):
    """同じ PR 番号でもリポジトリが異なれば独立している。"""
    sm.record_fix("owner", "repo-a", 1, ["r1"])
    assert sm.get_fix_attempts("owner", "repo-b", 1) == 0
    assert sm.get_processed_review_ids("owner", "repo-b", 1) == []


def test_different_owners_are_independent(sm):
    """同じ repo/PR でもオーナーが異なれば独立している。"""
    sm.record_fix("owner-a", "repo", 1, ["r1"])
    assert sm.get_fix_attempts("owner-b", "repo", 1) == 0


def test_reset_pr_clears_state(sm):
    sm.record_fix("owner", "repo", 1, ["r1"])
    sm.reset_pr("owner", "repo", 1)
    assert sm.get_fix_attempts("owner", "repo", 1) == 0
    assert sm.get_processed_review_ids("owner", "repo", 1) == []


def test_reset_nonexistent_pr_is_noop(sm):
    sm.reset_pr("owner", "repo", 99)  # should not raise


def test_state_persists_across_instances(tmp_path):
    sm1 = StateManager(state_file=tmp_path / "state.json")
    sm1.record_fix("owner", "repo", 1, ["r1"])

    sm2 = StateManager(state_file=tmp_path / "state.json")
    assert sm2.get_fix_attempts("owner", "repo", 1) == 1
    assert "r1" in sm2.get_processed_review_ids("owner", "repo", 1)


def test_corrupted_state_file_returns_defaults(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("not json", encoding="utf-8")
    sm = StateManager(state_file=state_file)
    assert sm.get_fix_attempts("owner", "repo", 1) == 0


@pytest.mark.parametrize("content", ["[]", '"string"', "42", "null"])
def test_non_object_json_returns_defaults(tmp_path, content):
    """state.json が非オブジェクト型 JSON のとき例外を発生させずデフォルト値を返す。"""
    state_file = tmp_path / "state.json"
    state_file.write_text(content, encoding="utf-8")
    sm = StateManager(state_file=state_file)
    assert sm.get_fix_attempts("owner", "repo", 1) == 0
    assert sm.get_processed_review_ids("owner", "repo", 1) == []


# --- key format ---

def test_key_uses_owner_repo_pr_format(tmp_path):
    """state.json のキー形式が {owner}/{repo}/pr_{N} になっている。"""
    import json

    sm = StateManager(state_file=tmp_path / "state.json")
    sm.record_fix("my-org", "my-repo", 42, ["r1"])

    state = json.loads((tmp_path / "state.json").read_text())
    assert "my-org/my-repo/pr_42" in state


# --- legacy key detection ---

def test_legacy_key_triggers_warning(tmp_path, capsys):
    """旧形式のキー（/ を含まない）が存在するとき stderr に警告ログを出力する。"""
    import json

    state_file = tmp_path / "state.json"
    # 旧形式でファイルを作成
    state_file.write_text(
        json.dumps({"pr_1": {"fix_attempts": 1, "processed_review_ids": []}})
    )

    sm = StateManager(state_file=state_file)
    sm.get_fix_attempts("owner", "repo", 1)

    captured = capsys.readouterr()
    assert "legacy" in captured.err.lower()
