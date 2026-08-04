#!/usr/bin/env python3
"""Codex adapter: Stop -> upstream ralph-stop.py (decision:block shape identical; spawn client=codex via RALPH_SPAWN_CLIENT)."""

from _codex_bootstrap import run_upstream_hook

if __name__ == "__main__":
    run_upstream_hook("ralph-stop.py")
