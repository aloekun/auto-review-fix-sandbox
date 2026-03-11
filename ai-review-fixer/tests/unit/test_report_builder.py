"""tests/unit/test_report_builder.py"""

import pytest

from report_builder import build_fix_report
from review_collector import Review


@pytest.fixture
def sample_review():
    return Review(
        id="123",
        user_login="coderabbitai[bot]",
        state="CHANGES_REQUESTED",
        body="Add type hints.",
        submitted_at="2026-03-11T00:00:00Z",
    )


def test_report_contains_header(sample_review):
    report = build_fix_report(1, 1, 3, [sample_review], ["src/main.py"], "abc1234567", True)
    assert "## AI Auto Fix Report" in report


def test_report_shows_attempt_fraction(sample_review):
    report = build_fix_report(1, 2, 3, [sample_review], [], "abc1234567", True)
    assert "2/3" in report


def test_report_shows_short_commit_hash_when_committed(sample_review):
    report = build_fix_report(1, 1, 3, [sample_review], [], "abc1234567890", True)
    assert "`abc1234`" in report


def test_report_shows_no_changes_when_not_committed(sample_review):
    report = build_fix_report(1, 1, 3, [sample_review], [], "abc1234567890", False)
    assert "No changes committed" in report
    assert "`abc1234`" not in report


def test_report_lists_changed_files(sample_review):
    report = build_fix_report(1, 1, 3, [sample_review], ["src/a.py", "src/b.py"], "abc1234", True)
    assert "src/a.py" in report
    assert "src/b.py" in report


def test_report_shows_review_user(sample_review):
    report = build_fix_report(1, 1, 3, [sample_review], [], "abc1234", True)
    assert "coderabbitai[bot]" in report


def test_report_includes_review_body_preview(sample_review):
    report = build_fix_report(1, 1, 3, [sample_review], [], "abc1234", True)
    assert "Add type hints." in report


def test_report_truncates_long_review_body():
    long_body = "x" * 200
    review = Review("1", "bot", "CHANGES_REQUESTED", long_body, "2026-01-01")
    report = build_fix_report(1, 1, 3, [review], [], "abc1234", True)
    # Body should be truncated: full 200-char body must not appear verbatim
    assert long_body not in report
    # A prefix of the body should appear followed by ellipsis
    assert "x" * 10 in report and "..." in report


def test_report_handles_empty_files_when_committed(sample_review):
    report = build_fix_report(1, 1, 3, [sample_review], [], "abc1234", True)
    assert "no files listed" in report


def test_report_hash_truncated_to_7_chars(sample_review):
    full_hash = "a" * 40
    report = build_fix_report(1, 1, 3, [sample_review], [], full_hash, True)
    assert f"`{'a' * 7}`" in report
    assert f"`{'a' * 40}`" not in report


def test_report_contains_footer(sample_review):
    report = build_fix_report(1, 1, 3, [sample_review], [], "abc1234", True)
    assert "auto-review-fix-vc" in report
