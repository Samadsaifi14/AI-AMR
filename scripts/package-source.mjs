import fs from 'node:fs/promises';
import path from 'node:path';
import {zipSync} from 'fflate';

export async function packageSource(root, destination) {
  const names = ['README.md', 'AGENTS.md', 'pyproject.toml', 'requirements-local.lock.txt',
    'browser_bridge.py', 'package.json', 'package-lock.json', 'vercel.json', 'verify-runtime.mjs',
    'results/public_pilot/audit.json'];
  async function collect(directory) {
    for (const item of await fs.readdir(path.join(root, directory), {withFileTypes:true})) {
      if (['__pycache__', 'private', 'test-runtime'].includes(item.name)) continue;
      const name = directory + '/' + item.name;
      if (item.isDirectory()) await collect(name);
      else if (item.isFile() && !/\.(pyc|joblib|xml)$/.test(name)) names.push(name);
    }
  }
  for (const directory of ['.agents', '.specify', 'specs', 'amr_discovery', 'scripts', 'tests', 'configs', 'docs', 'web', 'data', 'results/audit_v07', 'results/framework_v09_source_reviewed', 'results/dynamic_v10_full_panel', 'results/dynamic_v10_full_validation']) {
    await collect(directory);
  }
  const files = {};
  for (const name of names.sort()) {
    files[name] = [new Uint8Array(await fs.readFile(path.join(root, name))),
      {mtime:new Date('2026-01-01T00:00:00Z')}];
  }
  await fs.writeFile(destination, zipSync(files, {level:6}));
  console.log(`Packaged ${names.length} current source/resource files.`);
}
