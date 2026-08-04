#!/usr/bin/env python3
"""Codex adapter: UserPromptSubmit -> upstream prompt-suggest.py (output shapes identical)."""

from _codex_bootstrap import run_upstream_hook

if __name__ == "__main__":
    run_upstream_hook("prompt-suggest.py")
