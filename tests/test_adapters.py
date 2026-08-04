"""
Adapter tests for codex-prompts.

Each adapter is exercised as Codex runs it: a subprocess fed a recorded
Codex stdin payload (shapes captured live from codex-cli 0.146 hook probes,
2026-08-03). MCP_WORKSPACE points at a per-test workspace so state writes
stay isolated.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

import _codex_bootstrap  # noqa: E402  (inserts the shared lib dir into sys.path)

# Recorded common fields from a live codex-cli 0.146 hook payload
CODEX_COMMON = {
    "session_id": "0199fc00-0000-7000-8000-000000000000",
    "transcript_path": None,
    "cwd": "/tmp",
    "model": "gpt-5.6-sol",
    "permission_mode": "default",
    "turn_id": "turn-1",
}


@pytest.fixture()
def workspace(tmp_path):
    """Isolated MCP workspace with the runtime-state dir the lib expects."""
    (tmp_path / "server" / "runtime-state").mkdir(parents=True)
    return tmp_path


def run_adapter(
    name: str,
    payload: dict,
    workspace: Path,
    hooks_dir: Path = HOOKS_DIR,
    extra_env: dict | None = None,
):
    env = {
        **os.environ,
        "MCP_WORKSPACE": str(workspace),
        "CLAUDE_PLUGIN_ROOT": str(hooks_dir.parent),
        **(extra_env or {}),
    }
    return subprocess.run(
        ["python3", str(hooks_dir / name)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def stdout_json(result):
    return json.loads(result.stdout) if result.stdout.strip() else {}


class TestPromptSuggest:
    def test_non_command_prompt_passes_through(self, workspace):
        result = run_adapter(
            "prompt-suggest.py",
            {**CODEX_COMMON, "hook_event_name": "UserPromptSubmit", "prompt": "hello"},
            workspace,
        )
        assert result.returncode == 0

    def test_command_prompt_without_state_db_exits_cleanly(self, workspace):
        result = run_adapter(
            "prompt-suggest.py",
            {**CODEX_COMMON, "hook_event_name": "UserPromptSubmit", "prompt": ">>dev_workflow"},
            workspace,
        )
        assert result.returncode == 0
        out = stdout_json(result)
        if out.get("hookSpecificOutput"):
            assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"


class TestGateEnforce:
    def test_fail_verdict_denies(self, workspace):
        payload = {
            **CODEX_COMMON,
            "hook_event_name": "PreToolUse",
            "tool_name": "mcp__codex-prompts__prompt_engine",
            "tool_use_id": "tu-1",
            "tool_input": {
                "chain_id": "chain-demo#1",
                "gate_verdict": "GATE_REVIEW: FAIL - criteria unmet",
            },
        }
        result = run_adapter("gate-enforce.py", payload, workspace)
        assert result.returncode == 0
        out = stdout_json(result)
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_structured_fail_verdict_denies(self, workspace):
        # The exact payload shape that crashed PreToolUse in the first live
        # E2E run (structured verdict object, preferred schema shape)
        payload = {
            **CODEX_COMMON,
            "hook_event_name": "PreToolUse",
            "tool_name": "mcp__claude_prompts_mcp__prompt_engine",
            "tool_use_id": "tu-1b",
            "tool_input": {
                "chain_id": "chain-dev_workflow#1",
                "user_response": "step output",
                "gate_verdict": {
                    "overall": "FAIL",
                    "rationale": "criteria unmet",
                    "per_gate": [{"index": 1, "passed": False, "rationale": "g: no"}],
                },
            },
        }
        result = run_adapter("gate-enforce.py", payload, workspace)
        assert result.returncode == 0
        out = stdout_json(result)
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_pass_verdict_allows(self, workspace):
        payload = {
            **CODEX_COMMON,
            "hook_event_name": "PreToolUse",
            "tool_name": "mcp__codex-prompts__prompt_engine",
            "tool_use_id": "tu-1",
            "tool_input": {
                "chain_id": "chain-demo#1",
                "gate_verdict": "GATE_REVIEW: PASS - all criteria met",
            },
        }
        result = run_adapter("gate-enforce.py", payload, workspace)
        assert result.returncode == 0
        out = stdout_json(result)
        assert out.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"


class TestDelegationEnforce:
    def _seed_pending(self, workspace):
        os.environ["MCP_WORKSPACE"] = str(workspace)
        from session_state import save_session_state

        save_session_state(
            CODEX_COMMON["session_id"],
            {"pending_delegation": True, "delegation_agent_type": "chain-executor"},
        )

    def test_bash_denied_while_delegation_pending(self, workspace):
        self._seed_pending(workspace)
        payload = {
            **CODEX_COMMON,
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_use_id": "tu-2",
            "tool_input": {"command": "echo hi"},
        }
        result = run_adapter("delegation-enforce.py", payload, workspace)
        assert result.returncode == 0
        out = stdout_json(result)
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_subagent_spawn_remapped_to_task_and_allowed(self, workspace):
        self._seed_pending(workspace)
        payload = {
            **CODEX_COMMON,
            "hook_event_name": "PreToolUse",
            "tool_name": "collaborationspawn_agent",
            "tool_use_id": "tu-3",
            "tool_input": {"task_name": "compute_sum", "message": "opaque"},
        }
        result = run_adapter("delegation-enforce.py", payload, workspace)
        assert result.returncode == 0
        out = stdout_json(result)
        assert out.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"

    def test_no_pending_state_allows_bash(self, workspace):
        payload = {
            **CODEX_COMMON,
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_use_id": "tu-4",
            "tool_input": {"command": "echo hi"},
        }
        result = run_adapter("delegation-enforce.py", payload, workspace)
        assert result.returncode == 0
        out = stdout_json(result)
        assert out.get("hookSpecificOutput", {}).get("permissionDecision") != "deny"


class TestPostPromptEngine:
    def test_chain_response_tracked_without_error(self, workspace):
        payload = {
            **CODEX_COMMON,
            "hook_event_name": "PostToolUse",
            "tool_name": "mcp__codex-prompts__prompt_engine",
            "tool_use_id": "tu-5",
            "tool_input": {"command": ">>dev_workflow"},
            "tool_response": {
                "content": "Chain: chain-dev_workflow#1\n→ Progress 1/5\nNext: chain_id=\"chain-dev_workflow#1\""
            },
        }
        result = run_adapter("post-prompt-engine.py", payload, workspace)
        assert result.returncode == 0


class TestRalphContextTracker:
    def test_silent_without_active_session(self, workspace):
        payload = {
            **CODEX_COMMON,
            "hook_event_name": "PostToolUse",
            "tool_name": "apply_patch",
            "tool_use_id": "tu-6",
            "tool_input": {"command": "*** Begin Patch\n*** End Patch"},
            "tool_response": {"content": "ok"},
        }
        result = run_adapter("ralph-context-tracker.py", payload, workspace)
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestRalphStop:
    def test_allows_when_no_state(self, workspace):
        payload = {
            **CODEX_COMMON,
            "hook_event_name": "Stop",
            "stop_hook_active": False,
        }
        result = run_adapter("ralph-stop.py", payload, workspace)
        assert result.returncode == 0
        out = stdout_json(result)
        assert out.get("decision") != "block"

    def test_stop_hook_active_guard(self, workspace):
        payload = {
            **CODEX_COMMON,
            "hook_event_name": "Stop",
            "stop_hook_active": True,
        }
        result = run_adapter("ralph-stop.py", payload, workspace)
        assert result.returncode == 0
        out = stdout_json(result)
        assert out.get("decision") != "block"


class TestCompactRecovery:
    def test_no_state_exits_cleanly(self, workspace):
        payload = {
            **CODEX_COMMON,
            "hook_event_name": "SessionStart",
            "source": "compact",
        }
        result = run_adapter("compact-recovery.py", payload, workspace)
        assert result.returncode == 0


class TestSessionSkills:
    """The adapter injects protocol framing only — Codex natively enumerates
    ~/.codex/skills (measured 16.4KB <skills_instructions> on 0.146), so the
    upstream catalog would be duplication."""

    def _fake_home(self, tmp_path, with_skill=True):
        home = tmp_path / "home"
        skills = home / ".codex" / "skills"
        skills.mkdir(parents=True)
        if with_skill:
            skill = skills / "dev_workflow"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\ndescription: Development workflow with debug and planning phases\n---\n"
            )
        return home

    def test_startup_injects_protocol_framing(self, workspace, tmp_path):
        home = self._fake_home(tmp_path)
        payload = {**CODEX_COMMON, "hook_event_name": "SessionStart", "source": "startup"}
        result = run_adapter(
            "session-skills.py", payload, workspace, extra_env={"HOME": str(home)}
        )
        assert result.returncode == 0
        out = stdout_json(result)
        context = out["hookSpecificOutput"]["additionalContext"]
        assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        assert "Skills-first" in context
        # catalog suppressed: no per-skill /name enumeration
        assert "/dev_workflow" not in context

    def test_compact_source_stays_silent(self, workspace, tmp_path):
        home = self._fake_home(tmp_path)
        payload = {**CODEX_COMMON, "hook_event_name": "SessionStart", "source": "compact"}
        result = run_adapter(
            "session-skills.py", payload, workspace, extra_env={"HOME": str(home)}
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_empty_skills_dir_stays_silent(self, workspace, tmp_path):
        home = self._fake_home(tmp_path, with_skill=False)
        payload = {**CODEX_COMMON, "hook_event_name": "SessionStart", "source": "startup"}
        result = run_adapter(
            "session-skills.py", payload, workspace, extra_env={"HOME": str(home)}
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""


class TestCacheLayoutFallback:
    """Tier 2 finding: the plugin cache drops the hooks/lib symlink."""

    def test_adapters_resolve_lib_without_symlink(self, workspace, tmp_path):
        cache_root = tmp_path / "cache-plugin"
        cache_hooks = cache_root / "hooks"
        cache_hooks.mkdir(parents=True)
        for script in HOOKS_DIR.glob("*.py"):
            shutil.copy(script, cache_hooks / script.name)
        # node_modules present, hooks/lib symlink absent — as measured in
        # ~/.codex/plugins/cache on codex-cli 0.146
        (cache_root / "node_modules").symlink_to(REPO_ROOT / "node_modules")
        payload = {
            **CODEX_COMMON,
            "hook_event_name": "UserPromptSubmit",
            "prompt": "hello",
        }
        result = run_adapter("prompt-suggest.py", payload, workspace, hooks_dir=cache_hooks)
        assert result.returncode == 0
