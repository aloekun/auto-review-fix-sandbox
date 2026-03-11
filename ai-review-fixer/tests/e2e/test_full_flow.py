"""
tests/e2e/test_full_flow.py
E2E テスト: 実際の GitHub リポジトリと Claude Code CLI を使ったフルフロー検証。

【事前準備 (ユーザー作業)】
1. テスト用 GitHub リポジトリを作成:
   gh repo create <owner>/auto-review-fix-e2e --private

2. テストリポジトリに CodeRabbit をインストールする。

3. 環境変数を設定 (.env.e2e など、gitignore 済み):
   E2E_GITHUB_REPO=<owner>/auto-review-fix-e2e
   E2E_GITHUB_TOKEN=<repo scope を持つ personal access token>

4. リポジトリに main ブランチと 1 件以上のファイルがあることを確認する。

【実行方法】
   E2E_GITHUB_REPO=owner/repo pytest tests/e2e/ -v -m e2e
"""


import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.e2e
def test_full_flow_placeholder(e2e_repo):
    """
    E2E テストのプレースホルダー。

    TODO: ユーザーが E2E 用 GitHub リポジトリを準備したら以下を実装する。

    1. テスト用 PR をプログラムで作成する (gh pr create)
    2. FakeCodeRabbit 相当のレビューコメントを gh API で投稿する
    3. Orchestrator を実際の GHClient + ClaudeRunner で起動する
    4. Claude が自動修正コミットを作成したことを検証する
    5. PR コメントに "AI Auto Fix Report" が含まれることを検証する
    6. テスト用 PR をクローズして後片付けをする
    """
    assert e2e_repo, "E2E_GITHUB_REPO must be set"
    pytest.skip(
        "E2E test not yet implemented. "
        f"Target repo: {e2e_repo}. "
        "Implement after the test GitHub repository is prepared."
    )
