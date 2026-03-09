"""
orchestrator.py
メイン制御ループ。PRレビューを検知してClaudeに修正させる。

使い方:
  python orchestrator.py          # 一度だけ実行（デーモン用）
  python orchestrator.py --once   # 同上（明示的）
  python orchestrator.py --loop   # 60秒ポーリングのループモード
"""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

import report_builder
import run_logger
import state_manager
from claude_runner import run_claude
from context_builder import (
    extract_changed_files,
    extract_function_names_from_diff,
    get_call_graph_context,
    get_file_contents,
    get_previous_fix_diff,
)
from prompt_builder import (
    build_patch_proposal_prompt,
    build_patch_verification_prompt,
    build_prompt,
)
from review_collector import (
    get_open_prs,
    get_pr_diff,
    get_pr_info,
    get_review_comments,
    get_reviews,
    post_pr_comment,
)

CONFIG_FILE = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_workspace(workspace_dir: Path, owner: str, repo: str) -> None:
    """daemon-workspace が存在しなければ git clone する。"""
    if not workspace_dir.exists():
        repo_url = f"https://github.com/{owner}/{repo}.git"
        print(f"[orchestrator] Cloning {repo_url} into {workspace_dir}", flush=True)
        subprocess.run(
            ["git", "clone", repo_url, str(workspace_dir)],
            check=True
        )
    else:
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=workspace_dir, check=True
        )


def prepare_branch(workspace_dir: Path, branch: str) -> None:
    """指定ブランチをチェックアウトして最新化する。前回の残留変更を必ず破棄する。"""
    subprocess.run(
        ["git", "fetch", "origin", branch],
        cwd=workspace_dir, check=True
    )
    subprocess.run(
        ["git", "checkout", "-B", branch, f"origin/{branch}"],
        cwd=workspace_dir, check=True
    )
    subprocess.run(
        ["git", "reset", "--hard", f"origin/{branch}"],
        cwd=workspace_dir, check=True
    )
    subprocess.run(
        ["git", "clean", "-fd"],
        cwd=workspace_dir, check=True
    )


def run_once(config: dict) -> None:
    owner = config["repo"]["owner"]
    repo = config["repo"]["name"]
    max_attempts = config["daemon"]["max_fix_attempts"]
    reviewer_bot = config["reviewer_bot"]
    workspace_dir = (Path(__file__).parent / config["daemon"]["workspace_dir"]).resolve()
    patch_proposal_mode = config["daemon"].get("patch_proposal_mode", False)

    ensure_workspace(workspace_dir, owner, repo)

    pr_numbers = get_open_prs(owner, repo)
    if not pr_numbers:
        print("[orchestrator] No open PRs.", flush=True)
        return

    for pr_number in pr_numbers:
        if patch_proposal_mode:
            _process_pr_patch_mode(
                pr_number=pr_number,
                owner=owner,
                repo=repo,
                max_attempts=max_attempts,
                reviewer_bot=reviewer_bot,
                workspace_dir=workspace_dir,
            )
        else:
            _process_pr(
                pr_number=pr_number,
                owner=owner,
                repo=repo,
                max_attempts=max_attempts,
                reviewer_bot=reviewer_bot,
                workspace_dir=workspace_dir,
            )


# ---------------------------------------------------------------------------
# Phase 6.1 - 通常モード（強化版コンテキスト付き）
# ---------------------------------------------------------------------------

