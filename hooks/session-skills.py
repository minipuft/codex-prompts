#!/usr/bin/env python3
"""Codex adapter: SessionStart(startup|resume) -> skill-first protocol reminder.

Not a plain shim: Codex natively enumerates every skill under ~/.codex/skills
in its <skills_instructions> injection (measured 16.4KB on codex-cli 0.146,
2026-08-03), so a categorized catalog would duplicate what the host already
provides. This adapter uses the skill count as an existence gate and injects
only the protocol framing Codex lacks.

Counting is local (`_skill_catalog`), not `load_upstream_hook("session-skills.py")`.
That upstream file was a hook in name only — registered in no `hooks.json` on either
side — and was removed on 2026-08-05 once the Claude Code copy moved to the global
hooks layer. Importing it would then raise, the hook would exit non-zero, and Codex
reads a failed hook launch as a BLOCK on that event. This adapter only ever used the
count, so it now owns the ~30 lines that produce one (verified identical: 108 of 109
directories) instead of depending on a 253-line categorizer it never read.
"""

import json
import sys
from pathlib import Path

from _skill_catalog import count_skills


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        hook_input = {}

    # Self-gate on source even though hooks.json also matches on it —
    # SessionStart matcher semantics are still experimental in Codex.
    if hook_input.get("source") not in ("startup", "resume"):
        sys.exit(0)

    total = count_skills(Path.home() / ".codex" / "skills")
    if not total:
        sys.exit(0)

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
