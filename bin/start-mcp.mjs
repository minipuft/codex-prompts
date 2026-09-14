#!/usr/bin/env node

/** Launch the bundled MCP server with mutable output in the OS temp workspace. */

import { configureResourcesEnvironment } from './resource-config.mjs';
import { configureRuntimeWorkspace } from './workspace-config.mjs';

configureRuntimeWorkspace();
configureResourcesEnvironment();

await import('../node_modules/claude-prompts/dist/index.js');
