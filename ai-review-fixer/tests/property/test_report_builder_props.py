"""tests/property/test_report_builder_props.py - Hypothesis プロパティテスト"""

from hypothesis import given, settings
from hypothesis import strategies as st

from report_builder import build_fix_report
from review_collector import Review


def _review(user_login="bot", body="Fix this."):
    return Review("1", user_login, "CHANGES_REQUESTED", body, "2026-01-01T00:00:00Z")


@given(
    attempt=st.integers(min_value=1, max_value=10),
    max_attempts=st.integers(min_value=1, max_value=10),
)
def test_attempt_fraction_always_present(attempt, max_attempts):
    """attempt/max_attempts の表示は常に存在する。"""
    report = build_fix_report(1, attempt, max_attempts, [_review()], [], "abc1234", True)
    assert f"{attempt}/{max_attempts}" in report


@given(commit_hash=st.text(alphabet="0123456789abcdef", min_size=7, max_size=40))
def test_short_hash_is_at_most_7_chars(commit_hash):
    """commit hash の表示は常に 7 文字以下に切り詰められる。"""
    report = build_fix_report(1, 1, 3, [_review()], [], commit_hash, True)
    short = commit_hash[:7]
    assert f"`{short}`" in report
    # 8文字以上の表示はないことを確認
    if len(commit_hash) > 7:
        assert f"`{commit_hash}`" not in report


@given(body=st.text(min_size=0, max_size=300))
@settings(max_examples=50)
def test_report_is_always_a_string(body):
    """どんなレビュー本文でも文字列が返る。"""
    review = _review(body=body)
    result = build_fix_report(1, 1, 3, [review], [], "abc1234", True)
    assert isinstance(result, str)
    assert len(result) > 0


@given(files=st.lists(st.text(min_size=1, max_size=50), max_size=10))
def test_all_changed_files_appear_in_report(files):
    """changed_files に含まれる全ファイルがレポートに現れる。"""
    report = build_fix_report(1, 1, 3, [_review()], files, "abc1234", True)
    for f in files:
        assert f in report


@given(committed=st.booleans())
def test_commit_section_matches_committed_flag(committed):
    """committed=True なら hash が表示、False なら 'No changes committed'。"""
    report = build_fix_report(1, 1, 3, [_review()], [], "abc1234def", committed)
    if committed:
        assert "`abc1234`" in report
    else:
        assert "No changes committed" in report
