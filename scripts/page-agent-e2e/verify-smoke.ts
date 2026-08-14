import { existsSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { validateTaskFileWithErrors } from './task-schema.ts';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, '../..');

const checks: Array<{ name: string; check: () => boolean; message: string }> = [
  {
    name: 'YAML schema validation',
    check: () => {
      const smokeFile = resolve(projectRoot, 'tests/tools/page-agent/smoke.yaml');
      if (!existsSync(smokeFile)) return false;
      const result = validateTaskFileWithErrors(smokeFile);
      return result.success;
    },
    message: 'tests/tools/page-agent/smoke.yaml passes Zod schema validation',
  },
  {
    name: 'Runner script exists',
    check: () => existsSync(resolve(__dirname, 'page-agent-runner.ts')),
    message: 'scripts/page-agent-e2e/page-agent-runner.ts exists',
  },
  {
    name: 'Config module exists',
    check: () => existsSync(resolve(__dirname, 'config.ts')),
    message: 'config.ts module exists',
  },
  {
    name: 'Reports directory exists',
    check: () => existsSync(resolve(projectRoot, 'reports/page-agent-e2e')),
    message: 'reports/page-agent-e2e/ directory exists',
  },
  {
    name: 'Logs directory exists',
    check: () => existsSync(resolve(projectRoot, 'logs/page-agent-e2e')),
    message: 'logs/page-agent-e2e/ directory exists',
  },
  {
    name: 'No secrets in smoke.yaml',
    check: () => {
      const smokeFile = resolve(projectRoot, 'tests/tools/page-agent/smoke.yaml');
      if (!existsSync(smokeFile)) return true;
      const content = readFileSync(smokeFile, 'utf-8');
      const secretPatterns = [/Bearer\s+[A-Za-z0-9\-._~+/]+=*/i, /sk-[a-zA-Z0-9]+/, /password:\s*\S+/i];
      return !secretPatterns.some((p) => p.test(content));
    },
    message: 'No hardcoded secrets in smoke.yaml',
  },
];

console.log('\n🔍 PageAgent E2E Verification\n');

let allPassed = true;
for (const { name, check, message } of checks) {
  const passed = check();
  const icon = passed ? '✅' : '❌';
  console.log(`  ${icon} ${name}: ${message}`);
  if (!passed) allPassed = false;
}

console.log(`\n${allPassed ? '✅ All checks passed' : '❌ Some checks failed'}\n`);
process.exit(allPassed ? 0 : 1);
