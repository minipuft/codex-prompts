#!/usr/bin/env python3
"""Codex adapter: PreToolUse -> upstream delegation-enforce.py (tool names remapped via CODEX_TOOL_NAMES)."""

from _codex_bootstrap import run_upstream_hook

if __name__ == "__main__":
    run_upstream_hook("delegation-enforce.py", remap_tool_name=True)
