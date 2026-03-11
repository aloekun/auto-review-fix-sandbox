"""
scripts/fetch_pr_reviews.py
PR のレビュースレッドを一括取得してローカルファイルに保存する。

使い方:
  python scripts/fetch_pr_reviews.py 25
  python scripts/fetch_pr_reviews.py 25 --out /tmp/pr25.txt
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

QUERY = """
query($owner: String!, $repo: String!, $pr: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      title
      reviewThreads(first: 50, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          comments(first: 5) {
            totalCount
            nodes {
              author { login }
              body
              createdAt
            }
          }
        }
      }
    }
  }
}
"""

OWNER = "aloekun"
REPO = "auto-review-fix-sandbox"


def fetch_threads(pr_number: int) -> list[dict]:
    threads: list[dict] = []
    cursor = None
    page = 0
    while True:
        page += 1
        variables = {"owner": OWNER, "repo": REPO, "pr": pr_number}
        if cursor:
            variables["cursor"] = cursor

        result = subprocess.run(
            [
                "gh", "api", "graphql",
                "-f", f"query={QUERY}",
                "-F", f"owner={OWNER}",
                "-F", f"repo={REPO}",
                "-F", f"pr={pr_number}",
                *(["-F", f"cursor={cursor}"] if cursor else []),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        data = json.loads(result.stdout)
        pr_data = data["data"]["repository"].get("pullRequest")
        if pr_data is None:
            raise ValueError(f"PR #{pr_number} not found in {OWNER}/{REPO}")
        rt = pr_data["reviewThreads"]
        threads.extend(rt["nodes"])
        page_info = rt["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]

    return threads


def format_report(pr_number: int, threads: list[dict]) -> str:
    unresolved = [t for t in threads if not t["isResolved"]]
    resolved = [t for t in threads if t["isResolved"]]

    lines = [
        f"=== PR #{pr_number} Review Threads ===",
        f"Total: {len(threads)} | Unresolved: {len(unresolved)} | Resolved: {len(resolved)}",
        "",
    ]

    def _thread_block(t: dict, idx: int, body_limit: int = 200) -> list[str]:
        status = "RESOLVED" if t["isResolved"] else "UNRESOLVED"
        outdated = " [outdated]" if t["isOutdated"] else ""
        block = [
            f"[{idx}] {status}{outdated}  id={t['id']}",
            f"    File: {t['path']}:{t['line']}",
        ]
        first = True
        comment_nodes = t["comments"]["nodes"]
        total_count = t["comments"].get("totalCount", len(comment_nodes))
        for c in comment_nodes:
            author = c["author"]["login"] if c["author"] else "?"
            raw = c["body"].replace("\n", " ").strip()
            preview = raw[:body_limit] + ("..." if len(raw) > body_limit else "")
            prefix = "    " if first else "    -> "
            block.append(f"{prefix}[{author}] {preview}")
            first = False
        if total_count > len(comment_nodes):
            block.append(f"    [+{total_count - len(comment_nodes)} more comments not shown]")
        block.append("")
        return block

    if unresolved:
        lines.append("--- UNRESOLVED ---")
        for i, t in enumerate(unresolved, 1):
            lines.extend(_thread_block(t, i))

    if resolved:
        lines.append("--- RESOLVED ---")
        for i, t in enumerate(resolved, 1):
            lines.extend(_thread_block(t, i))

    return "\n".join(lines)


def main() -> None:
    # スクリプトが pnpm 経由で実行される場合、cwd はプロジェクトルート。
    _PROJECT_ROOT = Path(__file__).parent.parent

    parser = argparse.ArgumentParser()
    parser.add_argument("pr", type=int, help="PR number")
    parser.add_argument(
        "--out",
        default="",
        help="Output file path (default: tmp/pr<N>_reviews.txt in project root)",
    )
    parser.add_argument("--json-out", default="", help="Also save raw JSON here")
    args = parser.parse_args()

    print(f"Fetching review threads for PR #{args.pr}...", file=sys.stderr)
    threads = fetch_threads(args.pr)

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(threads, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Raw JSON saved: {out_path}", file=sys.stderr)

    report = format_report(args.pr, threads)

    out = Path(args.out) if args.out else _PROJECT_ROOT / "tmp" / f"pr{args.pr}_reviews.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"Report saved: {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
