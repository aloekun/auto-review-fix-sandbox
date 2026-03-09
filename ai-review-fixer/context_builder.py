"""
context_builder.py
プロンプトに付与する追加コンテキストを構築する。

- 変更されたファイルの全体内容 (6.1.1)
- Call graph context: 呼び出し元コード (6.1.2)
- 前回の自動修正差分 (6.1.3)
"""

import re
import subprocess
from pathlib import Path

# ファイル内容を渡す上限（大きすぎるとプロンプトが膨らむ）
_MAX_FILE_SIZE_CHARS = 20_000
# call graph の1関数あたり最大出力行数
_MAX_GREP_LINES_PER_FUNC = 20
# call graph を収集する関数の最大数
_MAX_FUNCS_FOR_CALL_GRAPH = 5

# 各言語の関数/メソッド定義を検出する正規表現
_DEF_PATTERNS = [
    re.compile(r"^\s*def\s+(\w+)"),                                          # Python
    re.compile(r"^\s*(?:async\s+)?function\s+(\w+)"),                       # JS/TS function
    re.compile(r"^\s*(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\("),    # JS/TS arrow
    re.compile(r"^\s*class\s+(\w+)"),                                        # class
    re.compile(r"^\s*(?:public|private|protected|static|async)"
               r"(?:\s+\w+)*\s+(\w+)\s*\("),                               # Java/C#/TS method
]

# 汎用的すぎて call graph では役に立たない名前を除外
_EXCLUDE_NAMES = frozenset({
    "__init__", "__str__", "__repr__", "__eq__", "__hash__",
    "main", "test", "setup", "teardown", "self", "cls",
    "run", "get", "set", "new", "init",
})

# hunk ヘッダー "@@ -N,M +N,M @@ context" のパターン
_HUNK_HEADER = re.compile(r"^@@ [^@]+ @@ (.+)")


def extract_changed_files(diff: str) -> list[str]:
    """diff から変更されたファイルのパスを抽出する。"""
    files: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:].strip()
            if path and path not in files:
                files.append(path)
    return files


def get_file_contents(changed_files: list[str], workspace_dir: Path) -> dict[str, str]:
    """変更されたファイルの全体内容を読み込む。

    Returns:
        {relative_path: content} のマップ。ファイルが巨大な場合は先頭を返す。
    """
    contents: dict[str, str] = {}
    for rel_path in changed_files:
        abs_path = workspace_dir / rel_path
        if not abs_path.exists() or not abs_path.is_file():
            continue
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
            if len(text) > _MAX_FILE_SIZE_CHARS:
                text = text[:_MAX_FILE_SIZE_CHARS] + "\n... (truncated)"
            contents[rel_path] = text
        except Exception as exc:
            contents[rel_path] = f"(error reading file: {exc})"
    return contents


def extract_function_names_from_diff(diff: str) -> list[str]:
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

    return [n for n in found if n not in _EXCLUDE_NAMES]


def _extract_name_from_text(text: str, result: set[str]) -> None:
    for pat in _DEF_PATTERNS:
        m = pat.match(text)
        if m:
            result.add(m.group(1))
            break


def get_call_graph_context(
    func_names: list[str],
    workspace_dir: Path,
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
            result = subprocess.run(
                ["git", "grep", "-n", "--", name],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            output = result.stdout.strip()
            if not output:
                continue
            lines = output.splitlines()[:_MAX_GREP_LINES_PER_FUNC]
            sections.append(f"#### Usages of `{name}`")
            sections.extend(lines)
            sections.append("")
        except Exception:
            pass

    return "\n".join(sections)


def get_previous_fix_diff(
    base_dir: Path,
    pr_number: int,
    previous_attempt: int,
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
        return diff_file.read_text(encoding="utf-8")
    return None
