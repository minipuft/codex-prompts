# codex-prompts

Codex CLI plugin for the [claude-prompts](https://github.com/minipuft/claude-prompts) MCP server: symbolic `>>` prompt commands, chain execution, quality gates, and autonomous verification (Ralph) loops, delivered through Codex lifecycle hooks.

This is the Codex CLI sibling of [gemini-prompts](https://github.com/minipuft/gemini-prompts) (Gemini CLI) and [opencode-prompts](https://github.com/minipuft/opencode-prompts) (OpenCode). The Python hook core is shared: `hooks/lib` is a symlink into the `claude-prompts` npm package, and each hook script here is a thin adapter over that shared library.

## Requirements

- **Codex CLI >= 0.117** (hooks shipped experimentally in v0.114; `UserPromptSubmit` in v0.116; `PreToolUse`/`PostToolUse` in v0.117). Developed and verified against v0.146.
- **Hooks are experimental and off by default.** Enable them in `~/.codex/config.toml`:

  ```toml
  [features]
  hooks = true
  ```

- **Not available on Windows** (Codex hooks limitation).
- Python 3.10+ on PATH (hooks are stdlib-only, no pip installs).
- Node.js >= 18.18.0 (runs the bundled MCP server).

## Install

### From the minipuft marketplace

Codex reads the same marketplace index as Claude Code (legacy-compatible `.claude-plugin/marketplace.json` — verified against codex-cli 0.146):

```bash
codex plugin marketplace add https://github.com/minipuft/minipuft-plugins.git
codex plugin add codex-prompts@minipuft
```

### From a local checkout (development)

codex-cli 0.146 has no path-based install — every install is marketplace-mediated, so a local checkout is served through a tiny local marketplace:

```bash
git clone https://github.com/minipuft/codex-prompts.git
cd codex-prompts && npm install

# one-time: local dev marketplace pointing at the checkout
mkdir -p ~/.codex/dev-marketplace/.claude-plugin ~/.codex/dev-marketplace/plugins
ln -s "$(pwd)" ~/.codex/dev-marketplace/plugins/codex-prompts
cat > ~/.codex/dev-marketplace/.claude-plugin/marketplace.json <<'EOF'
{
  "name": "codex-prompts-dev",
  "owner": { "name": "dev" },
  "plugins": [
    { "name": "codex-prompts", "description": "Dev build", "version": "0.1.0", "source": "./plugins/codex-prompts" }
  ]
}
EOF
codex plugin marketplace add ~/.codex/dev-marketplace
codex plugin add codex-prompts@codex-prompts-dev
```

Marketplace source paths must be marketplace-relative — an absolute `path` in the manifest is not resolved (measured on 0.146). Re-run `codex plugin add` after changing hook files; installs are cached copies, not live views.

## Trust the hooks (required once)

Installing a plugin does not trust its hooks. In a Codex session, run `/hooks`, review the codex-prompts entries, and enable them. Codex records trust against each hook's hash — updating the plugin re-requires review. For non-interactive automation only, `codex exec --dangerously-bypass-hook-trust` skips the check for a single invocation.

## What the hooks do

| Hook | Codex event | Behavior |
|------|-------------|----------|
| `prompt-suggest.py` | `UserPromptSubmit` | Detects `>>command` syntax and operators (`-->` chain, `==>` delegate, `::` gate, `@` framework, `#` style) and injects the exact `prompt_engine` call to run |
| `gate-enforce.py` | `PreToolUse` (`.*prompt_engine`) | Denies execution when a gate verdict is FAIL or a pending gate lacks a verdict |
| `delegation-enforce.py` | `PreToolUse` (`Bash\|apply_patch\|collaborationspawn_agent`) | While a `==>` delegation is pending, denies direct edits/commands and steers to subagent spawning |
| `post-prompt-engine.py` | `PostToolUse` (`.*prompt_engine`) | Tracks chain step/gate state and injects the imperative next-step directive |
| `ralph-context-tracker.py` | `PostToolUse` (`Bash\|apply_patch`) | Silent telemetry for active Ralph verification sessions |
| `ralph-stop.py` | `Stop` (timeout 120s) | Blocks turn end while a chain is unfinished or verification fails; feeds the reason back as the next turn |
| `compact-recovery.py` | `SessionStart` (`compact`) | Re-injects active chain state after compaction |
| `session-skills.py` | `SessionStart` (`startup\|resume`) | Injects the skill-first protocol reminder. Catalog-free by design: Codex natively enumerates `~/.codex/skills` in its `<skills_instructions>` injection (measured 16.4KB on 0.146), so only the framing Codex lacks is added |

Tool names above are Codex-verified: Codex emits Claude Code-compatible `tool_name` values (`Bash` with `tool_input.command`), `apply_patch` for patch edits, and `collaborationspawn_agent` for subagent spawns (multi_agent feature).

## Known divergences on codex-cli 0.146 (measured 2026-08-03)

- **`subagent-gate-enforce` is not ported.** Codex fires `SubagentStop` with the full Claude-compatible envelope (`agent_transcript_path`, `agent_type`, `stop_hook_active`), but the delegated task prompt is encrypted in `tool_input.message` and the transcript's inter-agent `NEW_TASK` payload block is empty — the `### Quality Gates` criteria the upstream hook parses are not recoverable in plaintext anywhere. Until Codex persists inter-agent payloads (or a session-state-based redesign is validated), delegated-step gate enforcement relies on the main-session `gate-enforce` + `ralph-stop` loop.
- **Plugin `.mcp.json` paths are not interpolated.** Codex registers the bundled server (`codex mcp list` shows it) but spawns it with the literal string `${CLAUDE_PLUGIN_ROOT}` in argv and env, an empty `CLAUDE_PLUGIN_ROOT` environment, and the *session* directory as cwd — plugin-relative paths cannot work. The bundled `.mcp.json` stays in place as the forward contract — it activates unchanged once Codex interpolates plugin variables.
- **MCP servers run inside a fixed Codex sandbox.** Measured on 0.146: an MCP server child may write the session workdir and `/tmp`, but not `~/.codex` (including the plugin cache), and `sandbox_workspace_write.writable_roots` additions are honored by the shell sandbox yet NOT by MCP children. `--dangerously-bypass-approvals-and-sandbox` lifts the restriction.
- **The packaged server currently writes state and logs package-relative** (`node_modules/claude-prompts/runtime-state/` + `logs/`), ignoring `MCP_WORKSPACE` — an upstream defect surfaced by this port's isolation testing. Every `prompt_engine` call performs such a write, so under the default sandbox the call fails even though startup and tool listing succeed.

  **Practical consequence** until the upstream `MCP_WORKSPACE` fix ships: a globally-registered server (`codex mcp add codex-prompts -- node <abs path>/node_modules/claude-prompts/dist/index.js --transport=stdio --client=codex`) works when the package directory is writable by the session — i.e. when your Codex session runs in the directory tree containing the server install, or when the sandbox is bypassed for automation. Verified end-to-end in isolation (global servers disabled): hooks + directive injection + `prompt_engine` round-trip all green under `--dangerously-bypass-approvals-and-sandbox`.

## Development notes

- **Dependency wiring**: until `claude-prompts@3.1.0` is on npm, `package.json` points at a packed tarball in `vendor/` (gitignored). Produce it from a claude-prompts checkout with `cd server && npm pack --pack-destination ../../codex-prompts/vendor`, then `npm install` here. After publish, switch the dependency to `"claude-prompts": "^3.1.0"`.
- **Shared library**: `hooks/lib -> ../node_modules/claude-prompts/hooks/lib` (committed symlink, same pattern as gemini-prompts). Adapters must not duplicate lib logic.
- **Spawning gotcha**: `codex exec` reads the prompt from stdin and blocks if stdin is piped but never closed — spawned invocations must close stdin.
- **Workspace resolution**: hooks resolve the workspace via `CLAUDE_PLUGIN_ROOT` (Codex provides it as a compatibility alias) with `PLUGIN_ROOT` as the native fallback; both are handled by the shared `workspace.py`.
