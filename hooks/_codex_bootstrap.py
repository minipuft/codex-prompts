#!/usr/bin/env python3
"""
Shared bootstrap for codex-prompts hook adapters.

Resolves the shared claude-prompts hook library in both install layouts:
- dev checkout: hooks/lib symlink -> ../node_modules/claude-prompts/hooks/lib
- codex plugin cache: the cache copy drops symlinks (measured 2026-08-03 on
  codex-cli 0.146), so fall back to node_modules/claude-prompts/hooks/lib.

Pins MCP_WORKSPACE to the plugin root before any lib import so hook state and
the bundled MCP server agree on runtime-state paths, and defaults Ralph's
spawned-work client to codex (consumed by cli_spawner.SpawnConfig).
"""

import importlib.util
import io
import json
import os
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
_PLUGIN_ROOT = _HOOKS_DIR.parent


def _resolve_lib_dir() -> Path:
    symlinked = _HOOKS_DIR / "lib"
    if (symlinked / "workspace.py").exists():
        return symlinked.resolve()
    fallback = _PLUGIN_ROOT / "node_modules" / "claude-prompts" / "hooks" / "lib"
    if (fallback / "workspace.py").exists():
        return fallback
    raise FileNotFoundError(
        f"claude-prompts hook lib not found at {symlinked} or {fallback}; run npm install"
    )


LIB_DIR = _resolve_lib_dir()
UPSTREAM_HOOKS_DIR = LIB_DIR.parent

os.environ.setdefault("MCP_WORKSPACE", str(_PLUGIN_ROOT))
os.environ.setdefault("RALPH_SPAWN_CLIENT", "codex")
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

# Codex tool_name -> upstream (Claude Code) tool_name, for hooks whose logic
# branches on tool identity. Identity mappings (Bash -> Bash) are omitted.
# Names measured live on codex-cli 0.146 (2026-08-03): shell execution reports
# "Bash"; patch edits are documented as "apply_patch" carrying a command field;
# subagent spawns report "collaborationspawn_agent" (multi_agent feature).
CODEX_TOOL_NAMES = {
    "collaborationspawn_agent": "Task",
    "apply_patch": "Bash",
}


def load_upstream_hook(script_name: str):
    """Import an upstream hook script (e.g. 'ralph-stop.py') as a module."""
    module_name = script_name.removesuffix(".py").replace("-", "_")
    script_path = UPSTREAM_HOOKS_DIR / script_name
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load upstream hook: {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_upstream_hook(script_name: str, remap_tool_name: bool = False) -> None:
    """Execute an upstream hook's main() against this process's stdin/stdout.

    With remap_tool_name, stdin is consumed, tool_name is translated via
    CODEX_TOOL_NAMES, and the rewritten payload is re-presented as stdin.
    A payload that is not valid JSON is passed through untouched so the
    upstream hook applies its own error handling.
    """
    if remap_tool_name:
        raw = sys.stdin.read()
        try:
            payload = json.loads(raw)
            name = payload.get("tool_name")
            if name in CODEX_TOOL_NAMES:
                payload["tool_name"] = CODEX_TOOL_NAMES[name]
            raw = json.dumps(payload)
        except json.JSONDecodeError:
            pass
        sys.stdin = io.StringIO(raw)

    load_upstream_hook(script_name).main()
