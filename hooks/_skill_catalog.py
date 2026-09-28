#!/usr/bin/env python3
"""Self-contained skill counter for the Codex session-skills adapter.

WHY THIS EXISTS RATHER THAN IMPORTING UPSTREAM:
The adapter used to call `load_upstream_hook("session-skills.py")` and use its
`scan_skills()`. That made a Codex session-start hook depend on an upstream file that
Claude Code itself never registered — `session-skills.py` was a hook in name only, wired
into no `hooks.json` on either side. When the upstream repo removed it (2026-08-05), the
import would have raised, the hook would have exited non-zero, and Codex reads a failed
hook launch as a BLOCK decision on that event — every session start, for a reminder string.

The adapter only ever needed a COUNT: `sum(len(names) for names in categories.values())`,
plus an is-empty check. It never read the categories. So the 253-line categorizer was never
the dependency — this is.

Semantics are deliberately identical to the upstream parser it replaces: a directory counts
only when its SKILL.md has YAML frontmatter carrying a non-empty `description`, in either the
multi-line `>-` form or the single-line form. Verified against ~/.codex/skills on 2026-08-05:
108 counted out of 109 directories, matching upstream exactly.
"""

import re
from pathlib import Path

__all__ = ["read_skill_description", "count_skills"]


def read_skill_description(skill_dir: Path) -> str | None:
    """Extract the description from a skill's SKILL.md YAML frontmatter."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    try:
        content = skill_md.read_text(encoding="utf-8")
    except OSError:
        return None

    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None
    frontmatter = match.group(1)

    # Multi-line `description: >-` form first — the common shape in these skills.
    desc_match = re.search(r"description:\s*>-?\s*\n((?:\s+.*\n)*)", frontmatter)
    if desc_match:
        raw = desc_match.group(1).strip()
        if raw:
            return re.sub(r"\s+", " ", raw).strip()

    # Single-line fallback. The `>` guard keeps a bare block marker from counting.
    desc_match = re.search(r"description:\s*(.+)", frontmatter)
    if desc_match:
        raw = desc_match.group(1).strip()
        if raw and not raw.startswith(">"):
            return raw

    return None


def count_skills(skills_dir: Path) -> int:
    """Number of skill directories carrying a parseable description."""
    if not skills_dir.is_dir():
        return 0
    return sum(
        1
        for entry in sorted(skills_dir.iterdir())
        if entry.is_dir() and read_skill_description(entry)
    )
