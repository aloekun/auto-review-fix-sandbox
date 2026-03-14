"""
orchestrator.py
メイン制御ループ。PRレビューを検知してClaudeに修正させる。

使い方:
  python orchestrator.py          # 一度だけ実行（デーモン用）
  python orchestrator.py --once   # 同上（明示的）
  python orchestrator.py --loop   # 60秒ポーリングのループモード
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

import report_builder
from claude_runner import ClaudeRunner
from context_builder import ContextBuilder
from git_client import GitClient
from interfaces import (
    ClaudeRunnerProtocol,
    GHClientProtocol,
    GitClientProtocol,
    StateManagerProtocol,
)
from prompt_builder import (
    build_patch_proposal_prompt,
    build_patch_verification_prompt,
    build_prompt,
)
from review_collector import GHClient
from run_logger import RunLogger
from state_manager import StateManager

CONFIG_FILE = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


class Orchestrator:
    """PR レビューを検知して Claude Code による自動修正を実行する制御クラス。"""

    def __init__(
        self,
        config: dict,
        gh_client: GHClientProtocol | None = None,
        git_client: GitClientProtocol | None = None,
        claude_runner: ClaudeRunnerProtocol | None = None,
        state_manager: StateManagerProtocol | None = None,
        base_dir: Path | None = None,
    ) -> None:
        self._config = config
        git = git_client or GitClient()
        self._gh = gh_client or GHClient()
        self._git = git
        self._claude = claude_runner or ClaudeRunner()
        self._state = state_manager or StateManager()
        self._context = ContextBuilder(git)
        self._logger = RunLogger(git)
        # runs/ 成果物の格納先。テストから tmp_path を注入できるように分離する。
        self._base_dir: Path = base_dir if base_dir is not None else Path(__file__).parent

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run_once(self) -> None:
        owner: str = self._config["owner"]
        repos_config = self._config.get("repos") or {}
        if not isinstance(repos_config, dict):
            raise TypeError(
                f"config.yaml: 'repos' must be a mapping, "
                f"got {type(repos_config).__name__!r}."
            )
        repos_include: list[str] = repos_config.get("include", [])
        if not isinstance(repos_include, list):
            raise TypeError(
                f"config.yaml: 'repos.include' must be a list, "
                f"got {type(repos_include).__name__!r}."
            )
        max_attempts: int = self._config["daemon"]["max_fix_attempts"]
        reviewer_bots: list[str] = self._config["reviewer_bots"]
        if not isinstance(reviewer_bots, list):
            raise TypeError(
                f"config.yaml: 'reviewer_bots' must be a list, "
                f"got {type(reviewer_bots).__name__!r}."
            )
        base_workspace = (
            Path(__file__).parent / self._config["daemon"]["workspace_dir"]
        ).resolve()
        patch_proposal_mode: bool = self._config["daemon"].get(
            "patch_proposal_mode", False
        )

        # TODO: repos の updated_at フィルタ（更新の古いリポジトリを除外）
        all_repos = self._gh.list_repos(owner)
        repos = [r for r in all_repos if r in repos_include] if repos_include else all_repos

        if not repos:
            print(
                f"[orchestrator] No repos found for owner {owner!r}.", flush=True
            )
            return

        # TODO: parallel processing for multiple repos
        for repo in repos:
            try:
                workspace_dir = (base_workspace / owner / repo).resolve()
                self._ensure_workspace(workspace_dir, owner, repo)

                pr_numbers = self._gh.get_open_prs(owner, repo)
                if not pr_numbers:
                    print(f"[orchestrator] {owner}/{repo}: No open PRs.", flush=True)
                    continue

                for pr_number in pr_numbers:
                    try:
                        if patch_proposal_mode:
                            self._process_pr_patch_mode(
                                pr_number=pr_number,
                                owner=owner,
                                repo=repo,
                                max_attempts=max_attempts,
                                reviewer_bots=reviewer_bots,
                                workspace_dir=workspace_dir,
                            )
                        else:
                            self._process_pr(
                                pr_number=pr_number,
                                owner=owner,
                                repo=repo,
                                max_attempts=max_attempts,
                                reviewer_bots=reviewer_bots,
                                workspace_dir=workspace_dir,
                            )
                    except Exception as exc:
                        print(
                            f"[orchestrator] {owner}/{repo} PR #{pr_number}: "
                            f"unhandled error, skipping: {exc}",
                            file=sys.stderr,
                            flush=True,
                        )
            except Exception as exc:
                print(
                    f"[orchestrator] {owner}/{repo}: repo-level error, skipping: {exc}",
                    file=sys.stderr,
                    flush=True,
                )

    # ------------------------------------------------------------------
    # Workspace management
    # ------------------------------------------------------------------

    def _ensure_workspace(
        self, workspace_dir: Path, owner: str, repo: str
    ) -> None:
        """daemon-workspace が存在しなければ git clone する。"""
        if not workspace_dir.exists():
            workspace_dir.parent.mkdir(parents=True, exist_ok=True)
            repo_url = f"https://github.com/{owner}/{repo}.git"
            print(
                f"[orchestrator] Cloning {repo_url} into {workspace_dir}",
                flush=True,
            )
            self._git.run(
                ["git", "clone", repo_url, str(workspace_dir)],
                check=True,
            )
        else:
            self._git.run(
                ["git", "fetch", "origin"],
                cwd=workspace_dir,
                check=True,
            )

    def _prepare_branch(self, workspace_dir: Path, branch: str, head_sha: str) -> None:
        """指定ブランチをチェックアウトして head_sha にピンする。前回の残留変更を必ず破棄する。

        head_sha を使うことで origin/<branch> が別の tip に進んでいた場合でも
        レビュー時点の正確なコミットからスタートできる。
        """
        self._git.run(
            ["git", "fetch", "origin", branch],
            cwd=workspace_dir,
            check=True,
        )
        self._git.run(
            ["git", "checkout", "-B", branch, f"origin/{branch}"],
            cwd=workspace_dir,
            check=True,
        )
        self._git.run(
            ["git", "reset", "--hard", head_sha],
            cwd=workspace_dir,
            check=True,
        )
        self._git.run(
            ["git", "clean", "-fd"],
            cwd=workspace_dir,
            check=True,
        )

    # ------------------------------------------------------------------
    # Phase 6.1 - 通常モード（強化版コンテキスト付き）
    # ------------------------------------------------------------------

    def _process_pr(
        self,
        pr_number: int,
        owner: str,
        repo: str,
        max_attempts: int,
        reviewer_bots: list[str],
        workspace_dir: Path,
    ) -> None:
        fix_attempts = self._state.get_fix_attempts(owner, repo, pr_number)
        processed_ids = self._state.get_processed_review_ids(owner, repo, pr_number)

        if fix_attempts >= max_attempts:
            print(
                f"[orchestrator] PR #{pr_number}: "
                f"max attempts ({max_attempts}) reached, skip.",
                flush=True,
            )
            return

        reviews = self._gh.get_reviews(owner, repo, pr_number)
        new_reviews = [
            r
            for r in reviews
            if r.user_login in reviewer_bots
            and r.state == "CHANGES_REQUESTED"
            and r.id not in processed_ids
        ]

        if not new_reviews:
            print(
                f"[orchestrator] PR #{pr_number}: "
                f"no new CHANGES_REQUESTED reviews from {reviewer_bots}, skip.",
                flush=True,
            )
            return

        print(
            f"[orchestrator] PR #{pr_number}: {len(new_reviews)} new review(s) found.",
            flush=True,
        )

        pr_info = self._gh.get_pr_info(owner, repo, pr_number)
        diff = self._gh.get_pr_diff(owner, repo, pr_number)
        all_inline_comments = self._gh.get_review_comments(owner, repo, pr_number)

        new_review_ids = {str(r.id) for r in new_reviews}
        new_inline_comments = [
            c
            for c in all_inline_comments
            if str(c.get("pull_request_review_id", "")) in new_review_ids
        ]

        # ブランチを最新化してからファイル内容を読み込む（6.1.1 / 6.1.2）
        self._prepare_branch(workspace_dir, pr_info.head_ref, pr_info.head_sha)

        base_dir = self._base_dir
        attempt_number = fix_attempts + 1

        # 追加コンテキストを収集する
        changed_files = self._context.extract_changed_files(diff)
        file_contents = self._context.get_file_contents(changed_files, workspace_dir)
        func_names = self._context.extract_function_names_from_diff(diff)
        call_graph_context = self._context.get_call_graph_context(func_names, workspace_dir)
        previous_fix_diff = self._context.get_previous_fix_diff(
            base_dir, pr_number, fix_attempts, owner=owner, repo=repo
        )

        print(
            f"[orchestrator] PR #{pr_number}: context gathered - "
            f"{len(file_contents)} file(s), {len(func_names)} function(s), "
            f"previous_fix={'yes' if previous_fix_diff else 'no'}",
            flush=True,
        )

        prompt = build_prompt(
            pr_number=pr_number,
            pr_title=pr_info.title,
            branch=pr_info.head_ref,
            diff=diff,
            reviews=new_reviews,
            inline_comments=new_inline_comments,
            fix_attempt=attempt_number,
            reviewer_bots=reviewer_bots,
            file_contents=file_contents,
            call_graph_context=call_graph_context,
            previous_fix_diff=previous_fix_diff,
        )

        returncode = self._claude.run(prompt, workspace_dir)

        if returncode != 0:
            # Count the failed attempt so max_fix_attempts guard can fire.
            self._state.record_fix(owner, repo, pr_number, [r.id for r in new_reviews])
            print(
                f"[orchestrator] PR #{pr_number}: "
                "Claude exited with non-zero code; attempt recorded.",
                file=sys.stderr,
                flush=True,
            )
            return

        self._finalize_run(
            pr_number=pr_number,
            owner=owner,
            repo=repo,
            attempt_number=attempt_number,
            max_attempts=max_attempts,
            reviewer_bots=reviewer_bots,
            prompt=prompt,
            new_reviews=new_reviews,
            new_inline_comments=new_inline_comments,
            diff=diff,
            workspace_dir=workspace_dir,
            original_head_sha=pr_info.head_sha,
            base_dir=base_dir,
        )

    # ------------------------------------------------------------------
    # Phase 6.2 - Patch Proposal Mode（2段階実行）
    # ------------------------------------------------------------------

    def _process_pr_patch_mode(
        self,
        pr_number: int,
        owner: str,
        repo: str,
        max_attempts: int,
        reviewer_bots: list[str],
        workspace_dir: Path,
    ) -> None:
        """Run 1 でパッチ生成のみ、Run 2 でパッチ検証 → commit を行う2段階モード。"""
        fix_attempts = self._state.get_fix_attempts(owner, repo, pr_number)
        processed_ids = self._state.get_processed_review_ids(owner, repo, pr_number)

        if fix_attempts >= max_attempts:
            print(
                f"[orchestrator] PR #{pr_number}: "
                f"max attempts ({max_attempts}) reached, skip.",
                flush=True,
            )
            return

        reviews = self._gh.get_reviews(owner, repo, pr_number)
        new_reviews = [
            r
            for r in reviews
            if r.user_login in reviewer_bots
            and r.state == "CHANGES_REQUESTED"
            and r.id not in processed_ids
        ]

        if not new_reviews:
            print(
                f"[orchestrator] PR #{pr_number}: "
                f"no new CHANGES_REQUESTED reviews from {reviewer_bots}, skip.",
                flush=True,
            )
            return

        print(
            f"[orchestrator] PR #{pr_number}: "
            f"{len(new_reviews)} new review(s) found (patch mode).",
            flush=True,
        )

        pr_info = self._gh.get_pr_info(owner, repo, pr_number)
        diff = self._gh.get_pr_diff(owner, repo, pr_number)
        all_inline_comments = self._gh.get_review_comments(owner, repo, pr_number)

        new_review_ids = {str(r.id) for r in new_reviews}
        new_inline_comments = [
            c
            for c in all_inline_comments
            if str(c.get("pull_request_review_id", "")) in new_review_ids
        ]

        # ブランチを最新化してからコンテキストを収集（Run 1 の前に1回だけ）
        self._prepare_branch(workspace_dir, pr_info.head_ref, pr_info.head_sha)

        base_dir = self._base_dir
        attempt_number = fix_attempts + 1

        changed_files = self._context.extract_changed_files(diff)
        file_contents = self._context.get_file_contents(changed_files, workspace_dir)
        func_names = self._context.extract_function_names_from_diff(diff)
        call_graph_context = self._context.get_call_graph_context(func_names, workspace_dir)
        previous_fix_diff = self._context.get_previous_fix_diff(
            base_dir, pr_number, fix_attempts, owner=owner, repo=repo
        )

        print(
            f"[orchestrator] PR #{pr_number}: context gathered - "
            f"{len(file_contents)} file(s), {len(func_names)} function(s), "
            f"previous_fix={'yes' if previous_fix_diff else 'no'}",
            flush=True,
        )

        # Run 1: パッチ生成（commit しない）
        print(
            f"[orchestrator] PR #{pr_number}: starting Run 1 (patch proposal)...",
            flush=True,
        )
        proposal_prompt = build_patch_proposal_prompt(
            pr_number=pr_number,
            pr_title=pr_info.title,
            branch=pr_info.head_ref,
            diff=diff,
            reviews=new_reviews,
            inline_comments=new_inline_comments,
            fix_attempt=attempt_number,
            reviewer_bots=reviewer_bots,
            file_contents=file_contents,
            call_graph_context=call_graph_context,
            previous_fix_diff=previous_fix_diff,
        )

        returncode1 = self._claude.run(proposal_prompt, workspace_dir)
        if returncode1 != 0:
            self._state.record_fix(owner, repo, pr_number, [r.id for r in new_reviews])
            print(
                f"[orchestrator] PR #{pr_number}: "
                f"Run 1 (patch proposal) failed with code {returncode1}; attempt recorded.",
                file=sys.stderr,
                flush=True,
            )
            return

        print(
            f"[orchestrator] PR #{pr_number}: "
            "Run 1 complete. Starting Run 2 (verification)...",
            flush=True,
        )

        # Run 2: 検証 → commit（prepare_branch は呼ばない: Run 1 の変更を保持する）
        verify_prompt = build_patch_verification_prompt(
            pr_number=pr_number,
            branch=pr_info.head_ref,
            fix_attempt=attempt_number,
            reviewer_bots=reviewer_bots,
            reviews=new_reviews,
            inline_comments=new_inline_comments,
        )

        returncode2 = self._claude.run(verify_prompt, workspace_dir)
        if returncode2 != 0:
            self._state.record_fix(owner, repo, pr_number, [r.id for r in new_reviews])
            print(
                f"[orchestrator] PR #{pr_number}: "
                f"Run 2 (verification) failed with code {returncode2}; attempt recorded.",
                file=sys.stderr,
                flush=True,
            )
            return

        # 両 Run 完了後にアーティファクトを保存し、PR にレポートを投稿する
        # Run 1 の proposal_prompt を代表プロンプトとして保存する
        self._finalize_run(
            pr_number=pr_number,
            owner=owner,
            repo=repo,
            attempt_number=attempt_number,
            max_attempts=max_attempts,
            reviewer_bots=reviewer_bots,
            prompt=proposal_prompt,
            new_reviews=new_reviews,
            new_inline_comments=new_inline_comments,
            diff=diff,
            workspace_dir=workspace_dir,
            original_head_sha=pr_info.head_sha,
            base_dir=base_dir,
        )

    # ------------------------------------------------------------------
    # 共通フィナライズ（アーティファクト保存 + PR コメント投稿）
    # ------------------------------------------------------------------

    def _finalize_run(
        self,
        pr_number: int,
        owner: str,
        repo: str,
        attempt_number: int,
        max_attempts: int,
        reviewer_bots: list[str],
        prompt: str,
        new_reviews: list,
        new_inline_comments: list,
        diff: str,
        workspace_dir: Path,
        original_head_sha: str,
        base_dir: Path,
    ) -> None:
        run_data = self._logger.save_run_artifacts(
            base_dir=base_dir,
            pr_number=pr_number,
            attempt=attempt_number,
            prompt=prompt,
            reviews=new_reviews,
            inline_comments=new_inline_comments,
            diff_before=diff,
            workspace_dir=workspace_dir,
            original_head_sha=original_head_sha,
            owner=owner,
            repo=repo,
        )

        # record_fix を先に実行する: save_structured_log / post_pr_comment が
        # 失敗しても state は確実に更新され、無限リトライを防ぐ。
        new_attempt = self._state.record_fix(
            owner, repo, pr_number, [r.id for r in new_reviews]
        )

        try:
            self._logger.save_structured_log(
                base_dir,
                {
                    "pr": pr_number,
                    "attempt": attempt_number,
                    "reviews_processed": len(new_reviews),
                    "files_changed": run_data["files_changed"],
                    "commit": run_data["commit_hash"],
                    "committed": run_data["committed"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                owner=owner,
                repo=repo,
            )
        except Exception as exc:
            print(
                f"[orchestrator] PR #{pr_number}: structured log failed (non-fatal): {exc}",
                file=sys.stderr,
                flush=True,
            )

        if not run_data["committed"]:
            # Still record the attempt so max_fix_attempts can eventually fire.
            # Without this, no-op runs would retry indefinitely.
            print(
                f"[orchestrator] PR #{pr_number}: no commit created; "
                f"attempt {new_attempt} recorded to prevent infinite retry.",
                flush=True,
            )
            self._gh.post_pr_comment(
                owner,
                repo,
                pr_number,
                "Auto-fix run completed without creating a commit. "
                "The attempt has been counted toward the retry limit.",
            )
            if new_attempt >= max_attempts:
                self._gh.post_pr_comment(
                    owner,
                    repo,
                    pr_number,
                    f"Auto-fix reached the maximum number of attempts ({max_attempts}). "
                    "Please review manually.",
                )
                print(
                    f"[orchestrator] PR #{pr_number}: max attempts reached, posted comment.",
                    flush=True,
                )
            return
        print(
            f"[orchestrator] PR #{pr_number}: fix attempt {new_attempt} recorded.",
            flush=True,
        )

        report_body = report_builder.build_fix_report(
            pr_number=pr_number,
            attempt=attempt_number,
            max_attempts=max_attempts,
            reviews=new_reviews,
            files_changed=run_data["files_changed"],
            commit_hash=run_data["commit_hash"],
            committed=run_data["committed"],
        )
        self._gh.post_pr_comment(owner, repo, pr_number, report_body)
        print(
            f"[orchestrator] PR #{pr_number}: posted fix report comment.", flush=True
        )

        for bot in reviewer_bots:
            try:
                self._gh.request_review(owner, repo, pr_number, bot)
                print(
                    f"[orchestrator] PR #{pr_number}: requested re-review from {bot}.",
                    flush=True,
                )
            except Exception as exc:
                print(
                    f"[orchestrator] PR #{pr_number}: "
                    f"request_review({bot}) failed (non-fatal): {exc}",
                    file=sys.stderr,
                    flush=True,
                )

        if new_attempt >= max_attempts:
            self._gh.post_pr_comment(
                owner,
                repo,
                pr_number,
                f"Auto-fix reached the maximum number of attempts ({max_attempts}). "
                "Please review manually.",
            )
            print(
                f"[orchestrator] PR #{pr_number}: max attempts reached, posted comment.",
                flush=True,
            )


if __name__ == "__main__":
    import time
    import traceback

    loop = "--loop" in sys.argv
    cfg = load_config()
    poll_interval = cfg["daemon"]["poll_interval_seconds"]

    orchestrator = Orchestrator(cfg)

    if loop:
        print("[daemon] Starting loop mode (Ctrl+C to stop)...", flush=True)
        while True:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[daemon] {ts} Running orchestrator...", flush=True)
            try:
                orchestrator.run_once()
            except Exception:
                print(
                    "[daemon] Error during orchestrator run",
                    file=sys.stderr,
                    flush=True,
                )
                traceback.print_exc()
            print(f"[daemon] Sleeping {poll_interval} seconds...", flush=True)
            time.sleep(poll_interval)
    else:
        orchestrator.run_once()
