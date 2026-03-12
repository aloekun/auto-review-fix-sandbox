"""tests/unit/test_claude_runner.py"""

import pytest

from claude_runner import ClaudeRunner


@pytest.fixture
def runner():
    return ClaudeRunner()


def test_run_returns_127_when_claude_not_in_path(runner, mocker, tmp_path):
    mocker.patch("claude_runner.shutil.which", return_value=None)
    result = runner.run("test prompt", tmp_path)
    assert result == 127


def test_run_returns_zero_on_success(runner, mocker, tmp_path):
    mocker.patch("claude_runner.shutil.which", return_value="/usr/bin/claude")

    mock_proc = mocker.MagicMock()
    mock_proc.__enter__ = mocker.MagicMock(return_value=mock_proc)
    mock_proc.__exit__ = mocker.MagicMock(return_value=False)
    mock_proc.stdin = mocker.MagicMock()
    mock_proc.stdout = iter([])
    mock_proc.poll.return_value = 0
    mock_proc.wait.return_value = 0

    mocker.patch("claude_runner.subprocess.Popen", return_value=mock_proc)
    result = runner.run("test prompt", tmp_path)
    assert result == 0


def test_run_returns_nonzero_on_failure(runner, mocker, tmp_path):
    mocker.patch("claude_runner.shutil.which", return_value="/usr/bin/claude")

    mock_proc = mocker.MagicMock()
    mock_proc.__enter__ = mocker.MagicMock(return_value=mock_proc)
    mock_proc.__exit__ = mocker.MagicMock(return_value=False)
    mock_proc.stdin = mocker.MagicMock()
    mock_proc.stdout = iter([])
    mock_proc.poll.return_value = 1
    mock_proc.wait.return_value = 1

    mocker.patch("claude_runner.subprocess.Popen", return_value=mock_proc)
    result = runner.run("test prompt", tmp_path)
    assert result == 1


def test_run_passes_prompt_to_stdin(runner, mocker, tmp_path):
    mocker.patch("claude_runner.shutil.which", return_value="/usr/bin/claude")

    written: list[str] = []

    mock_stdin = mocker.MagicMock()
    mock_stdin.write.side_effect = written.append

    mock_proc = mocker.MagicMock()
    mock_proc.__enter__ = mocker.MagicMock(return_value=mock_proc)
    mock_proc.__exit__ = mocker.MagicMock(return_value=False)
    mock_proc.stdin = mock_stdin
    mock_proc.stdout = iter([])
    mock_proc.poll.return_value = 0
    mock_proc.wait.return_value = 0

    mocker.patch("claude_runner.subprocess.Popen", return_value=mock_proc)
    runner.run("my prompt", tmp_path)

    assert "my prompt" in written
