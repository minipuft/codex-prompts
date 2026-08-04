#!/usr/bin/env python3
"""Codex adapter: SessionStart(startup|resume) -> skill-first protocol reminder.

Not a plain shim: Codex natively enumerates every skill under ~/.codex/skills
in its <skills_instructions> injection (measured 16.4KB on codex-cli 0.146,
2026-08-03), so the upstream hook's categorized catalog would duplicate what
the host already provides. This adapter reuses upstream scan_skills() as the
existence gate and injects only the protocol framing Codex lacks.
"""

import json
import sys
from pathlib import Path

from _codex_bootstrap import load_upstream_hook


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        hook_input = {}

    # Self-gate on source even though hooks.json also matches on it —
    # SessionStart matcher semantics are still experimental in Codex.
    if hook_input.get("source") not in ("startup", "resume"):
        sys.exit(0)

    upstream = load_upstream_hook("session-skills.py")
    categories = upstream.scan_skills(Path.home() / ".codex" / "skills")
    if not categories:
        sys.exit(0)

    total = sum(len(names) for names in categories.values())
    context = "\n".join(
        [
            f"Skills-first: {total} skills are listed in your skills instructions — "
            "invoke the relevant one BEFORE reasoning from memory. "
            "Check → invoke → announce → follow.",
            "Priority: process → architecture → language → tool → knowledge",
            'Red flag: "I know this" / "skill is overkill" → STOP, invoke the skill',
        ]
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": context,
                }
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # never let a reminder hook break session start
        print(f"[session-skills adapter] {e}", file=sys.stderr)
        sys.exit(1)
