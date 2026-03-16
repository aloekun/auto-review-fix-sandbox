"""Stop フック設定の検証テスト."""

import json
from pathlib import Path

SETTINGS_TEMPLATE = Path(__file__).resolve().parents[3] / ".claude" / "settings.local.json.template"


def test_stop_hook_is_configured_in_template() -> None:
    """settings.local.json.template に Stop フックが設定されていることを確認する."""
    assert SETTINGS_TEMPLATE.exists(), f"Template not found: {SETTINGS_TEMPLATE}"

    settings = json.loads(SETTINGS_TEMPLATE.read_text(encoding="utf-8"))
    hooks = settings.get("hooks", {})
    stop_hooks = hooks.get("Stop", [])

    assert len(stop_hooks) > 0, "Stop hooks section is empty"
    commands = [
        h["command"] for entry in stop_hooks for h in entry.get("hooks", []) if "command" in h
    ]
    assert any("hooks-stop-quality" in cmd for cmd in commands), (
        f"hooks-stop-quality not found in Stop hook commands: {commands}"
    )
