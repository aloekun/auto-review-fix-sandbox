"""tests/property/test_prompt_builder_props.py - Hypothesis プロパティテスト"""

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from prompt_builder import build_prompt
from review_collector import Review


def _review(body="Fix this."):
    return Review("1", "coderabbitai[bot]", "CHANGES_REQUESTED", body, "2026-01-01T00:00:00Z")


def _build(**overrides):
    kwargs = {
        "pr_number": 1,
        "pr_title": "Test PR",
        "branch": "feature/test",
        "diff": "",
        "reviews": [_review()],
        "inline_comments": [],
        "fix_attempt": 1,
        "reviewer_bots": ["coderabbitai[bot]"],
        "file_contents": {},
        "call_graph_context": "",
        "previous_fix_diff": None,
    }
    kwargs.update(overrides)
    return build_prompt(**kwargs)


@given(pr_number=st.integers(min_value=1, max_value=9999))
def test_pr_number_always_in_prompt(pr_number):
    """PR 番号は常にプロンプトに含まれる。"""
    prompt = _build(pr_number=pr_number)
    assert str(pr_number) in prompt


@given(branch=st.text(alphabet="abcdefghijklmnopqrstuvwxyz-/", min_size=1, max_size=30))
@settings(max_examples=30)
def test_branch_name_always_in_prompt(branch):
    """ブランチ名は常にプロンプトに含まれる。"""
    prompt = _build(branch=branch)
    assert branch in prompt


def test_untrusted_data_markers_always_present():
    """UNTRUSTED DATA のセパレータが必ず存在する。"""
    prompt = _build()
    assert "--- BEGIN UNTRUSTED DATA ---" in prompt
    assert "--- END UNTRUSTED DATA ---" in prompt


@given(body=st.text(min_size=1, max_size=200))
@settings(max_examples=30)
def test_review_body_in_prompt(body):
    """レビュー本文は常にプロンプトに含まれる。"""
    # prompt_builder が body.strip() するため、strip後に変わる文字列はスキップ
    assume(body == body.strip())
    prompt = _build(reviews=[_review(body=body)])
    assert body in prompt


@given(
    reviews=st.lists(
        st.builds(
            Review,
            id=st.text(alphabet="0123456789", min_size=1, max_size=5),
            user_login=st.just("coderabbitai[bot]"),
            state=st.just("CHANGES_REQUESTED"),
            body=st.text(min_size=1, max_size=50),
            submitted_at=st.just("2026-01-01T00:00:00Z"),
        ),
        min_size=1,
        max_size=5,
    )
)
@settings(max_examples=20)
def test_prompt_is_always_nonempty_string(reviews):
    """どんなレビューリストでも非空文字列が返る。"""
    prompt = _build(reviews=reviews)
    assert isinstance(prompt, str)
    assert len(prompt) > 0


@given(
    file_contents=st.dictionaries(
        keys=st.text(alphabet="abcdefghijklmnopqrstuvwxyz/.", min_size=3, max_size=20),
        values=st.text(min_size=0, max_size=100),
        max_size=3,
    )
)
@settings(max_examples=20)
def test_file_contents_grow_prompt(file_contents):
    """file_contents があるプロンプトは空の場合より長い（または同等）。"""
    prompt_with = _build(file_contents=file_contents)
    prompt_without = _build(file_contents={})
    if file_contents:
        assert len(prompt_with) >= len(prompt_without)
