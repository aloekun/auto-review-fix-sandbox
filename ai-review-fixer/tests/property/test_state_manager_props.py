"""tests/property/test_state_manager_props.py - Hypothesis プロパティテスト"""

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from state_manager import StateManager


def _sm() -> StateManager:
    """一時ファイルを使った StateManager を生成する。"""
    tmp = tempfile.mkdtemp()
    return StateManager(state_file=Path(tmp) / "state.json")


@given(n=st.integers(min_value=1, max_value=20))
@settings(max_examples=30)
def test_record_fix_n_times_yields_n_attempts(n):
    """record_fix を n 回呼ぶと fix_attempts == n になる。"""
    sm = _sm()
    for i in range(n):
        sm.record_fix(1, [str(i)])
    assert sm.get_fix_attempts(1) == n


@given(
    review_ids=st.lists(
        st.text(alphabet="0123456789", min_size=1, max_size=10),
        min_size=1,
        max_size=20,
        unique=True,
    )
)
@settings(max_examples=30)
def test_all_review_ids_are_recorded(review_ids):
    """record_fix で渡した全 review_id が processed_review_ids に含まれる。"""
    sm = _sm()
    sm.record_fix(1, review_ids)
    processed = sm.get_processed_review_ids(1)
    for rid in review_ids:
        assert rid in processed


@given(
    rid=st.text(alphabet="0123456789", min_size=1, max_size=10),
    n=st.integers(min_value=2, max_value=5),
)
@settings(max_examples=20)
def test_duplicate_review_ids_not_stored_twice(rid, n):
    """同じ review_id を複数回 record_fix しても重複して保存されない。"""
    sm = _sm()
    for _ in range(n):
        sm.record_fix(1, [rid])
    processed = sm.get_processed_review_ids(1)
    assert processed.count(rid) == 1


@given(pr=st.integers(min_value=1, max_value=100))
@settings(max_examples=20)
def test_independent_prs_do_not_interfere(pr):
    """あるPRへの記録が他のPRに影響しない。"""
    sm = _sm()
    other_pr = pr + 1
    sm.record_fix(pr, ["r1"])
    assert sm.get_fix_attempts(other_pr) == 0
    assert sm.get_processed_review_ids(other_pr) == []
