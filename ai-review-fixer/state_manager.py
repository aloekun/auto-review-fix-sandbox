"""
state_manager.py
処理済みPRの修正試行回数とレビューIDを追跡する。
state.json はgitignore済み。
"""

import json
import os
from pathlib import Path

STATE_FILE = Path(__file__).parent / "state.json"


def _load() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def _save(state: dict) -> None:
    tmp_file = STATE_FILE.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_file, STATE_FILE)


def _pr_key(pr_number: int) -> str:
    return f"pr_{pr_number}"


def get_fix_attempts(pr_number: int) -> int:
    state = _load()
    return state.get(_pr_key(pr_number), {}).get("fix_attempts", 0)


def get_processed_review_ids(pr_number: int) -> list[str]:
    state = _load()
    return state.get(_pr_key(pr_number), {}).get("processed_review_ids", [])


def record_fix(pr_number: int, review_ids: list[str]) -> int:
    """修正完了を記録し、新しい fix_attempts の値を返す。"""
    state = _load()
    key = _pr_key(pr_number)
    entry = state.get(key, {"fix_attempts": 0, "processed_review_ids": []})
    entry["fix_attempts"] += 1
    for rid in review_ids:
        if rid not in entry["processed_review_ids"]:
            entry["processed_review_ids"].append(rid)
    state[key] = entry
    _save(state)
    return entry["fix_attempts"]


def reset_pr(pr_number: int) -> None:
    """PRの状態をリセットする（テスト用）。"""
    state = _load()
    state.pop(_pr_key(pr_number), None)
    _save(state)
