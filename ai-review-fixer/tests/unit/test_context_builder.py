"""tests/unit/test_context_builder.py"""

from unittest.mock import MagicMock

import pytest

from context_builder import _EXCLUDE_NAMES, ContextBuilder


@pytest.fixture
def cb():
    return ContextBuilder()


# --- extract_changed_files ---

def test_extract_changed_files_basic(cb):
    diff = (
        "diff --git a/src/foo.py b/src/foo.py\n"
        "--- a/src/foo.py\n"
        "+++ b/src/foo.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )
    assert cb.extract_changed_files(diff) == ["src/foo.py"]


def test_extract_changed_files_deduplicates(cb):
    diff = "+++ b/src/foo.py\n+++ b/src/foo.py\n"
    assert cb.extract_changed_files(diff) == ["src/foo.py"]


def test_extract_changed_files_multiple(cb):
    diff = "+++ b/a.py\n+++ b/b.py\n"
    assert cb.extract_changed_files(diff) == ["a.py", "b.py"]


def test_extract_changed_files_empty_diff(cb):
    assert cb.extract_changed_files("") == []


# --- get_file_contents ---

def test_get_file_contents_reads_file(cb, tmp_path):
    (tmp_path / "main.py").write_text("print('hello')\n", encoding="utf-8")
    result = cb.get_file_contents(["main.py"], tmp_path)
    assert result["main.py"] == "print('hello')\n"


def test_get_file_contents_truncates_large_file(cb, tmp_path):
    big_content = "x" * 25_000
    (tmp_path / "big.py").write_text(big_content, encoding="utf-8")
    result = cb.get_file_contents(["big.py"], tmp_path)
    assert "(truncated)" in result["big.py"]
    assert len(result["big.py"]) < 25_000


def test_get_file_contents_skips_missing_files(cb, tmp_path):
    result = cb.get_file_contents(["nonexistent.py"], tmp_path)
    assert "nonexistent.py" not in result


# --- extract_function_names_from_diff ---

def test_extract_function_names_python(cb):
    diff = "+def my_function(x):\n"
    names = cb.extract_function_names_from_diff(diff)
    assert "my_function" in names


def test_extract_function_names_excludes_generic(cb):
    diff = "+def get(x):\n+def main():\n"
    names = cb.extract_function_names_from_diff(diff)
    assert "get" not in names
    assert "main" not in names


def test_extract_function_names_from_hunk_header(cb):
    diff = "@@ -1,3 +1,3 @@ def calculate_total\n"
    names = cb.extract_function_names_from_diff(diff)
    assert "calculate_total" in names


def test_exclude_names_does_not_contain_normal_names():
    assert "calculate_total" not in _EXCLUDE_NAMES
    assert "my_service" not in _EXCLUDE_NAMES


# --- get_call_graph_context ---

def test_get_call_graph_context_empty_when_no_funcs(cb, tmp_path):
    result = cb.get_call_graph_context([], tmp_path)
    assert result == ""


def test_get_call_graph_context_uses_git_grep(tmp_path):
    mock_git = MagicMock()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "src/main.py:5: my_func()\n"
    mock_result.stderr = ""
    mock_git.run.return_value = mock_result

    cb = ContextBuilder(git_client=mock_git)
    result = cb.get_call_graph_context(["my_func"], tmp_path)

    assert "my_func" in result
    assert "src/main.py:5" in result
    mock_git.run.assert_called_once()


def test_get_call_graph_context_handles_git_failure(tmp_path):
    mock_git = MagicMock()
    mock_result = MagicMock()
    mock_result.returncode = 2  # error code
    mock_result.stderr = "fatal: not a git repo"
    mock_git.run.return_value = mock_result

    cb = ContextBuilder(git_client=mock_git)
    result = cb.get_call_graph_context(["my_func"], tmp_path)

    assert "call-graph lookup failed" in result


def test_get_call_graph_context_handles_exception(tmp_path):
    mock_git = MagicMock()
    mock_git.run.side_effect = OSError("git not found")

    cb = ContextBuilder(git_client=mock_git)
    result = cb.get_call_graph_context(["my_func"], tmp_path)

    assert "call-graph lookup failed" in result


# --- get_previous_fix_diff ---

def test_get_previous_fix_diff_returns_none_for_zero_attempt(cb, tmp_path):
    assert cb.get_previous_fix_diff(tmp_path, pr_number=1, previous_attempt=0) is None


def test_get_previous_fix_diff_returns_none_when_file_missing(cb, tmp_path):
    assert cb.get_previous_fix_diff(tmp_path, pr_number=1, previous_attempt=1) is None


def test_get_previous_fix_diff_returns_content(cb, tmp_path):
    patch_dir = tmp_path / "runs" / "pr-1" / "attempt-1"
    patch_dir.mkdir(parents=True)
    (patch_dir / "diff_after.patch").write_text("diff content", encoding="utf-8")

    result = cb.get_previous_fix_diff(tmp_path, pr_number=1, previous_attempt=1)
    assert result == "diff content"
