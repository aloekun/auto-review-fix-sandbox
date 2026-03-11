"""
scripts/list_unresolved.py
サブエージェント向け: PR の未対応レビュースレッドのみを stdout に出力する。

使い方:
  python scripts/list_unresolved.py 26
  pnpm gh-unresolved 26

Exit code:
  0  未対応なし
  1  未対応あり
"""

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent))
from fetch_pr_reviews import OWNER, REPO, fetch_threads  # noqa: E402

BODY_LIMIT = 500
_DETAILS_RE = re.compile(r"<details>.*?</details>", re.DOTALL)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List unresolved PR review threads (sub-agent friendly)."
    )
    parser.add_argument("pr", type=int, help="PR number")
    args = parser.parse_args()

    threads = fetch_threads(args.pr)
    unresolved = [t for t in threads if not t["isResolved"]]

    print(
        f"PR #{args.pr} ({OWNER}/{REPO}): "
        f"{len(unresolved)} unresolved / {len(threads)} total"
    )

    if not unresolved:
        print("All review threads resolved.")
        sys.exit(0)

    print()
    for i, t in enumerate(unresolved, 1):
        outdated = " [outdated]" if t["isOutdated"] else ""
        print(f"[{i}] id={t['id']}{outdated}")
        line = t["line"] if t["line"] is not None else "?"
        print(f"    File: {t['path']}:{line}")
        nodes = t["comments"]["nodes"]
        total_count = t["comments"].get("totalCount", len(nodes))
        for j, c in enumerate(nodes):
            author = c["author"]["login"] if c["author"] else "?"
            raw = _DETAILS_RE.sub("", c["body"]).replace("\n", " ").strip()
            preview = raw[:BODY_LIMIT] + ("..." if len(raw) > BODY_LIMIT else "")
            prefix = "   " if j == 0 else "    -> "
            print(f"    {prefix}[{author}] {preview}")
        if total_count > len(nodes):
            print(f"    [+{total_count - len(nodes)} more comments not shown]")
        print()

    sys.exit(1)


if __name__ == "__main__":
    main()
