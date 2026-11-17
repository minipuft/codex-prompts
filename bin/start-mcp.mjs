#!/usr/bin/env node

/** Launch the bundled MCP server with mutable output in the OS temp workspace. */

import { configureResourcesEnvironment } from './resource-config.mjs';
import { configureRuntimeWorkspace, resolveRuntimeWorkspace } from './workspace-config.mjs';

try {
  const runtimeWorkspace = resolveRuntimeWorkspace();
  configureRuntimeWorkspace();
  configureResourcesEnvironment({ runtimeWorkspace });
} catch (error) {
  process.stderr.write(`codex-prompts: ${error instanceof Error ? error.message : String(error)}\n`);
  process.exit(1);
}

await import('../node_modules/claude-prompts/dist/index.js');
