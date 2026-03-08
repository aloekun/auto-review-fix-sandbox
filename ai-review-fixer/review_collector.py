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


def get_open_prs(owner: str, repo: str) -> list[int]:
    """オープン中のPR番号一覧を返す。"""
    result = subprocess.run(
        ["gh", "pr", "list", "--repo", f"{owner}/{repo}",
         "--state", "open", "--json", "number"],
        capture_output=True, text=True, encoding="utf-8", check=True
    )
    items = json.loads(result.stdout)
    return [item["number"] for item in items]


def get_pr_info(owner: str, repo: str, pr_number: int) -> PRInfo:
    """PRのメタ情報を取得する。フォークPR対応のため head リポジトリURLも含む。"""
    result = subprocess.run(
        ["gh", "pr", "view", str(pr_number),
         "--repo", f"{owner}/{repo}",
         "--json", "number,headRefName,headRefOid,title,headRepository"],
        capture_output=True, text=True, encoding="utf-8", check=True
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


def get_reviews(owner: str, repo: str, pr_number: int) -> list[Review]:
    """PRのレビュー一覧を取得する。"""
    result = subprocess.run(
        ["gh", "api", f"repos/{owner}/{repo}/pulls/{pr_number}/reviews"],
        capture_output=True, text=True, encoding="utf-8", check=True
    )
    items = json.loads(result.stdout)
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


def get_review_comments(owner: str, repo: str, pr_number: int) -> list[dict]:
    """PRのインラインレビューコメント一覧を取得する。"""
    result = subprocess.run(
        ["gh", "api", f"repos/{owner}/{repo}/pulls/{pr_number}/comments"],
        capture_output=True, text=True, encoding="utf-8", check=True
    )
    return json.loads(result.stdout)


def get_pr_diff(owner: str, repo: str, pr_number: int) -> str:
    """PR の差分を取得する。"""
    result = subprocess.run(
        ["gh", "pr", "diff", str(pr_number), "--repo", f"{owner}/{repo}"],
        capture_output=True, text=True, encoding="utf-8", check=True
    )
    return result.stdout


def post_pr_comment(owner: str, repo: str, pr_number: int, body: str) -> None:
    """PRにコメントを投稿する。"""
    subprocess.run(
        ["gh", "pr", "comment", str(pr_number),
         "--repo", f"{owner}/{repo}", "--body", body],
        check=True
    )