def _process_pr(
    pr_number: int,
    owner: str,
    repo: str,
    max_attempts: int,
    reviewer_bot: str,
    workspace_dir: Path,
) -> None:
    fix_attempts = state_manager.get_fix_attempts(pr_number)
    processed_ids = state_manager.get_processed_review_ids(pr_number)

    if fix_attempts >= max_attempts:
        print(f"[orchestrator] PR #{pr_number}: max attempts ({max_attempts}) reached, skip.", flush=True)
        return

    reviews = get_reviews(owner, repo, pr_number)
    new_reviews = [
        r for r in reviews
        if r.user_login == reviewer_bot and
        r.state == "CHANGES_REQUESTED" and
        r.id not in processed_ids
    ]

    if not new_reviews:
        print(f"[orchestrator] PR #{pr_number}: no new CHANGES_REQUESTED reviews from {reviewer_bot}, skip.", flush=True)
        return

    print(f"[orchestrator] PR #{pr_number}: {len(new_reviews)} new review(s) found.", flush=True)

    pr_info = get_pr_info(owner, repo, pr_number)
    diff = get_pr_diff(owner, repo, pr_number)
    all_inline_comments = get_review_comments(owner, repo, pr_number)

    new_review_ids = {str(r.id) for r in new_reviews}
    new_inline_comments = [
        c for c in all_inline_comments
        if str(c.get("pull_request_review_id", "")) in new_review_ids
    ]

    # ブランチを最新化してからファイル内容を読み込む（6.1.1 / 6.1.2）
    prepare_branch(workspace_dir, pr_info.head_ref)

    base_dir = Path(__file__).parent
    attempt_number = fix_attempts + 1

    # 追加コンテキストを収集する
    changed_files = extract_changed_files(diff)
    file_contents = get_file_contents(changed_files, workspace_dir)
    func_names = extract_function_names_from_diff(diff)
    call_graph_context = get_call_graph_context(func_names, workspace_dir)
    previous_fix_diff = get_previous_fix_diff(base_dir, pr_number, fix_attempts)

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
        reviewer_bot=reviewer_bot,
        file_contents=file_contents,
        call_graph_context=call_graph_context,
        previous_fix_diff=previous_fix_diff,
    )

    returncode = run_claude(prompt, workspace_dir)

    if returncode != 0:
        print(
            f"[orchestrator] PR #{pr_number}: Claude exited with non-zero code, skip recording.",
            file=sys.stderr, flush=True,
        )
        return

    _finalize_run(
        pr_number=pr_number,
        owner=owner,
        repo=repo,
        attempt_number=attempt_number,
        max_attempts=max_attempts,
        prompt=prompt,
        new_reviews=new_reviews,
        new_inline_comments=new_inline_comments,
        diff=diff,
        workspace_dir=workspace_dir,
        original_head_sha=pr_info.head_sha,
        base_dir=base_dir,
    )


# ---------------------------------------------------------------------------
# Phase 6.2 - Patch Proposal Mode（2段階実行）
# ---------------------------------------------------------------------------

def _process_pr_patch_mode(
    pr_number: int,
    owner: str,
    repo: str,
    max_attempts: int,
    reviewer_bot: str,
    workspace_dir: Path,
) -> None:
    """Run 1 でパッチ生成のみ、Run 2 でパッチ検証 → commit を行う2段階モード。"""
    fix_attempts = state_manager.get_fix_attempts(pr_number)
    processed_ids = state_manager.get_processed_review_ids(pr_number)

    if fix_attempts >= max_attempts:
        print(f"[orchestrator] PR #{pr_number}: max attempts ({max_attempts}) reached, skip.", flush=True)
        return

    reviews = get_reviews(owner, repo, pr_number)
    new_reviews = [
        r for r in reviews
        if r.user_login == reviewer_bot and
        r.state == "CHANGES_REQUESTED" and
        r.id not in processed_ids
    ]

    if not new_reviews:
        print(f"[orchestrator] PR #{pr_number}: no new CHANGES_REQUESTED reviews from {reviewer_bot}, skip.", flush=True)
        return

    print(f"[orchestrator] PR #{pr_number}: {len(new_reviews)} new review(s) found (patch mode).", flush=True)

    pr_info = get_pr_info(owner, repo, pr_number)
    diff = get_pr_diff(owner, repo, pr_number)
    all_inline_comments = get_review_comments(owner, repo, pr_number)

    new_review_ids = {str(r.id) for r in new_reviews}
    new_inline_comments = [
        c for c in all_inline_comments
        if str(c.get("pull_request_review_id", "")) in new_review_ids
    ]

    # ブランチを最新化してからコンテキストを収集（Run 1 の前に1回だけ）
    prepare_branch(workspace_dir, pr_info.head_ref)

    base_dir = Path(__file__).parent
    attempt_number = fix_attempts + 1

    changed_files = extract_changed_files(diff)
    file_contents = get_file_contents(changed_files, workspace_dir)
    func_names = extract_function_names_from_diff(diff)
    call_graph_context = get_call_graph_context(func_names, workspace_dir)
    previous_fix_diff = get_previous_fix_diff(base_dir, pr_number, fix_attempts)

    print(
        f"[orchestrator] PR #{pr_number}: context gathered - "
        f"{len(file_contents)} file(s), {len(func_names)} function(s), "
        f"previous_fix={'yes' if previous_fix_diff else 'no'}",
        flush=True,
    )

    # Run 1: パッチ生成（commit しない）
    print(f"[orchestrator] PR #{pr_number}: starting Run 1 (patch proposal)...", flush=True)
    proposal_prompt = build_patch_proposal_prompt(
        pr_number=pr_number,
        pr_title=pr_info.title,
        branch=pr_info.head_ref,
        diff=diff,
        reviews=new_reviews,
        inline_comments=new_inline_comments,
        fix_attempt=attempt_number,
        reviewer_bot=reviewer_bot,
        file_contents=file_contents,
        call_graph_context=call_graph_context,
        previous_fix_diff=previous_fix_diff,
    )

    returncode1 = run_claude(proposal_prompt, workspace_dir)
    if returncode1 != 0:
        print(
            f"[orchestrator] PR #{pr_number}: Run 1 (patch proposal) failed with code {returncode1}, skip.",
            file=sys.stderr, flush=True,
        )
        return

    print(f"[orchestrator] PR #{pr_number}: Run 1 complete. Starting Run 2 (verification)...", flush=True)

    # Run 2: 検証 → commit（prepare_branch は呼ばない: Run 1 の変更を保持する）
    verify_prompt = build_patch_verification_prompt(
        pr_number=pr_number,
        branch=pr_info.head_ref,
        fix_attempt=attempt_number,
        reviewer_bot=reviewer_bot,
        reviews=new_reviews,
        inline_comments=new_inline_comments,
    )

    returncode2 = run_claude(verify_prompt, workspace_dir)
    if returncode2 != 0:
        print(
            f"[orchestrator] PR #{pr_number}: Run 2 (verification) failed with code {returncode2}, skip.",
            file=sys.stderr, flush=True,
        )
        return

    # 両 Run 完了後にアーティファクトを保存し、PR にレポートを投稿する
    # Run 1 の proposal_prompt を代表プロンプトとして保存する
    _finalize_run(
        pr_number=pr_number,
        owner=owner,
        repo=repo,
        attempt_number=attempt_number,
        max_attempts=max_attempts,
        prompt=proposal_prompt,
        new_reviews=new_reviews,
        new_inline_comments=new_inline_comments,
        diff=diff,
        workspace_dir=workspace_dir,
        original_head_sha=pr_info.head_sha,
        base_dir=base_dir,
    )


