"""
run_logger.py
実行アーティファクトの保存と構造化JSONログの記録を担当する。

保存先:
  runs/pr-{N}/attempt-{M}/  - prompt, reviews, diff_before, diff_after
  logs/YYYY-MM-DD/          - pr-{N}-run-{M}.json
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from git_client import GitClient
from interfaces import GitClientProtocol


class RunLogger:
    """実行アーティファクトと構造化ログを保存する。"""

    def __init__(self, git_client: GitClientProtocol | None = None) -> None:
        self._git = git_client or GitClient()

    def save_run_artifacts(
        self,
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

        try:
            commit_hash = self._get_commit_hash(workspace_dir)
        except Exception as exc:
            raise RuntimeError(
                f"failed to inspect git state in {workspace_dir}"
            ) from exc
        committed = commit_hash != original_head_sha

        files_changed: list[str] = []
        if committed:
            try:
                files_changed = self._get_changed_files(workspace_dir, original_head_sha)
            except Exception as exc:
                print(f"[run_logger] Failed to get changed files: {exc}", flush=True)
            try:
                diff_after = self._get_diff_after(workspace_dir, original_head_sha)
                (run_dir / "diff_after.patch").write_text(diff_after, encoding="utf-8")
            except Exception as exc:
                raise RuntimeError(
                    f"[run_logger] Failed to save post-fix diff artifact: {exc}"
                ) from exc

        print(f"[run_logger] Saved artifacts: {run_dir}", flush=True)
        return {
            "commit_hash": commit_hash,
            "committed": committed,
            "files_changed": files_changed,
        }

    def save_structured_log(self, base_dir: Path, log_data: dict) -> None:
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

    # ------------------------------------------------------------------
    # Private git helpers
    # ------------------------------------------------------------------

    def _run_git(self, workspace_dir: Path, *args: str) -> str:
        git_bin = shutil.which("git")
        if git_bin is None:
            raise FileNotFoundError("Could not find 'git' in PATH")
        result = self._git.run(
            [git_bin, *args],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return result.stdout

    def _get_commit_hash(self, workspace_dir: Path) -> str:
        return self._run_git(workspace_dir, "log", "-1", "--format=%H").strip()

    def _get_changed_files(self, workspace_dir: Path, base_sha: str) -> list:
        stdout = self._run_git(
            workspace_dir, "diff", "--name-only", f"{base_sha}..HEAD"
        )
        return [f for f in stdout.strip().split("\n") if f]

    def _get_diff_after(self, workspace_dir: Path, base_sha: str) -> str:
        return self._run_git(workspace_dir, "diff", f"{base_sha}..HEAD")


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
