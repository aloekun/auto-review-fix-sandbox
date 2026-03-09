"""
run_logger.py
実行アーティファクトの保存と構造化JSONログの記録を担当する。

保存先:
  runs/pr-{N}/attempt-{M}/  - prompt, reviews, diff_before, diff_after
  logs/YYYY-MM-DD/          - pr-{N}-run-{M}.json
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def save_run_artifacts(
    base_dir: Path,
    pr_number: int,
    attempt: int,
    prompt: str,
    reviews: list,
    inline_comments: list,
    diff_before: str,
    workspace_dir: Path,
    original_head_sha: str,
) -> dict:
    """
    実行アーティファクトを保存し、git情報を返す。

    Returns:
        dict with keys: commit_hash, committed (bool), files_changed (list[str])
    """
    run_dir = base_dir / "runs" / f"pr-{pr_number}" / f"attempt-{attempt}"
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    (run_dir / "reviews.txt").write_text(
        _format_reviews_text(reviews, inline_comments), encoding="utf-8"
    )
    (run_dir / "diff_before.patch").write_text(diff_before, encoding="utf-8")

    commit_hash = _get_commit_hash(workspace_dir)
    committed = commit_hash != original_head_sha

    files_changed: list[str] = []
    if committed:
        files_changed = _get_changed_files(workspace_dir)
        diff_after = _get_diff_after(workspace_dir)
        (run_dir / "diff_after.patch").write_text(diff_after, encoding="utf-8")

    print(f"[run_logger] Saved artifacts: {run_dir}", flush=True)
    return {
        "commit_hash": commit_hash,
        "committed": committed,
        "files_changed": files_changed,
    }


def save_structured_log(base_dir: Path, log_data: dict) -> None:
    """構造化JSONログを logs/YYYY-MM-DD/pr-{N}-run-{M}.json に保存する。"""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_dir = base_dir / "logs" / date_str
    log_dir.mkdir(parents=True, exist_ok=True)

    pr = log_data["pr"]
    attempt = log_data["attempt"]
    log_file = log_dir / f"pr-{pr}-run-{attempt}.json"
    log_file.write_text(
        json.dumps(log_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[run_logger] Saved log: {log_file}", flush=True)


def _get_commit_hash(workspace_dir: Path) -> str:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H"],
        capture_output=True, text=True, cwd=workspace_dir,
    )
    return result.stdout.strip()


def _get_changed_files(workspace_dir: Path) -> list:
    result = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        capture_output=True, text=True, cwd=workspace_dir,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def _get_diff_after(workspace_dir: Path) -> str:
    result = subprocess.run(
        ["git", "show", "HEAD", "--patch"],
        capture_output=True, text=True, cwd=workspace_dir,
    )
    return result.stdout


def _format_reviews_text(reviews: list, inline_comments: list) -> str:
    lines = []
    for r in reviews:
        lines.append(f"Review by {r.user_login} [{r.state}] (id: {r.id})")
        lines.append(f"Submitted at: {r.submitted_at}")
        if r.body:
            lines.append(f"Body:\n{r.body}")
        lines.append("")

    if inline_comments:
        lines.append("--- Inline Comments ---")
        for c in inline_comments:
            path = c.get("path", "?")
            line = c.get("original_line", c.get("line", "?"))
            body = c.get("body", "")
            lines.append(f"{path}:{line} -> {body}")

    return "\n".join(lines)
