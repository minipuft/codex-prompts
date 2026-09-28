import { existsSync, readFileSync, statSync } from 'node:fs';
import { homedir } from 'node:os';
import { isAbsolute, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const BUNDLED_RESOURCES_PATH = fileURLToPath(
  new URL('../node_modules/claude-prompts/resources', import.meta.url),
);

function requireAbsolutePath(candidate, settingName) {
  if (typeof candidate !== 'string' || candidate.trim() === '') {
    throw new Error(`${settingName} must be a non-empty absolute path.`);
  }

  const normalized = candidate.trim();
  if (!isAbsolute(normalized)) {
    throw new Error(`${settingName} must be an absolute path: ${normalized}`);
  }
  return normalized;
}

function validateResourcesDirectory(candidate, settingName) {
  const resolved = requireAbsolutePath(candidate, settingName);
  if (!existsSync(resolved)) {
    throw new Error(`${settingName} does not exist: ${resolved}`);
  }
  if (!statSync(resolved).isDirectory()) {
    throw new Error(`${settingName} must identify a directory: ${resolved}`);
  }
  return resolved;
}

function resolveUserConfig(env, homeDirectory) {
  const explicitConfig = env.CODEX_PROMPTS_CONFIG_PATH?.trim();
  if (explicitConfig) {
    return {
      path: requireAbsolutePath(explicitConfig, 'CODEX_PROMPTS_CONFIG_PATH'),
      required: true,
    };
  }

  const configuredRoot = env.XDG_CONFIG_HOME?.trim();
  const configRoot = configuredRoot
    ? requireAbsolutePath(configuredRoot, 'XDG_CONFIG_HOME')
    : join(homeDirectory, '.config');
  return { path: join(configRoot, 'codex-prompts', 'config.json'), required: false };
}

function readConfiguredResourcesPath(config) {
  if (!existsSync(config.path)) {
    if (config.required) {
      throw new Error(`CODEX_PROMPTS_CONFIG_PATH does not exist: ${config.path}`);
    }
    return undefined;
  }

  let parsed;
  try {
    parsed = JSON.parse(readFileSync(config.path, 'utf8'));
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new Error(`Codex prompts config is not valid JSON (${config.path}): ${detail}`);
  }

  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error(`Codex prompts config must be a JSON object: ${config.path}`);
  }
  return parsed.resourcesPath;
}

export function resolveResourcesPath({
  env = process.env,
  homeDirectory = homedir(),
  bundledResourcesPath = BUNDLED_RESOURCES_PATH,
} = {}) {
  const explicitResources = env.MCP_RESOURCES_PATH?.trim();
  if (explicitResources) {
    return validateResourcesDirectory(explicitResources, 'MCP_RESOURCES_PATH');
  }

  const config = resolveUserConfig(env, homeDirectory);
  const configuredResources = readConfiguredResourcesPath(config);
  if (configuredResources !== undefined) {
    return validateResourcesDirectory(configuredResources, 'resourcesPath');
  }

  return validateResourcesDirectory(bundledResourcesPath, 'bundled resources path');
}

export function configureResourcesEnvironment(options) {
  const resourcesPath = resolveResourcesPath(options);
  process.env.MCP_RESOURCES_PATH = resourcesPath;
  return resourcesPath;
}
