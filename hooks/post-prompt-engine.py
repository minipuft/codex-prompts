#!/usr/bin/env python3
"""Codex adapter: PostToolUse -> upstream post-prompt-engine.py (output shapes identical)."""

from _codex_bootstrap import run_upstream_hook

if __name__ == "__main__":
    run_upstream_hook("post-prompt-engine.py")
