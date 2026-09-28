import { mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

/**
 * Decide the runtime workspace path without touching the filesystem.
 *
 * `MCP_WORKSPACE` unset -> the OS temp workspace, marked as the default so the
 * caller knows it is safe to create. `MCP_WORKSPACE` set by the user -> that
 * path verbatim, left untouched: a missing user-set path must still reach the
 * engine and be refused there.
 */
export function resolveRuntimeWorkspace({ env = process.env, tmpDirectory = tmpdir() } = {}) {
  const isDefault = env.MCP_WORKSPACE == null;
  const path = env.MCP_WORKSPACE ?? join(tmpDirectory, 'codex-prompts');
  return { path, isDefault };
}

/**
 * Apply the workspace decision: create the default temp workspace so a
 * strict engine (claude-prompts >=5.0.0) can start, but never create a
 * user-set path. `MCP_RUNTIME_ROOT` is set for the default case but never
 * pre-created -- the engine creates it on demand.
 */
export function configureRuntimeWorkspace({
  env = process.env,
  tmpDirectory = tmpdir(),
  mkdir = mkdirSync,
} = {}) {
  const { path: runtimeWorkspace, isDefault } = resolveRuntimeWorkspace({ env, tmpDirectory });
  if (isDefault) {
    mkdir(runtimeWorkspace, { recursive: true });
  }
  env.MCP_WORKSPACE ??= runtimeWorkspace;
  env.MCP_RUNTIME_ROOT ??= join(runtimeWorkspace, 'server');
  return runtimeWorkspace;
}
