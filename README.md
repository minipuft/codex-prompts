# codex-prompts

Codex CLI plugin for the [claude-prompts](https://github.com/minipuft/claude-prompts-mcp) MCP server: symbolic `>>` prompt commands, chain execution, quality gates, and autonomous verification (Ralph) loops, delivered through Codex lifecycle hooks.

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
    { "name": "codex-prompts", "description": "Dev build", "version": "0.1.3", "source": "./plugins/codex-prompts" }
  ]
}
EOF
codex plugin marketplace add ~/.codex/dev-marketplace
codex plugin add codex-prompts@codex-prompts-dev
```

Marketplace source paths must be marketplace-relative — an absolute `path` in the manifest is not resolved (measured on 0.146). Re-run `codex plugin add` after changing hook files; installs are cached copies, not live views.

## Prompt catalog configuration

The portable plugin default is the curated 26-prompt catalog bundled with its `claude-prompts` dependency. Mutable MCP state and logs are stored separately under the OS temporary directory (`/tmp/codex-prompts/server` on Linux).

To opt this user into a persistent catalog from another checkout, create `~/.config/codex-prompts/config.json` (`$XDG_CONFIG_HOME/codex-prompts/config.json` when `XDG_CONFIG_HOME` is set):

```json
{
  "resourcesPath": "/absolute/path/to/claude-prompts-mcp/server/resources"
}
```

Resource selection precedence is:

1. `MCP_RESOURCES_PATH`
2. The file named by `CODEX_PROMPTS_CONFIG_PATH`
3. The default user config above
4. The 26-prompt catalog bundled with the plugin

Configured paths must be absolute existing directories. Invalid explicit configuration fails startup with a path-specific error instead of silently changing the visible prompt inventory. This setting is user-global across Codex projects; Codex 0.146 does not expose reliable invoking-project context to plugin MCP children.

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
- **Plugin variables are not interpolated.** Codex 0.146 passed `${CLAUDE_PLUGIN_ROOT}` literally. The plugin therefore launches a relative `./bin/start-mcp.mjs` with `cwd: "."`, which Codex resolves to the installed plugin root.
- **MCP servers run inside a fixed Codex sandbox.** A child may write `/tmp` but not `~/.codex` or the plugin cache. The launcher sets `MCP_RUNTIME_ROOT` to the OS-temp runtime directory, while prompt resources are selected independently through the persistent user configuration described above.
- **Project context is unavailable to the MCP child.** Codex strips the invoking project path from this launch shape, so automatic per-project catalogs are not supported on 0.146. Use the explicit user config or `MCP_RESOURCES_PATH`.

## Development notes

- **Dependency wiring**: until `claude-prompts@3.1.0` is on npm, `package.json` points at a packed tarball in `vendor/` (gitignored). Produce it from a claude-prompts checkout with `cd server && npm pack --pack-destination ../../codex-prompts/vendor`, then `npm install` here. After publish, switch the dependency to `"claude-prompts": "^3.1.0"`.
- **Shared library**: `hooks/lib -> ../node_modules/claude-prompts/hooks/lib` (committed symlink, same pattern as gemini-prompts). Adapters must not duplicate lib logic.
- **Spawning gotcha**: `codex exec` reads the prompt from stdin and blocks if stdin is piped but never closed — spawned invocations must close stdin.
- **Workspace resolution**: hooks resolve the workspace via `CLAUDE_PLUGIN_ROOT` (Codex provides it as a compatibility alias) with `PLUGIN_ROOT` as the native fallback; both are handled by the shared `workspace.py`.
