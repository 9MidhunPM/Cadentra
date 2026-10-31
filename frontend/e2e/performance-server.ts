/** Test-only native static server. Never starts an API, database, or protocol mock. */
import { createHash } from 'node:crypto'
import { spawn, spawnSync, execFileSync } from 'node:child_process'
import { accessSync, constants, existsSync, mkdtempSync, readFileSync, readdirSync, lstatSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:net'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

export const PERFORMANCE_ORIGIN = 'http://127.0.0.1:8080'
export const digest = (value: string | Buffer) => createHash('sha256').update(value).digest('hex')
export function tmpPath(value: string | undefined, label: string) {
  if (!value || !resolve(value).startsWith(`/tmp${sep}`)) throw new Error(`${label} must be under /tmp`)
  return resolve(value)
}
export function checkedOrigin(value = process.env.CADENTRA_PERFORMANCE_ORIGIN || PERFORMANCE_ORIGIN) {
  if (value !== PERFORMANCE_ORIGIN) throw new Error('T30 requires the explicit loopback origin http://127.0.0.1:8080')
  return value
}
export function readManifest(path: string) {
  const filename = tmpPath(path, 'Private fixture manifest')
  const info = lstatSync(filename)
  if (dirname(filename) !== '/tmp' || !info.isFile() || info.isSymbolicLink() || (info.mode & 0o7777) !== 0o600
      || info.uid !== process.getuid?.()) throw new Error('Private fixture manifest must be a directly owned mode0600 file under/tmp')
  const manifest = JSON.parse(readFileSync(filename, 'utf8'))
  if (manifest.test_only !== true || manifest.kind !== 'T30' || manifest.state !== 'ready' || manifest.database !== 'cadentra_performance_test'
      || !/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(manifest.run || '')
      || !/^t30_[a-f0-9]{32}$/.test(manifest.schema || '')
      || manifest.schema.slice(4) !== String(manifest.run).replaceAll('-', '')) {
    throw new Error('Require the new isolated performance database and matching per-run schema manifest')
  }
  return manifest
}
function walk(root: string, directory: string, output: Record<string, string>) {
  if (!existsSync(directory)) throw new Error(`Missing runtime input directory: ${relative(root, directory)}`)
  for (const entry of readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (entry.name === '__pycache__' || entry.name.startsWith('.env')) continue
    const path = join(directory, entry.name)
    if (entry.isSymbolicLink()) throw new Error('Runtime input hashes must not follow symbolic links')
    if (entry.isDirectory()) walk(root, path, output)
    else if (entry.isFile()) output[relative(root, path)] = digest(readFileSync(path))
  }
}
export function runtimeInputs(repo: string) {
  const source: Record<string, string> = {}
  walk(repo, join(repo, 'frontend/src'), source)
  walk(repo, join(repo, 'backend/app'), source)
  for (const file of ['frontend/package.json', 'frontend/package-lock.json', 'frontend/vite.config.ts',
    'frontend/index.html', 'frontend/nginx.conf', 'backend/pyproject.toml', 'backend/uv.lock']) {
    source[file] = digest(readFileSync(join(repo, file)))
  }
  const dist: Record<string, string> = {}
  walk(join(repo, 'frontend/dist'), join(repo, 'frontend/dist'), dist)
  const harness: Record<string, string> = {}
  for (const file of ['frontend/e2e/performance.ts', 'frontend/e2e/performance-server.ts', 'frontend/playwright.performance.config.ts',
    'backend/tests/reporting/live_app.py', 'backend/tests/reporting/performance_fixture.py', 'backend/tests/reporting/fixture_database.py']) {
    harness[file] = digest(readFileSync(join(repo, file)))
  }
  return { source, source_sha256: digest(JSON.stringify(source)), dist, dist_sha256: digest(JSON.stringify(dist)),
    harness, harness_sha256: digest(JSON.stringify(harness)) }
}
export type NativeEvidence = {
  test_only: true; serving: 'native-nginx-static'; origin: string; api_origin: string;
  database: string; schema: string; dataset_run: string; commit: string; working_tree_dirty: boolean;
  inputs: ReturnType<typeof runtimeInputs>; nginx_config_sha256: string; adapted_config_sha256: string;
  native_versions: { nginx: string; node: string }; nginx_binary_sha256: string;
  server_files: { directory: string; wrapper: string; adapted_config: string; error_log: string };
  adaptations: string[]; docker_verified: false; server_stopped?: boolean;
}
function nginxPath(path: string) {
  if (/["\r\n\\]/.test(path)) throw new Error('Unsafe native NGINX pathname')
  return `"${path}"`
}
async function main() {
  if (process.env.APP_ENV !== 'test') throw new Error('Native benchmark runner requires APP_ENV=test')
  const manifest = readManifest(process.env.CADENTRA_PERFORMANCE_CREDENTIALS || '')
  const metadataPath = tmpPath(process.env.CADENTRA_PERFORMANCE_SERVER_METADATA, 'Server metadata')
  if (existsSync(metadataPath)) throw new Error('Use a new server metadata filename; preserve earlier evidence')
  const origin = checkedOrigin()
  const apiOrigin = process.env.CADENTRA_PERFORMANCE_API_ORIGIN || 'http://127.0.0.1:8004'
  if (apiOrigin !== 'http://127.0.0.1:8004') throw new Error('Real T30 API must use its assigned loopback port8004')
  const binary = tmpPath(process.env.CADENTRA_PERFORMANCE_NGINX, 'Task-owned NGINX binary')
  accessSync(binary, constants.X_OK)
  const version = spawnSync(binary, ['-v'], { encoding: 'utf8' })
  if (version.status !== 0 || !`${version.stdout}${version.stderr}`.includes('nginx/1.30.6')) {
    throw new Error('Require the reviewed native NGINX1.30.6 binary')
  }
  const frontend = dirname(dirname(fileURLToPath(import.meta.url)))
  const repo = dirname(frontend)
  const sourceBefore: Record<string, string> = {}
  walk(repo, join(repo, 'frontend/src'), sourceBefore)
  walk(repo, join(repo, 'backend/app'), sourceBefore)
  const build = spawnSync('npm', ['run', 'build'], { cwd: frontend, stdio: 'inherit' })
  if (build.status !== 0) throw new Error('Production asset build failed')
  const sourceAfter: Record<string, string> = {}
  walk(repo, join(repo, 'frontend/src'), sourceAfter)
  walk(repo, join(repo, 'backend/app'), sourceAfter)
  if (JSON.stringify(sourceBefore) !== JSON.stringify(sourceAfter)) throw new Error('Runtime source changed during build')
  // Preserve any existing port owner. No process discovery, shutdown or port takeover.
  await new Promise<void>((done, reject) => {
    const probe = createServer()
    probe.once('error', reject)
    probe.listen(8080, '127.0.0.1', () => probe.close(error => error ? reject(error) : done()))
  })
  const temporary = mkdtempSync('/tmp/cadentra-t30-nginx-')
  const mime = resolve(dirname(binary), '../conf/mime.types')
  accessSync(mime, constants.R_OK)
  const sourceConfig = readFileSync(join(frontend, 'nginx.conf'), 'utf8')
  for (const expected of ['listen 8080;', 'root /usr/share/nginx/html;', 'server api:8001 resolve;']) {
    if (!sourceConfig.includes(expected)) throw new Error(`Reviewed server configuration changed: ${expected}`)
  }
  const adapted = sourceConfig.replace('listen 8080;', 'listen 127.0.0.1:8080;')
    .replace('root /usr/share/nginx/html;', `root ${nginxPath(join(frontend, 'dist'))};`)
    .replace('server api:8001 resolve;', 'server 127.0.0.1:8004;')
    .replace(/\s*resolver 127\.0\.0\.11 valid=10s ipv6=off;/, '')
  const serverConfig = join(temporary, 'server.conf')
  writeFileSync(serverConfig, adapted)
  const config = join(temporary, 'nginx.conf')
  const log = join(temporary, 'error.log')
  writeFileSync(config, `worker_processes 1;
pid ${nginxPath(join(temporary, 'nginx.pid'))};
error_log ${nginxPath(log)} warn;
events { worker_connections 256; }
http {
  include ${nginxPath(mime)};
  client_body_temp_path ${nginxPath(join(temporary, 'client'))};
  proxy_temp_path ${nginxPath(join(temporary, 'proxy'))};
  fastcgi_temp_path ${nginxPath(join(temporary, 'fastcgi'))};
  uwsgi_temp_path ${nginxPath(join(temporary, 'uwsgi'))};
  scgi_temp_path ${nginxPath(join(temporary, 'scgi'))};
  include ${nginxPath(serverConfig)};
}
`)
  const syntax = spawnSync(binary, ['-t', '-p', temporary, '-c', config, '-e', log], { stdio: 'inherit' })
  if (syntax.status !== 0) throw new Error('Native NGINX configuration validation failed')
  const child = spawn(binary, ['-p', temporary, '-c', config, '-e', log, '-g', 'daemon off;'], { stdio: 'inherit' })
  const stop = () => { if (child.exitCode === null) child.kill('SIGTERM') }
  process.once('SIGINT', stop)
  process.once('SIGTERM', stop)
  try {
    const indexHash = digest(readFileSync(join(frontend, 'dist/index.html')))
    const deadline = Date.now() + 10_000
    while (true) {
      if (child.exitCode !== null) throw new Error('Owned NGINX exited before readiness')
      try {
        const response = await fetch(origin, { signal: AbortSignal.timeout(1000) })
        if (response.status !== 200 || digest(Buffer.from(await response.arrayBuffer())) !== indexHash) {
          throw new Error('Port8080 did not serve this exact production build')
        }
        break
      } catch (error) {
        if (Date.now() >= deadline) throw error
        await new Promise(resolve => setTimeout(resolve, 100))
      }
    }
    const metadata: NativeEvidence = {
      test_only: true, serving: 'native-nginx-static', origin, api_origin: apiOrigin,
      database: manifest.database, schema: manifest.schema, dataset_run: manifest.run,
      commit: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: repo, encoding: 'utf8' }).trim(),
      working_tree_dirty: Boolean(execFileSync('git', ['status', '--porcelain'], { cwd: repo, encoding: 'utf8' }).trim()),
      inputs: runtimeInputs(repo), nginx_config_sha256: digest(sourceConfig), adapted_config_sha256: digest(adapted),
      native_versions: { nginx: `${version.stdout}${version.stderr}`.trim(), node: process.version },
      nginx_binary_sha256: digest(readFileSync(binary)), docker_verified: false,
      server_files: { directory: temporary, wrapper: config, adapted_config: serverConfig, error_log: log },
      adaptations: ['Static root points to this production dist; listener restricted to loopback8080.',
        'Upstream api:8001 and Docker DNS resolution replaced with the real test API at127.0.0.1:8004.',
        'Task-local wrapper supplies MIME/PID/log/temp paths; production routing/cache/header directives preserved.'],
    }
    writeFileSync(metadataPath, JSON.stringify(metadata, null, 2), { flag: 'wx' })
    console.log(`Native static benchmark server ready at ${origin}; database namespace ${manifest.schema}`)
    await new Promise<void>(resolve => child.once('exit', () => resolve()))
    writeFileSync(metadataPath, JSON.stringify({ ...metadata, server_stopped: true }, null, 2))
  } finally {
    stop()
    process.removeListener('SIGINT', stop)
    process.removeListener('SIGTERM', stop)
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main()
