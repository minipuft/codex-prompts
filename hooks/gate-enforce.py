#!/usr/bin/env python3
"""Codex adapter: PreToolUse -> upstream gate-enforce.py (permissionDecision shape identical)."""

from _codex_bootstrap import run_upstream_hook

if __name__ == "__main__":
    run_upstream_hook("gate-enforce.py")