# ---------------------------------------------------------------------------
# 共通フィナライズ（アーティファクト保存 + PR コメント投稿）
# ---------------------------------------------------------------------------

def _finalize_run(
    pr_number: int,
    owner: str,
    repo: str,
    attempt_number: int,
    max_attempts: int,
    prompt: str,
    new_reviews: list,
    new_inline_comments: list,
    diff: str,
    workspace_dir: Path,
    original_head_sha: str,
    base_dir: Path,
) -> None:
    run_data = run_logger.save_run_artifacts(
        base_dir=base_dir,
        pr_number=pr_number,
        attempt=attempt_number,
        prompt=prompt,
        reviews=new_reviews,
        inline_comments=new_inline_comments,
        diff_before=diff,
        workspace_dir=workspace_dir,
        original_head_sha=original_head_sha,
    )

    run_logger.save_structured_log(base_dir, {
        "pr": pr_number,
        "attempt": attempt_number,
        "reviews_processed": len(new_reviews),
        "files_changed": run_data["files_changed"],
        "commit": run_data["commit_hash"],
        "committed": run_data["committed"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    if not run_data["committed"]:
        post_pr_comment(
            owner,
            repo,
            pr_number,
            "Auto-fix run completed without creating a commit. All review comments appear to be already addressed.",
        )
        print(
            f"[orchestrator] PR #{pr_number}: no commit created; marking review as processed to prevent retry loop.",
            flush=True,
        )
        state_manager.record_fix(pr_number, [r.id for r in new_reviews])
        return

    report_body = report_builder.build_fix_report(
        pr_number=pr_number,
        attempt=attempt_number,
        max_attempts=max_attempts,
        reviews=new_reviews,
        files_changed=run_data["files_changed"],
        commit_hash=run_data["commit_hash"],
        committed=run_data["committed"],
    )
    post_pr_comment(owner, repo, pr_number, report_body)
    print(f"[orchestrator] PR #{pr_number}: posted fix report comment.", flush=True)

    new_attempt = state_manager.record_fix(pr_number, [r.id for r in new_reviews])
    print(f"[orchestrator] PR #{pr_number}: fix attempt {new_attempt} recorded.", flush=True)

    if new_attempt >= max_attempts:
        post_pr_comment(
            owner, repo, pr_number,
            f"Auto-fix reached the maximum number of attempts ({max_attempts}). "
            "Please review manually."
        )
        print(f"[orchestrator] PR #{pr_number}: max attempts reached, posted comment.", flush=True)


if __name__ == "__main__":
    import time
    import traceback
    loop = "--loop" in sys.argv
    cfg = load_config()
    poll_interval = cfg["daemon"]["poll_interval_seconds"]

    if loop:
        print("[daemon] Starting loop mode (Ctrl+C to stop)...", flush=True)
        while True:
            print(f"[daemon] {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Running orchestrator...", flush=True)
            try:
                run_once(cfg)
            except Exception:
                print("[daemon] Error during orchestrator run", file=sys.stderr, flush=True)
                traceback.print_exc()
            print(f"[daemon] Sleeping {poll_interval} seconds...", flush=True)
            time.sleep(poll_interval)
    else:
        run_once(cfg)
