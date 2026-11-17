import { existsSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { isAbsolute, join } from 'node:path';

/** The file the server reads as the profile's config (claude-prompts >=6, `paths.resources`). */
const PROFILE_CONFIG_FILE = 'config.jsonc';

/** First line of a profile config this launcher wrote, so it only ever removes its own file. */
const PROFILE_CONFIG_MARKER = '// Written by codex-prompts at every start';

const REMOVED_RESOURCES_VARIABLE =
  'MCP_RESOURCES_PATH is no longer read by claude-prompts; unset it, then set MCP_WORKSPACE to a profile folder holding resources/<type>/, or set resourcesPath in ~/.config/codex-prompts/config.json.';

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

/**
 * Decide which prompt catalog the server serves, without touching the filesystem.
 *
 * A user-set `MCP_WORKSPACE` is the user's own profile and wins outright: the codex-prompts
 * config is not read. Otherwise `resourcesPath` from that config selects a catalog folder, and
 * with neither the server's bundled catalog applies.
 */
export function resolveResourceSelection({
  env = process.env,
  homeDirectory = homedir(),
  runtimeWorkspace,
}) {
  const removed = env.MCP_RESOURCES_PATH;
  if (removed !== undefined && removed !== '') {
    throw new Error(REMOVED_RESOURCES_VARIABLE);
  }
  if (!runtimeWorkspace.isDefault) {
    return { source: 'workspace', profile: runtimeWorkspace.path };
  }

  const config = resolveUserConfig(env, homeDirectory);
  const configuredResources = readConfiguredResourcesPath(config);
  if (configuredResources !== undefined) {
    return {
      source: 'configured',
      profile: runtimeWorkspace.path,
      resourcesPath: validateResourcesDirectory(configuredResources, 'resourcesPath'),
      configPath: config.path,
    };
  }
  return { source: 'bundled', profile: runtimeWorkspace.path };
}

function renderProfileConfig({ resourcesPath, configPath }) {
  const paths = JSON.stringify({ resources: [resourcesPath] }, null, 2).replace(/\n/g, '\n  ');
  return [
    `${PROFILE_CONFIG_MARKER} from resourcesPath in ${configPath}; edit that file, not this one.`,
    '{',
    '  "version": 5,',
    `  "paths": ${paths}`,
    '}',
    '',
  ].join('\n');
}

function removeOwnProfileConfig(path) {
  if (!existsSync(path)) return;
  if (readFileSync(path, 'utf8').startsWith(PROFILE_CONFIG_MARKER)) {
    rmSync(path);
  }
}

/**
 * Apply the selection to the launcher's own profile, the default runtime workspace that
 * `MCP_WORKSPACE` already names for the child server.
 *
 * `configured` writes that profile's `config.jsonc` listing the folder in `paths.resources`, so it
 * is served in place of the bundled catalog. `bundled` removes a config this launcher wrote
 * earlier, so a deleted `resourcesPath` stops being served. `workspace` writes nothing: the
 * folder belongs to the user.
 */
export function configureResourcesEnvironment({
  env = process.env,
  homeDirectory = homedir(),
  runtimeWorkspace,
}) {
  const selection = resolveResourceSelection({ env, homeDirectory, runtimeWorkspace });
  const profileConfig = join(selection.profile, PROFILE_CONFIG_FILE);
  if (selection.source === 'configured') {
    writeFileSync(profileConfig, renderProfileConfig(selection));
  } else if (selection.source === 'bundled') {
    removeOwnProfileConfig(profileConfig);
  }
  return selection;
}
