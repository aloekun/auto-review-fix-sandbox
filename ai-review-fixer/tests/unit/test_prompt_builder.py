"""tests/unit/test_prompt_builder.py"""

import pytest

from prompt_builder import (
    build_patch_proposal_prompt,
    build_patch_verification_prompt,
    build_prompt,
)
from review_collector import Review


@pytest.fixture
def base_review():
    return Review(
        id="1",
        user_login="coderabbitai[bot]",
        state="CHANGES_REQUESTED",
        body="Add type hints.",
        submitted_at="2026-03-11T00:00:00Z",
    )


@pytest.fixture
def base_kwargs(base_review):
    return {
        "pr_number": 42,
        "pr_title": "Test PR",
        "branch": "feature/test",
        "diff": "diff --git a/src/main.py b/src/main.py\n+++ b/src/main.py\n",
        "reviews": [base_review],
        "inline_comments": [],
        "fix_attempt": 1,
        "reviewer_bot": "coderabbitai[bot]",
        "file_contents": {},
        "call_graph_context": "",
        "previous_fix_diff": None,
    }


# --- build_prompt ---

def test_build_prompt_contains_pr_number(base_kwargs):
    prompt = build_prompt(**base_kwargs)
    assert "42" in prompt


def test_build_prompt_contains_branch(base_kwargs):
    prompt = build_prompt(**base_kwargs)
    assert "feature/test" in prompt


def test_build_prompt_contains_untrusted_data_markers(base_kwargs):
    prompt = build_prompt(**base_kwargs)
    assert "--- BEGIN UNTRUSTED DATA ---" in prompt
    assert "--- END UNTRUSTED DATA ---" in prompt


def test_build_prompt_includes_review_body(base_kwargs):
    prompt = build_prompt(**base_kwargs)
    assert "Add type hints." in prompt


def test_build_prompt_includes_file_contents_when_provided(base_kwargs):
    base_kwargs["file_contents"] = {"src/main.py": "def foo(): pass\n"}
    prompt = build_prompt(**base_kwargs)
    assert "def foo(): pass" in prompt


def test_build_prompt_includes_call_graph_when_provided(base_kwargs):
    base_kwargs["call_graph_context"] = "#### Usages of `foo`\nsrc/main.py:1: foo()"
    prompt = build_prompt(**base_kwargs)
    assert "Usages of `foo`" in prompt


def test_build_prompt_includes_previous_fix_when_provided(base_kwargs):
    base_kwargs["previous_fix_diff"] = "diff --git old/new changes"
    prompt = build_prompt(**base_kwargs)
    assert "previous fix" in prompt.lower() or "diff --git old/new changes" in prompt


def test_build_prompt_excludes_file_section_when_empty(base_kwargs):
    prompt = build_prompt(**base_kwargs)
    # file_contents が空なのでファイルセクションは簡略化されているはず
    assert "def foo(): pass" not in prompt


def test_build_prompt_contains_commit_instruction(base_kwargs):
    prompt = build_prompt(**base_kwargs)
    assert "commit" in prompt.lower()


# --- build_patch_proposal_prompt ---

def test_patch_proposal_prompt_contains_pr_number(base_kwargs):
    prompt = build_patch_proposal_prompt(**base_kwargs)
    assert "42" in prompt


def test_patch_proposal_prompt_mentions_no_commit(base_kwargs):
    prompt = build_patch_proposal_prompt(**base_kwargs)
    # 明示的に「do not commit」または「do NOT commit」と指示されているはず
    assert "do not commit" in prompt.lower() or "do NOT commit" in prompt


# --- build_patch_verification_prompt ---

def test_patch_verification_prompt_contains_pr_number(base_review):
    prompt = build_patch_verification_prompt(
        pr_number=42,
        branch="feature/test",
        fix_attempt=1,
        reviewer_bot="coderabbitai[bot]",
        reviews=[base_review],
        inline_comments=[],
    )
    assert "42" in prompt


def test_patch_verification_prompt_mentions_commit(base_review):
    prompt = build_patch_verification_prompt(
        pr_number=42,
        branch="feature/test",
        fix_attempt=1,
        reviewer_bot="coderabbitai[bot]",
        reviews=[base_review],
        inline_comments=[],
    )
    assert "commit" in prompt.lower()
