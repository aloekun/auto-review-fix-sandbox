"""tests/unit/test_state_manager.py"""

import pytest

from state_manager import StateManager


@pytest.fixture
def sm(tmp_path):
    return StateManager(state_file=tmp_path / "state.json")


def test_initial_fix_attempts_is_zero(sm):
    assert sm.get_fix_attempts(1) == 0


def test_initial_processed_review_ids_is_empty(sm):
    assert sm.get_processed_review_ids(1) == []


def test_record_fix_increments_attempts(sm):
    sm.record_fix(1, ["r1"])
    assert sm.get_fix_attempts(1) == 1


def test_record_fix_returns_new_attempt_count(sm):
    result = sm.record_fix(1, ["r1"])
    assert result == 1
    result2 = sm.record_fix(1, ["r2"])
    assert result2 == 2


def test_record_fix_accumulates_review_ids(sm):
    sm.record_fix(1, ["r1"])
    sm.record_fix(1, ["r2"])
    ids = sm.get_processed_review_ids(1)
    assert "r1" in ids
    assert "r2" in ids


def test_record_fix_deduplicates_review_ids(sm):
    sm.record_fix(1, ["r1"])
    sm.record_fix(1, ["r1"])
    ids = sm.get_processed_review_ids(1)
    assert ids.count("r1") == 1


def test_different_prs_are_independent(sm):
    sm.record_fix(1, ["r1"])
    assert sm.get_fix_attempts(2) == 0
    assert sm.get_processed_review_ids(2) == []


def test_reset_pr_clears_state(sm):
    sm.record_fix(1, ["r1"])
    sm.reset_pr(1)
    assert sm.get_fix_attempts(1) == 0
    assert sm.get_processed_review_ids(1) == []


def test_reset_nonexistent_pr_is_noop(sm):
    sm.reset_pr(99)  # should not raise


def test_state_persists_across_instances(tmp_path):
    sm1 = StateManager(state_file=tmp_path / "state.json")
    sm1.record_fix(1, ["r1"])

    sm2 = StateManager(state_file=tmp_path / "state.json")
    assert sm2.get_fix_attempts(1) == 1
    assert "r1" in sm2.get_processed_review_ids(1)


def test_corrupted_state_file_returns_defaults(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text("not json", encoding="utf-8")
    sm = StateManager(state_file=state_file)
    assert sm.get_fix_attempts(1) == 0
