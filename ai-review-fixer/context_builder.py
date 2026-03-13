"""
context_builder.py
プロンプトに付与する追加コンテキストを構築する。

- 変更されたファイルの全体内容 (6.1.1)
- Call graph context: 呼び出し元コード (6.1.2)
- 前回の自動修正差分 (6.1.3)
"""

import re
from pathlib import Path

from git_client import GitClient
from interfaces import GitClientProtocol

# ファイル内容を渡す上限（大きすぎるとプロンプトが膨らむ）
_MAX_FILE_SIZE_CHARS = 20_000
# call graph の1関数あたり最大出力行数
_MAX_GREP_LINES_PER_FUNC = 20
# call graph を収集する関数の最大数
_MAX_FUNCS_FOR_CALL_GRAPH = 5

# 各言語の関数/メソッド定義を検出する正規表現
_DEF_PATTERNS = [
    re.compile(r"^\s*def\s+(\w+)"),  # Python
    re.compile(r"^\s*(?:async\s+)?function\s+(\w+)"),  # JS/TS function
    re.compile(r"^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>"),  # JS/TS arrow
    re.compile(r"^\s*class\s+(\w+)"),  # class
    re.compile(
        r"^\s*(?:public|private|protected|static|async)"
        r"(?:\s+\w+)*\s+(\w+)\s*\("
    ),  # Java/C#/TS method
]

# 汎用的すぎて call graph では役に立たない名前を除外
_EXCLUDE_NAMES = frozenset(
    {
        "__init__",
        "__str__",
        "__repr__",
        "__eq__",
        "__hash__",
        "main",
        "test",
        "setup",
        "teardown",
        "self",
        "cls",
        "run",
        "get",
        "set",
        "new",
        "init",
    }
)

# hunk ヘッダー "@@ -N,M +N,M @@ context" のパターン
_HUNK_HEADER = re.compile(r"^@@ [^@]+ @@ (.+)")


class ContextBuilder:
    """プロンプトに付与する追加コンテキストを構築する。"""

    def __init__(self, git_client: GitClientProtocol | None = None) -> None:
        self._git = git_client or GitClient()

    def extract_changed_files(self, diff: str) -> list[str]:
        """diff から変更されたファイルのパスを抽出する。"""
        files: list[str] = []
        for line in diff.splitlines():
            if line.startswith("+++ b/"):
                path = line[6:].strip()
                if path and path not in files:
                    files.append(path)
        return files

    def get_file_contents(
        self, changed_files: list[str], workspace_dir: Path
    ) -> dict[str, str]:
        """変更されたファイルの全体内容を読み込む。

        シンボリックリンクとリポジトリルート外へのパスエスケープを拒否する。
        フォーク PR で `secrets.txt -> /etc/passwd` のような仕込みを防ぐ。

        Returns:
            {relative_path: content} のマップ。ファイルが巨大な場合は先頭を返す。
        """
        contents: dict[str, str] = {}
        root = workspace_dir.resolve()
        for rel_path in changed_files:
            candidate = workspace_dir / rel_path
            # シンボリックリンクを解決して存在確認する。失敗は安全にスキップ。
            try:
                resolved = candidate.resolve(strict=True)
            except (OSError, ValueError):
                continue
            # シンボリックリンクまたはリポジトリルート外へのパスを拒否
            if candidate.is_symlink() or not resolved.is_relative_to(root):
                continue
            if not resolved.is_file():
                continue
            try:
                text = resolved.read_text(encoding="utf-8", errors="replace")
                if len(text) > _MAX_FILE_SIZE_CHARS:
                    text = text[:_MAX_FILE_SIZE_CHARS] + "\n... (truncated)"
                contents[rel_path] = text
            except Exception as exc:
                contents[rel_path] = f"(error reading file: {exc})"
        return contents

    def extract_function_names_from_diff(self, diff: str) -> list[str]:
        """diff から変更された関数/クラス名を抽出する。

        hunk ヘッダーのコンテキスト行と、変更行（+/-）の定義パターンを参照する。
        """
        found: set[str] = set()

        for line in diff.splitlines():
            # hunk ヘッダーからコンテキスト関数名を抽出
            m = _HUNK_HEADER.match(line)
            if m:
                _extract_name_from_text(m.group(1).strip(), found)
                continue

            # 変更行（+/-）の定義パターンを抽出
            if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
                _extract_name_from_text(line[1:], found)

        return sorted(n for n in found if n not in _EXCLUDE_NAMES)

    def get_call_graph_context(
        self, func_names: list[str], workspace_dir: Path
    ) -> str:
        """関数名を git grep して呼び出し元のコードを返す。

        Returns:
            各関数の使用箇所を示す文字列。見つからなければ空文字列。
        """
        if not func_names:
            return ""

        sections: list[str] = []
        for name in func_names[:_MAX_FUNCS_FOR_CALL_GRAPH]:
            try:
                result = self._git.run(
                    ["git", "grep", "-n", "--", name],
                    cwd=workspace_dir,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                if result.returncode not in (0, 1):
                    sections.append(f"#### Usages of `{name}`")
                    sections.append(f"(call-graph lookup failed: {result.stderr.strip()})")
                    sections.append("")
                    continue
                output = result.stdout.strip()
                if not output:
                    continue
                lines = output.splitlines()[:_MAX_GREP_LINES_PER_FUNC]
                sections.append(f"#### Usages of `{name}`")
                sections.extend(lines)
                sections.append("")
            except (OSError, Exception) as exc:
                sections.append(f"#### Usages of `{name}`")
                sections.append(f"(call-graph lookup failed: {exc})")
                sections.append("")

        return "\n".join(sections)

    def get_previous_fix_diff(
        self, base_dir: Path, pr_number: int, previous_attempt: int
    ) -> str | None:
        """前回の自動修正差分 (diff_after.patch) を返す。なければ None。"""
        if previous_attempt <= 0:
            return None
        diff_file = (
            base_dir
            / "runs"
            / f"pr-{pr_number}"
            / f"attempt-{previous_attempt}"
            / "diff_after.patch"
        )
        if diff_file.exists():
            text = diff_file.read_text(encoding="utf-8")
            limit = 50_000
            if len(text) > limit:
                text = text[:limit] + f"\n\n... [diff truncated at {limit} chars] ..."
            return text
        return None


def _extract_name_from_text(text: str, result: set[str]) -> None:
    for pat in _DEF_PATTERNS:
        m = pat.match(text)
        if m:
            result.add(m.group(1))
            break
