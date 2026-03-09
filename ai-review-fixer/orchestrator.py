"""
orchestrator.py
メイン制御ループ。PRレビューを検知してClaudeに修正させる。

使い方:
  python orchestrator.py          # 一度だけ実行（デーモン用）
  python orchestrator.py --once   # 同上（明示的）
"""

import subprocess
import sys
from pathlib import Path

import yaml

import state_manager
from claude_runner import run_claude
from prompt_builder import build_prompt
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

    ensure_workspace(workspace_dir, owner, repo)

    pr_numbers = get_open_prs(owner, repo)
    if not pr_numbers:
        print("[orchestrator] No open PRs.", flush=True)
        return

    for pr_number in pr_numbers:
        _process_pr(
            pr_number=pr_number,
            owner=owner,
            repo=repo,
            max_attempts=max_attempts,
            reviewer_bot=reviewer_bot,
            workspace_dir=workspace_dir,
        )


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
        if r.user_login == reviewer_bot
        and r.state == "CHANGES_REQUESTED"
        and r.id not in processed_ids
    ]

    if not new_reviews:
        print(f"[orchestrator] PR #{pr_number}: no new CHANGES_REQUESTED reviews from {reviewer_bot}, skip.", flush=True)
        return

    print(f"[orchestrator] PR #{pr_number}: {len(new_reviews)} new review(s) found.", flush=True)

    pr_info = get_pr_info(owner, repo, pr_number)
    diff = get_pr_diff(owner, repo, pr_number)
    all_inline_comments = get_review_comments(owner, repo, pr_number)

    new_review_ids = {r.id for r in new_reviews}
    new_inline_comments = [
        c for c in all_inline_comments
        if str(c.get("pull_request_review_id", "")) in new_review_ids
    ]

    prompt = build_prompt(
        pr_number=pr_number,
        pr_title=pr_info.title,
        branch=pr_info.head_ref,
        diff=diff,
        reviews=new_reviews,
        inline_comments=new_inline_comments,
        fix_attempt=fix_attempts + 1,
        reviewer_bot=reviewer_bot,
    )

    prepare_branch(workspace_dir, pr_info.head_ref)

    returncode = run_claude(prompt, workspace_dir)

    if returncode != 0:
        print(
            f"[orchestrator] PR #{pr_number}: Claude exited with non-zero code, skip recording.",
            file=sys.stderr, flush=True,
        )
        return

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
    loop = "--loop" in sys.argv
    cfg = load_config()
    poll_interval = cfg["daemon"]["poll_interval_seconds"]

    if loop:
        print("[daemon] Starting loop mode (Ctrl+C to stop)...", flush=True)
        while True:
            print(f"[daemon] {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Running orchestrator...", flush=True)
            try:
                run_once(cfg)
            except Exception as e:
                print(f"[daemon] Error: {e}", file=sys.stderr, flush=True)
            print(f"[daemon] Sleeping {poll_interval} seconds...", flush=True)
            time.sleep(poll_interval)
    else:
        run_once(cfg)
