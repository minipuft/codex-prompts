#!/usr/bin/env node

/** Launch the bundled MCP server with mutable output in the OS temp workspace. */

import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { configureResourcesEnvironment } from './resource-config.mjs';

const runtimeWorkspace = join(tmpdir(), 'codex-prompts');
process.env.MCP_WORKSPACE ??= runtimeWorkspace;
process.env.MCP_RUNTIME_ROOT ??= join(runtimeWorkspace, 'server');
configureResourcesEnvironment();

await import('../node_modules/claude-prompts/dist/index.js');
