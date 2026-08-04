#!/usr/bin/env python3
"""Codex adapter: PostToolUse -> upstream ralph-context-tracker.py (tool names remapped via CODEX_TOOL_NAMES)."""

from _codex_bootstrap import run_upstream_hook

if __name__ == "__main__":
    run_upstream_hook("ralph-context-tracker.py", remap_tool_name=True)
