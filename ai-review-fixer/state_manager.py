"""
state_manager.py
処理済みPRの修正試行回数とレビューIDを追跡する。
state.json はgitignore済み。

キー形式: {owner}/{repo}/pr_{N}  (Phase 9 multi-repo 対応)
旧キー形式 pr_{N} が検出された場合は警告ログを出力する。
"""

import json
import os
import sys
from pathlib import Path

_DEFAULT_STATE_FILE = Path(__file__).parent / "state.json"


class StateManager:
    """PR ごとの修正試行回数と処理済みレビュー ID を state.json に永続化する。"""

    def __init__(self, state_file: Path = _DEFAULT_STATE_FILE) -> None:
        self._state_file = state_file

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_fix_attempts(self, owner: str, repo: str, pr_number: int) -> int:
        state = self._load()
        return state.get(self._key(owner, repo, pr_number), {}).get("fix_attempts", 0)

    def get_processed_review_ids(
        self, owner: str, repo: str, pr_number: int
    ) -> list[str]:
        state = self._load()
        return state.get(self._key(owner, repo, pr_number), {}).get(
            "processed_review_ids", []
        )

    def record_fix(
        self, owner: str, repo: str, pr_number: int, review_ids: list
    ) -> int:
        """修正完了を記録し、新しい fix_attempts の値を返す。"""
        state = self._load()
        key = self._key(owner, repo, pr_number)
        entry = state.get(key, {"fix_attempts": 0, "processed_review_ids": []})
        entry["fix_attempts"] += 1
        for rid in review_ids:
            if rid not in entry["processed_review_ids"]:
                entry["processed_review_ids"].append(rid)
        state[key] = entry
        self._save(state)
        return entry["fix_attempts"]

    def reset_pr(self, owner: str, repo: str, pr_number: int) -> None:
        """PRの状態をリセットする（テスト用）。"""
        state = self._load()
        state.pop(self._key(owner, repo, pr_number), None)
        self._save(state)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        if self._state_file.exists():
            try:
                with open(self._state_file, encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    return {}
                # 旧形式キー（/ を含まない）を検出して警告する
                for key in data:
                    if "/" not in key:
                        print(
                            f"[state_manager] WARNING: legacy key detected: {key!r}. "
                            "This key will be ignored. "
                            "Delete state.json to reset.",
                            file=sys.stderr,
                            flush=True,
                        )
                return data
            except json.JSONDecodeError:
                return {}
        return {}

    def _save(self, state: dict) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_file = self._state_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_file, self._state_file)

    @staticmethod
    def _key(owner: str, repo: str, pr_number: int) -> str:
        return f"{owner}/{repo}/pr_{pr_number}"
