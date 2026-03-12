"""
fake_gh_client.py
テスト用の GHClient 偽実装。設定可能なデータを返し、呼び出し履歴を記録する。
"""

from dataclasses import dataclass, field

from review_collector import PRInfo, Review


@dataclass
class FakeGHClient:
    """GHClientProtocol の偽実装。テストで注入して使う。"""

    open_prs: list[int] = field(default_factory=list)
    pr_infos: dict[int, PRInfo] = field(default_factory=dict)
    reviews: dict[int, list[Review]] = field(default_factory=dict)
    review_comments: dict[int, list[dict]] = field(default_factory=dict)
    pr_diffs: dict[int, str] = field(default_factory=dict)

    # 呼び出し記録（アサート用）
    posted_comments: list[tuple[int, str]] = field(default_factory=list)
    review_requests: list[tuple[int, str]] = field(default_factory=list)

    def get_open_prs(self, owner: str, repo: str) -> list[int]:  # noqa: ARG002
        return list(self.open_prs)

    def get_pr_info(self, owner: str, repo: str, pr_number: int) -> PRInfo:  # noqa: ARG002
        return self.pr_infos[pr_number]

    def get_reviews(self, owner: str, repo: str, pr_number: int) -> list[Review]:  # noqa: ARG002
        return list(self.reviews.get(pr_number, []))

    def get_review_comments(
        self, owner: str, repo: str, pr_number: int  # noqa: ARG002
    ) -> list[dict]:
        return list(self.review_comments.get(pr_number, []))

    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:  # noqa: ARG002
        return self.pr_diffs.get(pr_number, "")

    def post_pr_comment(
        self, owner: str, repo: str, pr_number: int, body: str  # noqa: ARG002
    ) -> None:
        self.posted_comments.append((pr_number, body))

    def request_review(
        self, owner: str, repo: str, pr_number: int, reviewer_bot: str  # noqa: ARG002
    ) -> None:
        self.review_requests.append((pr_number, reviewer_bot))
