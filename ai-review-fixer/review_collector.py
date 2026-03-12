"""
review_collector.py
gh CLI を使って GitHub PR のレビューコメントと差分を取得する。
"""

import json
import subprocess
from dataclasses import dataclass


@dataclass
class Review:
    id: str
    user_login: str
    state: str  # CHANGES_REQUESTED, COMMENTED, APPROVED, etc.
    body: str
    submitted_at: str


@dataclass
class PRInfo:
    number: int
    head_ref: str
    head_sha: str
    title: str
    head_repo_url: str  # フォークPR対応: ブランチが存在するリポジトリのURL


class GHClient:
    """gh CLI をラップして GitHub PR データを取得する。"""

    def get_open_prs(self, owner: str, repo: str) -> list[int]:
        """オープン中のPR番号一覧を返す。"""
        result = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                f"{owner}/{repo}",
                "--state",
                "open",
                "--json",
                "number",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=60,
        )
        items = json.loads(result.stdout)
        return [item["number"] for item in items]

    def get_pr_info(self, owner: str, repo: str, pr_number: int) -> PRInfo:
        """PRのメタ情報を取得する。フォークPR対応のため head リポジトリURLも含む。"""
        result = subprocess.run(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--repo",
                f"{owner}/{repo}",
                "--json",
                "number,headRefName,headRefOid,title,headRepository",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=60,
        )
        data = json.loads(result.stdout)
        head_repo = data.get("headRepository") or {}
        head_repo_url = head_repo.get("url") or f"https://github.com/{owner}/{repo}"
        return PRInfo(
            number=data["number"],
            head_ref=data["headRefName"],
            head_sha=data["headRefOid"],
            title=data["title"],
            head_repo_url=head_repo_url,
        )

    def get_reviews(self, owner: str, repo: str, pr_number: int) -> list[Review]:
        """PRのレビュー一覧を取得する。"""
        result = subprocess.run(
            [
                "gh",
                "api",
                "--paginate",
                "--jq",
                ".[]",
                f"repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=60,
        )
        items = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        return [
            Review(
                id=str(item["id"]),
                user_login=item["user"]["login"],
                state=item["state"],
                body=item.get("body", ""),
                submitted_at=item.get("submitted_at", ""),
            )
            for item in items
        ]

    def get_review_comments(
        self, owner: str, repo: str, pr_number: int
    ) -> list[dict]:
        """PRのインラインレビューコメント一覧を取得する。"""
        result = subprocess.run(
            [
                "gh",
                "api",
                "--paginate",
                "--jq",
                ".[]",
                f"repos/{owner}/{repo}/pulls/{pr_number}/comments",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=60,
        )
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """PR の差分を取得する。"""
        result = subprocess.run(
            ["gh", "pr", "diff", str(pr_number), "--repo", f"{owner}/{repo}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=60,
        )
        return result.stdout

    def post_pr_comment(
        self, owner: str, repo: str, pr_number: int, body: str
    ) -> None:
        """PRにコメントを投稿する。"""
        subprocess.run(
            [
                "gh",
                "pr",
                "comment",
                str(pr_number),
                "--repo",
                f"{owner}/{repo}",
                "--body",
                body,
            ],
            check=True,
            encoding="utf-8",
            timeout=60,
        )

    def request_review(
        self, owner: str, repo: str, pr_number: int, reviewer_bot: str
    ) -> None:
        """修正後に reviewer へ再レビューを依頼する。"""
        if reviewer_bot == "coderabbitai[bot]":
            self.post_pr_comment(owner, repo, pr_number, "@coderabbitai review")
        else:
            # 将来: GitHub reviewers API / 他ボットのコメントトリガー
            pass
