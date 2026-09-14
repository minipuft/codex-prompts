#!/usr/bin/env python3
"""Codex adapter: SessionStart(compact) -> upstream compact-recovery.py (plain-stdout context injection identical)."""

from _codex_bootstrap import run_upstream_hook

if __name__ == "__main__":
    run_upstream_hook("compact-recovery.py")
