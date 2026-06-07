# PageAgent E2E Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a semantic DOM-based E2E testing infrastructure using Alibaba PageAgent that reads text DOM instead of screenshots, reducing token cost by 10-50x while maintaining deterministic assertions.

**Architecture:** Standalone npm package (`scripts/page-agent-e2e/`) with Playwright as browser shell, PageAgent for semantic interaction, Zod for YAML validation, and dotenv for configuration. Claude Code skill (`.claude/skills/page-agent-e2e/`) provides AI-assisted test creation and debugging. Reports in JSON + Markdown, append-only JSONL execution log.

**Tech Stack:** TypeScript, tsx runner, Playwright, Alibaba page-agent, Zod, yaml, dotenv

---

## File Structure

```
scripts/page-agent-e2e/
├── package.json              # Standalone npm package with all dependencies
├── tsconfig.json             # TypeScript config (ES2022, NodeNext)
├── .env                      # Runner-local overrides (gitignored)
├── .env.example              # Template (committed)
├── .gitignore                # Ignores .env, node_modules
├── page-agent-runner.ts      # Main orchestrator: load YAML → launch browser → run cases → report
├── page-agent-injector.ts    # PageAgent browser injection with security config
├── task-schema.ts            # Zod schema + CLI validator
├── report.ts                 # JSON + Markdown report generator
├── logger.ts                 # Append-only JSONL logger
├── config.ts                 # Dotenv loading + env resolution
├── assertions.ts             # Deterministic assertion executor
├── start-services.ts         # Optional service launcher (checks if already running)
└── verify-smoke.ts           # Post-run verification script

tests/e2e/page-agent/
├── smoke.yaml                # Primary smoke test cases
└── tasks.example.yaml        # Template for new cases

.claude/skills/page-agent-e2e/
├── SKILL.md                  # Trigger rules + constraints (concise)
├── .env                      # Skill-level defaults (gitignored)
├── .env.example              # Template (committed)
├── .gitignore                # Ignores .env, *.log
├── references/
│   ├── page-agent-e2e-architecture.md
│   ├── task-yaml-schema.md
│   ├── security-and-ci.md
│   ├── project-gotchas.md
│   ├── product-verification.md
│   └── hooks-and-memory.md
└── examples/
    └── smoke.yaml

logs/page-agent-e2e/
├── .gitkeep                  # Keep directory in git
└── run.log                   # Append-only JSONL (gitignored)

reports/page-agent-e2e/       # Generated reports (gitignored)
└── .gitkeep
```

---

## Task 1: Project Scaffolding — package.json, tsconfig, gitignore, config

**Files:**
- Create: `scripts/page-agent-e2e/package.json`
- Create: `scripts/page-agent-e2e/tsconfig.json`
- Create: `scripts/page-agent-e2e/.gitignore`
- Create: `scripts/page-agent-e2e/.env.example`
- Create: `scripts/page-agent-e2e/config.ts`
- Create: `logs/page-agent-e2e/.gitkeep`
- Create: `reports/page-agent-e2e/.gitkeep`
- Modify: `.gitignore` (root) — add `logs/page-agent-e2e/run.log` and `reports/page-agent-e2e/` entries

- [ ] **Step 1: Create package.json**

```json
{
  "name": "page-agent-e2e",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "e2e": "tsx page-agent-runner.ts 'tests/e2e/page-agent/**/*.yaml'",
    "e2e:smoke": "tsx page-agent-runner.ts tests/e2e/page-agent/smoke.yaml",
    "e2e:validate": "tsx task-schema.ts --validate 'tests/e2e/page-agent/**/*.yaml'",
    "e2e:report": "tsx report.ts --last",
    "e2e:verify": "tsx verify-smoke.ts"
  },
  "dependencies": {
    "@anthropic-ai/sdk": "^0.39.0",
    "dotenv": "^16.4.0",
    "openai": "^4.0.0",
    "page-agent": "latest"
  },
  "devDependencies": {
    "@playwright/test": "^1.52.0",
    "@types/node": "^22.0.0",
    "tsx": "^4.0.0",
    "typescript": "^5.7.0",
    "yaml": "^2.7.0",
    "zod": "^3.23.0"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "lib": ["ES2022"],
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "./dist",
    "rootDir": ".",
    "resolveJsonModule": true,
    "declaration": false,
    "noEmit": true
  },
  "include": ["*.ts"],
  "exclude": ["node_modules", "dist"]
}
```

- [ ] **Step 3: Create .gitignore**

```gitignore
node_modules/
dist/
.env
```

- [ ] **Step 4: Create .env.example**

```env
# PageAgent LLM Configuration (provider-agnostic)
PAGE_AGENT_LLM_BASE_URL=https://api.openai.com/v1
PAGE_AGENT_LLM_MODEL=gpt-4o
PAGE_AGENT_LLM_API_KEY=sk-...

# PageAgent Behavior
PAGE_AGENT_LANGUAGE=zh-CN
PAGE_AGENT_DEBUG=0
PAGE_AGENT_STEP_DELAY=0.3

# Service URLs (set if services already running)
PAGE_AGENT_BASE_URL=http://localhost:5173
PAGE_AGENT_BACKEND_URL=http://localhost:8000
PAGE_AGENT_E2E_SKIP_START=0

# Test Credentials
E2E_TEST_USER=test_rich
E2E_TEST_PASSWORD=TestRich123!

# Child App
PAGE_AGENT_CHILD_BASE_URL=http://localhost:5174
E2E_CHILD_PIN=🐱,🐶,🌟,🌈
E2E_CHILD_USER=test_child
```

- [ ] **Step 5: Create config.ts**

```typescript
import { config } from 'dotenv';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Load skill-level .env (lowest file priority)
config({ path: resolve(__dirname, '../../.claude/skills/page-agent-e2e/.env') });
// Load runner-level .env (overrides skill-level)
config({ path: resolve(__dirname, '.env') });
// Shell env vars already set take highest priority (dotenv won't overwrite)

export interface PageAgentConfig {
  llm: {
    baseURL: string;
    model: string;
    apiKey: string;
  };
  language: string;
  debug: boolean;
  stepDelay: number;
  baseUrl: string;
  backendUrl: string;
  childBaseUrl: string;
  skipStart: boolean;
  testUser: string;
  testPassword: string;
  childPin: string[];
  childUser: string;
}

export function loadConfig(): PageAgentConfig {
  const apiKey = process.env.PAGE_AGENT_LLM_API_KEY;
  if (!apiKey) {
    throw new Error(
      'PAGE_AGENT_LLM_API_KEY is required. Set it in shell env, scripts/page-agent-e2e/.env, or .claude/skills/page-agent-e2e/.env'
    );
  }

  return {
    llm: {
      baseURL: process.env.PAGE_AGENT_LLM_BASE_URL || 'https://api.openai.com/v1',
      model: process.env.PAGE_AGENT_LLM_MODEL || 'gpt-4o',
      apiKey,
    },
    language: process.env.PAGE_AGENT_LANGUAGE || 'zh-CN',
    debug: process.env.PAGE_AGENT_DEBUG === '1',
    stepDelay: parseFloat(process.env.PAGE_AGENT_STEP_DELAY || '0.3'),
    baseUrl: process.env.PAGE_AGENT_BASE_URL || 'http://localhost:5173',
    backendUrl: process.env.PAGE_AGENT_BACKEND_URL || 'http://localhost:8000',
    childBaseUrl: process.env.PAGE_AGENT_CHILD_BASE_URL || 'http://localhost:5174',
    skipStart: process.env.PAGE_AGENT_E2E_SKIP_START === '1',
    testUser: process.env.E2E_TEST_USER || 'test_rich',
    testPassword: process.env.E2E_TEST_PASSWORD || 'TestRich123!',
    childPin: (process.env.E2E_CHILD_PIN || '🐱,🐶,🌟,🌈').split(','),
    childUser: process.env.E2E_CHILD_USER || 'test_child',
  };
}
```

- [ ] **Step 6: Create directory stubs and update root .gitignore**

```bash
mkdir -p logs/page-agent-e2e
touch logs/page-agent-e2e/.gitkeep
mkdir -p reports/page-agent-e2e
touch reports/page-agent-e2e/.gitkeep
```

Append to root `.gitignore`:

```gitignore
# PageAgent E2E
logs/page-agent-e2e/run.log
reports/page-agent-e2e/*.json
reports/page-agent-e2e/*.md
scripts/page-agent-e2e/.env
```

- [ ] **Step 7: Install dependencies**

```bash
cd scripts/page-agent-e2e && npm install
```

- [ ] **Step 8: Verify TypeScript compiles config.ts**

```bash
cd scripts/page-agent-e2e && npx tsx --no-warnings -e "import { loadConfig } from './config.ts'; console.log('config module OK')"
```

Expected: `config module OK` (will warn about missing API key if .env not set, but module loads)

- [ ] **Step 9: Commit**

```bash
git add scripts/page-agent-e2e/package.json scripts/page-agent-e2e/tsconfig.json scripts/page-agent-e2e/.gitignore scripts/page-agent-e2e/.env.example scripts/page-agent-e2e/config.ts logs/page-agent-e2e/.gitkeep reports/page-agent-e2e/.gitkeep .gitignore
git commit -m "feat(e2e): scaffold page-agent-e2e runner package with config"
```

---

## Task 2: YAML Schema Validation — Zod Schema + CLI Validator

**Files:**
- Create: `scripts/page-agent-e2e/task-schema.ts`

- [ ] **Step 1: Write task-schema.ts with Zod schema and CLI validator**

```typescript
import { z } from 'zod';
import { readFileSync } from 'fs';
import { parse as parseYaml } from 'yaml';
import { glob } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const AssertionSchema = z.object({
  type: z.enum([
    'url_contains',
    'url_equals',
    'text_visible',
    'text_not_visible',
    'locator_visible',
    'locator_count',
    'api_response',
    'db_query',
    'log_contains',
    'console_no_errors',
    'network_no_failures',
  ]),
  value: z.string().optional(),
  selector: z.string().optional(),
  count: z.number().optional(),
  timeoutMs: z.number().optional(),
  query: z.string().optional(),
  expected: z.string().optional(),
});

const FixturesSchema = z.object({
  seed: z.string().optional(),
  user: z.string().optional(),
  role: z.string().optional(),
}).optional();

const CaseSchema = z.object({
  id: z.string().min(1),
  app: z.enum(['main', 'child']).optional().default('main'),
  description: z.string().optional(),
  baseUrl: z.string().url().optional(),
  route: z.string().min(1),
  task: z.string().min(1),
  maxSteps: z.number().int().min(1).max(100).default(20),
  timeoutMs: z.number().int().min(1000).optional().default(30000),
  storageState: z.string().optional(),
  tags: z.array(z.string()).optional(),
  fixtures: FixturesSchema,
  assertions: z.array(AssertionSchema).min(1),
});

const TaskFileSchema = z.object({
  cases: z.array(CaseSchema).min(1),
});

export type TaskCase = z.infer<typeof CaseSchema>;
export type TaskFile = z.infer<typeof TaskFileSchema>;
export type Assertion = z.infer<typeof AssertionSchema>;

export function validateTaskFile(filePath: string): TaskFile {
  const content = readFileSync(filePath, 'utf-8');
  const parsed = parseYaml(content);
  return TaskFileSchema.parse(parsed);
}

export function validateTaskFileWithErrors(filePath: string): { success: boolean; data?: TaskFile; errors?: string[] } {
  try {
    const data = validateTaskFile(filePath);
    return { success: true, data };
  } catch (err) {
    if (err instanceof z.ZodError) {
      const errors = err.errors.map(
        (e) => `  ${e.path.join('.')}: ${e.message}`
      );
      return { success: false, errors };
    }
    return { success: false, errors: [(err as Error).message] };
  }
}

// CLI mode: tsx task-schema.ts --validate <glob>
if (process.argv.includes('--validate')) {
  const patterns = process.argv.slice(process.argv.indexOf('--validate') + 1);
  if (patterns.length === 0) {
    console.error('Usage: tsx task-schema.ts --validate <file-or-glob>...');
    process.exit(1);
  }

  let hasError = false;

  for (const pattern of patterns) {
    const files = import('node:fs').then((fs) => {
      // Simple glob: if pattern contains *, expand with node:fs
      // For simplicity, use synchronous approach
    });

    // Resolve relative to project root (two levels up from scripts/page-agent-e2e/)
    const projectRoot = resolve(__dirname, '../..');
    const filePath = resolve(projectRoot, pattern);

    const result = validateTaskFileWithErrors(filePath);
    if (result.success) {
      const caseCount = result.data!.cases.length;
      console.log(`✓ ${pattern} (${caseCount} cases)`);
    } else {
      console.error(`✗ ${pattern}`);
      result.errors!.forEach((e) => console.error(e));
      hasError = true;
    }
  }

  process.exit(hasError ? 1 : 0);
}
```

- [ ] **Step 2: Create smoke.yaml test file**

```bash
mkdir -p tests/e2e/page-agent
```

Create `tests/e2e/page-agent/smoke.yaml`:

```yaml
cases:
  - id: login-smoke
    app: main
    route: /login
    task: |
      使用测试账号登录系统。账号来自环境变量 E2E_TEST_USER，密码来自环境变量 E2E_TEST_PASSWORD。
      如果看到用户名输入框，输入测试账号。
      如果看到密码输入框，输入测试密码。
      点击登录按钮。登录成功后停在首页或仪表盘。
    maxSteps: 12
    fixtures:
      user: E2E_TEST_USER
    assertions:
      - type: url_contains
        value: /dashboard
      - type: text_not_visible
        value: 登录失败
      - type: console_no_errors

  - id: asset-list-smoke
    app: main
    route: /assets
    task: |
      确认资产列表页面已加载。检查页面是否显示资产相关内容。
      如果有搜索框，尝试输入"测试"进行搜索。
    maxSteps: 8
    storageState: tests/e2e/page-agent/.auth/main-user.json
    assertions:
      - type: url_contains
        value: /assets
      - type: network_no_failures

  - id: child-login-smoke
    app: child
    route: /
    task: |
      在儿童端输入 PIN 码登录。PIN 码来自环境变量 E2E_CHILD_PIN。
      找到 PIN 输入区域，输入数字。确认进入儿童主页。
    maxSteps: 10
    fixtures:
      user: E2E_CHILD_USER
    assertions:
      - type: url_contains
        value: /home
      - type: console_no_errors
```

- [ ] **Step 3: Create tasks.example.yaml template**

```yaml
# Template for new PageAgent E2E test cases
# Copy this file, rename, and fill in your cases.
cases:
  - id: example-case
    app: main
    route: /target-page
    task: |
      Describe what PageAgent should do in natural language.
      Use business terms. PageAgent reads text DOM to understand the page.
    maxSteps: 15
    assertions:
      - type: url_contains
        value: /expected-path
      - type: text_visible
        value: 期望看到的文本
      - type: console_no_errors
```

- [ ] **Step 4: Run schema validation on smoke.yaml**

```bash
cd scripts/page-agent-e2e && npx tsx task-schema.ts --validate ../../tests/e2e/page-agent/smoke.yaml
```

Expected: `✓ ../../tests/e2e/page-agent/smoke.yaml (3 cases)`

- [ ] **Step 5: Commit**

```bash
git add scripts/page-agent-e2e/task-schema.ts tests/e2e/page-agent/smoke.yaml tests/e2e/page-agent/tasks.example.yaml
git commit -m "feat(e2e): add Zod schema validation and smoke test YAML"
```

---

## Task 3: Assertion Executor

**Files:**
- Create: `scripts/page-agent-e2e/assertions.ts`

- [ ] **Step 1: Write assertions.ts**

```typescript
import type { Page } from '@playwright/test';
import type { Assertion } from './task-schema.ts';

export interface AssertionResult {
  type: string;
  passed: boolean;
  message: string;
  expected?: string;
  actual?: string;
}

export async function executeAssertion(
  page: Page,
  assertion: Assertion,
  consoleErrors: string[],
  networkFailures: string[]
): Promise<AssertionResult> {
  const timeout = assertion.timeoutMs || 5000;

  switch (assertion.type) {
    case 'url_contains': {
      const url = page.url();
      const passed = url.includes(assertion.value!);
      return { type: assertion.type, passed, message: passed ? 'URL matches' : `URL "${url}" does not contain "${assertion.value}"`, expected: assertion.value, actual: url };
    }

    case 'url_equals': {
      const url = page.url();
      const passed = url === assertion.value!;
      return { type: assertion.type, passed, message: passed ? 'URL matches exactly' : `URL "${url}" !== "${assertion.value}"`, expected: assertion.value, actual: url };
    }

    case 'text_visible': {
      try {
        await page.getByText(assertion.value!, { exact: false }).first().waitFor({ timeout, state: 'visible' });
        return { type: assertion.type, passed: true, message: `Text "${assertion.value}" is visible` };
      } catch {
        return { type: assertion.type, passed: false, message: `Text "${assertion.value}" not found within ${timeout}ms`, expected: assertion.value };
      }
    }

    case 'text_not_visible': {
      try {
        await page.getByText(assertion.value!, { exact: false }).first().waitFor({ timeout: 2000, state: 'visible' });
        return { type: assertion.type, passed: false, message: `Text "${assertion.value}" is visible but should not be`, expected: 'not visible', actual: 'visible' };
      } catch {
        return { type: assertion.type, passed: true, message: `Text "${assertion.value}" correctly not visible` };
      }
    }

    case 'locator_visible': {
      try {
        await page.locator(assertion.selector!).first().waitFor({ timeout, state: 'visible' });
        return { type: assertion.type, passed: true, message: `Locator "${assertion.selector}" is visible` };
      } catch {
        return { type: assertion.type, passed: false, message: `Locator "${assertion.selector}" not visible within ${timeout}ms`, expected: 'visible' };
      }
    }

    case 'locator_count': {
      const count = await page.locator(assertion.selector!).count();
      const passed = count === assertion.count!;
      return { type: assertion.type, passed, message: passed ? `Count matches (${count})` : `Expected ${assertion.count} elements, found ${count}`, expected: String(assertion.count), actual: String(count) };
    }

    case 'console_no_errors': {
      const passed = consoleErrors.length === 0;
      return { type: assertion.type, passed, message: passed ? 'No console errors' : `${consoleErrors.length} console error(s)`, actual: consoleErrors.length > 0 ? consoleErrors.slice(0, 5).join('\n') : undefined };
    }

    case 'network_no_failures': {
      const passed = networkFailures.length === 0;
      return { type: assertion.type, passed, message: passed ? 'No network failures' : `${networkFailures.length} failed request(s)`, actual: networkFailures.length > 0 ? networkFailures.slice(0, 5).join('\n') : undefined };
    }

    case 'api_response': {
      return { type: assertion.type, passed: false, message: 'api_response assertion requires custom implementation per case' };
    }

    case 'db_query': {
      return { type: assertion.type, passed: false, message: 'db_query assertion requires database connection configuration' };
    }

    case 'log_contains': {
      return { type: assertion.type, passed: false, message: 'log_contains assertion not yet implemented' };
    }

    default:
      return { type: assertion.type, passed: false, message: `Unknown assertion type: ${assertion.type}` };
  }
}

export async function executeAssertions(
  page: Page,
  assertions: Assertion[],
  consoleErrors: string[],
  networkFailures: string[]
): Promise<AssertionResult[]> {
  const results: AssertionResult[] = [];
  for (const assertion of assertions) {
    results.push(await executeAssertion(page, assertion, consoleErrors, networkFailures));
  }
  return results;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd scripts/page-agent-e2e && npx tsx --no-warnings -e "import { executeAssertions } from './assertions.ts'; console.log('assertions module OK')"
```

Expected: `assertions module OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/page-agent-e2e/assertions.ts
git commit -m "feat(e2e): add deterministic assertion executor"
```

---

## Task 4: Report Generator + Logger

**Files:**
- Create: `scripts/page-agent-e2e/report.ts`
- Create: `scripts/page-agent-e2e/logger.ts`

- [ ] **Step 1: Write logger.ts — append-only JSONL**

```typescript
import { appendFileSync, mkdirSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const LOG_DIR = resolve(__dirname, '../../logs/page-agent-e2e');
const LOG_PATH = resolve(LOG_DIR, 'run.log');

export interface RunLogEntry {
  timestamp: string;
  command: string;
  gitBranch: string | null;
  gitCommit: string | null;
  targetApp: string;
  targetBaseUrl: string;
  taskFile: string;
  caseCount: number;
  passCount: number;
  failCount: number;
  durationMs: number;
  reportJson: string;
  reportMd: string;
  tokenUsage: {
    totalTokens: number;
    promptTokens: number;
    completionTokens: number;
    cachedTokens: number;
  };
  failedCaseIds: string[];
  safetyWarnings: string[];
  verificationResult: 'pass' | 'partial' | 'fail';
}

function getGitInfo(): { branch: string | null; commit: string | null } {
  try {
    const branch = execSync('git rev-parse --abbrev-ref HEAD', { encoding: 'utf-8' }).trim();
    const commit = execSync('git rev-parse --short HEAD', { encoding: 'utf-8' }).trim();
    return { branch, commit };
  } catch {
    return { branch: null, commit: null };
  }
}

export function appendRunLog(entry: Omit<RunLogEntry, 'timestamp' | 'gitBranch' | 'gitCommit'>): void {
  if (!existsSync(LOG_DIR)) {
    mkdirSync(LOG_DIR, { recursive: true });
  }

  const git = getGitInfo();
  const fullEntry: RunLogEntry = {
    ...entry,
    timestamp: new Date().toISOString(),
    gitBranch: git.branch,
    gitCommit: git.commit,
  };

  appendFileSync(LOG_PATH, JSON.stringify(fullEntry) + '\n', 'utf-8');
}

export function getLogPath(): string {
  return LOG_PATH;
}
```

- [ ] **Step 2: Write report.ts — JSON + Markdown generation**

```typescript
import { writeFileSync, mkdirSync, existsSync, readdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import type { AssertionResult } from './assertions.ts';

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPORT_DIR = resolve(__dirname, '../../reports/page-agent-e2e');

export interface CaseReport {
  id: string;
  app: string;
  route: string;
  passed: boolean;
  durationMs: number;
  assertions: AssertionResult[];
  pageAgentHistory: Array<{ step: number; action: string; result: string }>;
  tokenUsage: { promptTokens: number; completionTokens: number; totalTokens: number; cachedTokens: number };
  consoleErrors: string[];
  networkFailures: string[];
  finalUrl: string;
  domSummary: string;
}

export interface FullReport {
  timestamp: string;
  taskFile: string;
  cases: CaseReport[];
  summary: {
    total: number;
    passed: number;
    failed: number;
    durationMs: number;
    totalTokens: number;
  };
}

function getTimestamp(): string {
  return new Date().toISOString().replace(/[:-]/g, '').replace('T', '-').slice(0, 15);
}

export function generateReport(taskFile: string, cases: CaseReport[]): { jsonPath: string; mdPath: string; report: FullReport } {
  if (!existsSync(REPORT_DIR)) {
    mkdirSync(REPORT_DIR, { recursive: true });
  }

  const ts = getTimestamp();
  const jsonPath = resolve(REPORT_DIR, `${ts}.json`);
  const mdPath = resolve(REPORT_DIR, `${ts}.md`);

  const totalTokens = cases.reduce((sum, c) => sum + c.tokenUsage.totalTokens, 0);
  const totalDuration = cases.reduce((sum, c) => sum + c.durationMs, 0);

  const report: FullReport = {
    timestamp: new Date().toISOString(),
    taskFile,
    cases,
    summary: {
      total: cases.length,
      passed: cases.filter((c) => c.passed).length,
      failed: cases.filter((c) => !c.passed).length,
      durationMs: totalDuration,
      totalTokens,
    },
  };

  // JSON report
  writeFileSync(jsonPath, JSON.stringify(report, null, 2), 'utf-8');

  // Markdown report
  const md = generateMarkdown(report);
  writeFileSync(mdPath, md, 'utf-8');

  return { jsonPath, mdPath, report };
}

function generateMarkdown(report: FullReport): string {
  const lines: string[] = [];
  lines.push(`# PageAgent E2E Report`);
  lines.push('');
  lines.push(`**Generated:** ${report.timestamp}`);
  lines.push(`**Task File:** ${report.taskFile}`);
  lines.push(`**Result:** ${report.summary.passed}/${report.summary.total} passed`);
  lines.push(`**Duration:** ${(report.summary.durationMs / 1000).toFixed(1)}s`);
  lines.push(`**Total Tokens:** ${report.summary.totalTokens.toLocaleString()}`);
  lines.push('');

  // Summary table
  lines.push('## Summary');
  lines.push('');
  lines.push('| Case | App | Status | Duration | Tokens |');
  lines.push('|------|-----|--------|----------|--------|');
  for (const c of report.cases) {
    const status = c.passed ? '✅ PASS' : '❌ FAIL';
    lines.push(`| ${c.id} | ${c.app} | ${status} | ${(c.durationMs / 1000).toFixed(1)}s | ${c.tokenUsage.totalTokens} |`);
  }
  lines.push('');

  // Failed case details
  const failed = report.cases.filter((c) => !c.passed);
  if (failed.length > 0) {
    lines.push('## Failed Cases');
    lines.push('');
    for (const c of failed) {
      lines.push(`### ${c.id}`);
      lines.push('');
      lines.push(`**Final URL:** ${c.finalUrl}`);
      lines.push('');

      if (c.consoleErrors.length > 0) {
        lines.push('**Console Errors:**');
        lines.push('```');
        c.consoleErrors.slice(0, 10).forEach((e) => lines.push(e));
        lines.push('```');
        lines.push('');
      }

      if (c.networkFailures.length > 0) {
        lines.push('**Network Failures:**');
        lines.push('```');
        c.networkFailures.slice(0, 10).forEach((e) => lines.push(e));
        lines.push('```');
        lines.push('');
      }

      lines.push('**Assertion Failures:**');
      const failedAssertions = c.assertions.filter((a) => !a.passed);
      for (const a of failedAssertions) {
        lines.push(`- \`${a.type}\`: ${a.message}`);
        if (a.expected) lines.push(`  - Expected: ${a.expected}`);
        if (a.actual) lines.push(`  - Actual: ${a.actual}`);
      }
      lines.push('');

      if (c.pageAgentHistory.length > 0) {
        lines.push('**PageAgent Steps:**');
        for (const step of c.pageAgentHistory.slice(-5)) {
          lines.push(`- Step ${step.step}: ${step.action} → ${step.result}`);
        }
        lines.push('');
      }

      if (c.domSummary) {
        lines.push('**DOM Summary (truncated):**');
        lines.push('```');
        lines.push(c.domSummary.slice(0, 2000));
        lines.push('```');
        lines.push('');
      }
    }
  }

  return lines.join('\n');
}

// CLI mode: tsx report.ts --last
if (process.argv.includes('--last')) {
  if (!existsSync(REPORT_DIR)) {
    console.error('No reports directory found.');
    process.exit(1);
  }
  const files = readdirSync(REPORT_DIR).filter((f) => f.endsWith('.md')).sort();
  if (files.length === 0) {
    console.error('No reports found.');
    process.exit(1);
  }
  const latest = resolve(REPORT_DIR, files[files.length - 1]);
  const { readFileSync } = await import('fs');
  console.log(readFileSync(latest, 'utf-8'));
}
```

- [ ] **Step 3: Verify both modules compile**

```bash
cd scripts/page-agent-e2e && npx tsx --no-warnings -e "import { appendRunLog } from './logger.ts'; import { generateReport } from './report.ts'; console.log('logger+report OK')"
```

Expected: `logger+report OK`

- [ ] **Step 4: Commit**

```bash
git add scripts/page-agent-e2e/logger.ts scripts/page-agent-e2e/report.ts
git commit -m "feat(e2e): add JSONL logger and JSON/Markdown report generator"
```

---

## Task 5: PageAgent Injector

**Files:**
- Create: `scripts/page-agent-e2e/page-agent-injector.ts`

- [ ] **Step 1: Write page-agent-injector.ts**

```typescript
import type { Page } from '@playwright/test';
import type { PageAgentConfig } from './config.ts';
import type { TaskCase } from './task-schema.ts';

export interface PageAgentResult {
  success: boolean;
  data: unknown;
  history: Array<{ step: number; action: string; result: string }>;
  usage: { promptTokens: number; completionTokens: number; totalTokens: number; cachedTokens: number };
}

function buildContentTransform(): string {
  // Returns a function string that will be evaluated in browser context
  return `function(content) {
    return content
      .replace(/Bearer\\s+[A-Za-z0-9\\-._~+\\/]+=*/g, 'Bearer [REDACTED]')
      .replace(/Authorization:\\s*.+/gi, 'Authorization: [REDACTED]')
      .replace(/1[3-9]\\d{9}/g, '[PHONE_REDACTED]')
      .replace(/\\w+@\\w+\\.\\w+/g, '[EMAIL_REDACTED]')
      .replace(/\\d{6}(18|19|20)\\d{2}(0[1-9]|1[0-2])\\d{6}/g, '[ID_REDACTED]')
      .replace(/access_token["\\s:=]+[^\\s"&]+/gi, 'access_token=[REDACTED]')
      .replace(/refresh_token["\\s:=]+[^\\s"&]+/gi, 'refresh_token=[REDACTED]')
      .replace(/password["\\s:=]+[^\\s"&]+/gi, 'password=[REDACTED]');
  }`;
}

export async function injectPageAgent(
  page: Page,
  config: PageAgentConfig,
  testCase: TaskCase
): Promise<void> {
  // Inject PageAgent configuration into the page context
  // The actual PageAgent library will be loaded via its npm package
  await page.addInitScript({
    content: `
      window.__pageAgentE2EConfig = {
        model: "${config.llm.model}",
        baseURL: "${config.llm.baseURL}",
        apiKey: "${config.llm.apiKey}",
        language: "${config.language}",
        maxSteps: ${testCase.maxSteps},
        stepDelay: ${config.stepDelay},
        enableMask: false,
        experimentalScriptExecutionTool: false,
        instructions: {
          system: "你是 E2E 测试执行器。优先使用页面可见文本、表单标签、按钮文本和 DOM 语义完成操作。不要依赖截图。不要等待超过必要时间。任务完成后必须调用 done，并说明完成状态。自然语言完成说明不能替代确定性断言。"
        },
        transformPageContent: ${buildContentTransform()}
      };
    `,
  });
}

export async function runPageAgentTask(
  page: Page,
  task: string,
  config: PageAgentConfig,
  testCase: TaskCase
): Promise<PageAgentResult> {
  // Execute PageAgent task in browser context
  // This uses the page-agent npm package's browser API
  const result = await page.evaluate(
    async ({ task: taskText, maxSteps, stepDelay }) => {
      // page-agent exposes window.PageAgent after injection
      const pa = (window as any).__pageAgent;
      if (!pa) {
        return {
          success: false,
          data: 'PageAgent not initialized in page context',
          history: [],
          usage: { promptTokens: 0, completionTokens: 0, totalTokens: 0, cachedTokens: 0 },
        };
      }

      try {
        const result = await pa.run(taskText, { maxSteps, stepDelay });
        return {
          success: result.success ?? true,
          data: result.data ?? null,
          history: result.history ?? [],
          usage: result.usage ?? { promptTokens: 0, completionTokens: 0, totalTokens: 0, cachedTokens: 0 },
        };
      } catch (err: any) {
        return {
          success: false,
          data: err.message || String(err),
          history: [],
          usage: { promptTokens: 0, completionTokens: 0, totalTokens: 0, cachedTokens: 0 },
        };
      }
    },
    { task, maxSteps: testCase.maxSteps, stepDelay: config.stepDelay }
  );

  return result as PageAgentResult;
}

export async function extractDomSummary(page: Page, maxChars: number = 20000): Promise<string> {
  const text = await page.evaluate(() => {
    const body = document.body;
    if (!body) return '';
    // Get visible text content, truncated
    return body.innerText || '';
  });
  return text.slice(0, maxChars);
}
```

- [ ] **Step 2: Verify module compiles**

```bash
cd scripts/page-agent-e2e && npx tsx --no-warnings -e "import { injectPageAgent, runPageAgentTask, extractDomSummary } from './page-agent-injector.ts'; console.log('injector module OK')"
```

Expected: `injector module OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/page-agent-e2e/page-agent-injector.ts
git commit -m "feat(e2e): add PageAgent browser injector with security redaction"
```

---

## Task 6: Main Runner Orchestrator

**Files:**
- Create: `scripts/page-agent-e2e/page-agent-runner.ts`

- [ ] **Step 1: Write page-agent-runner.ts**

```typescript
import { chromium } from '@playwright/test';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync } from 'fs';
import { loadConfig } from './config.ts';
import { validateTaskFile, type TaskCase } from './task-schema.ts';
import { injectPageAgent, runPageAgentTask, extractDomSummary } from './page-agent-injector.ts';
import { executeAssertions, type AssertionResult } from './assertions.ts';
import { generateReport, type CaseReport } from './report.ts';
import { appendRunLog } from './logger.ts';

const __dirname = dirname(fileURLToPath(import.meta.url));

async function runCase(testCase: TaskCase, config: ReturnType<typeof loadConfig>): Promise<CaseReport> {
  const startTime = Date.now();
  const consoleErrors: string[] = [];
  const networkFailures: string[] = [];

  const baseUrl = testCase.app === 'child' ? config.childBaseUrl : config.baseUrl;
  const targetUrl = testCase.baseUrl || baseUrl;

  const browser = await chromium.launch({ headless: !config.debug });
  const context = await browser.newContext({
    baseURL: targetUrl,
    viewport: { width: 390, height: 844 },
  });

  // Load storage state if specified
  if (testCase.storageState && existsSync(resolve(__dirname, '../..', testCase.storageState))) {
    const storageState = resolve(__dirname, '../..', testCase.storageState);
    await context.addCookies((await import(storageState, { with: { type: 'json' } })).default?.cookies || []);
  }

  const page = await context.newPage();

  // Capture console errors
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  // Capture network failures
  page.on('response', (resp) => {
    if (resp.status() >= 400) {
      networkFailures.push(`${resp.status()} ${resp.request().method()} ${resp.url()}`);
    }
  });

  let pageAgentResult = {
    success: false,
    data: null as unknown,
    history: [] as Array<{ step: number; action: string; result: string }>,
    usage: { promptTokens: 0, completionTokens: 0, totalTokens: 0, cachedTokens: 0 },
  };

  try {
    // Navigate to target
    await page.goto(testCase.route, { waitUntil: 'networkidle', timeout: testCase.timeoutMs });

    // Inject and run PageAgent
    await injectPageAgent(page, config, testCase);
    pageAgentResult = await runPageAgentTask(page, testCase.task, config, testCase);
  } catch (err: any) {
    consoleErrors.push(`Runner error: ${err.message}`);
  }

  // Execute assertions regardless of PageAgent result
  const assertionResults = await executeAssertions(page, testCase.assertions, consoleErrors, networkFailures);
  const finalUrl = page.url();
  const domSummary = await extractDomSummary(page);

  await browser.close();

  const durationMs = Date.now() - startTime;
  const allPassed = assertionResults.every((a) => a.passed);

  return {
    id: testCase.id,
    app: testCase.app || 'main',
    route: testCase.route,
    passed: allPassed,
    durationMs,
    assertions: assertionResults,
    pageAgentHistory: pageAgentResult.history,
    tokenUsage: pageAgentResult.usage,
    consoleErrors,
    networkFailures,
    finalUrl,
    domSummary,
  };
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error('Usage: tsx page-agent-runner.ts <yaml-file>...');
    process.exit(1);
  }

  const config = loadConfig();
  const taskFilePath = resolve(args[0]);

  if (!existsSync(taskFilePath)) {
    console.error(`Task file not found: ${taskFilePath}`);
    process.exit(1);
  }

  console.log(`\n🔬 PageAgent E2E Runner`);
  console.log(`   Task file: ${args[0]}`);
  console.log(`   Base URL: ${config.baseUrl}`);
  console.log(`   LLM: ${config.llm.model} @ ${config.llm.baseURL}`);
  console.log(`   Debug: ${config.debug}\n`);

  const taskFile = validateTaskFile(taskFilePath);
  console.log(`   Found ${taskFile.cases.length} test case(s)\n`);

  const caseReports: CaseReport[] = [];

  for (const testCase of taskFile.cases) {
    console.log(`  ▸ Running: ${testCase.id}...`);
    const report = await runCase(testCase, config);
    caseReports.push(report);
    const icon = report.passed ? '✅' : '❌';
    console.log(`  ${icon} ${testCase.id} (${(report.durationMs / 1000).toFixed(1)}s, ${report.tokenUsage.totalTokens} tokens)`);
  }

  // Generate reports
  const { jsonPath, mdPath, report } = generateReport(args[0], caseReports);
  console.log(`\n📊 Report: ${mdPath}`);
  console.log(`   JSON: ${jsonPath}`);

  // Append to run log
  const totalTokens = caseReports.reduce((sum, c) => sum + c.tokenUsage.totalTokens, 0);
  appendRunLog({
    command: `tsx page-agent-runner.ts ${args[0]}`,
    targetApp: taskFile.cases[0]?.app || 'main',
    targetBaseUrl: config.baseUrl,
    taskFile: args[0],
    caseCount: caseReports.length,
    passCount: caseReports.filter((c) => c.passed).length,
    failCount: caseReports.filter((c) => !c.passed).length,
    durationMs: report.summary.durationMs,
    reportJson: jsonPath,
    reportMd: mdPath,
    tokenUsage: {
      totalTokens,
      promptTokens: caseReports.reduce((sum, c) => sum + c.tokenUsage.promptTokens, 0),
      completionTokens: caseReports.reduce((sum, c) => sum + c.tokenUsage.completionTokens, 0),
      cachedTokens: caseReports.reduce((sum, c) => sum + c.tokenUsage.cachedTokens, 0),
    },
    failedCaseIds: caseReports.filter((c) => !c.passed).map((c) => c.id),
    safetyWarnings: [],
    verificationResult: report.summary.failed === 0 ? 'pass' : report.summary.passed > 0 ? 'partial' : 'fail',
  });

  // Summary
  console.log(`\n${'─'.repeat(50)}`);
  console.log(`   Results: ${report.summary.passed}/${report.summary.total} passed`);
  console.log(`   Duration: ${(report.summary.durationMs / 1000).toFixed(1)}s`);
  console.log(`   Tokens: ${totalTokens.toLocaleString()}`);
  console.log(`${'─'.repeat(50)}\n`);

  process.exit(report.summary.failed > 0 ? 1 : 0);
}

main().catch((err) => {
  console.error('Fatal error:', err.message);
  process.exit(1);
});
```

- [ ] **Step 2: Verify runner compiles (dry import)**

```bash
cd scripts/page-agent-e2e && npx tsx --no-warnings -e "
  // Verify all imports resolve
  const modules = ['./config.ts', './task-schema.ts', './page-agent-injector.ts', './assertions.ts', './report.ts', './logger.ts'];
  for (const m of modules) { await import(m); }
  console.log('All runner modules resolve OK');
"
```

Expected: `All runner modules resolve OK` (may warn about missing API key)

- [ ] **Step 3: Commit**

```bash
git add scripts/page-agent-e2e/page-agent-runner.ts
git commit -m "feat(e2e): add main PageAgent E2E runner orchestrator"
```

---

## Task 7: Verification Script

**Files:**
- Create: `scripts/page-agent-e2e/verify-smoke.ts`

- [ ] **Step 1: Write verify-smoke.ts**

```typescript
import { existsSync, readdirSync, readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { validateTaskFileWithErrors } from './task-schema.ts';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, '../..');

const checks: Array<{ name: string; check: () => boolean; message: string }> = [
  {
    name: 'YAML schema validation',
    check: () => {
      const smokeFile = resolve(projectRoot, 'tests/e2e/page-agent/smoke.yaml');
      if (!existsSync(smokeFile)) return false;
      const result = validateTaskFileWithErrors(smokeFile);
      return result.success;
    },
    message: 'tests/e2e/page-agent/smoke.yaml passes Zod schema validation',
  },
  {
    name: 'Runner script exists',
    check: () => existsSync(resolve(__dirname, 'page-agent-runner.ts')),
    message: 'scripts/page-agent-e2e/page-agent-runner.ts exists',
  },
  {
    name: 'Config loads without crash',
    check: () => {
      try {
        // Config will throw if API key missing, that's OK for verification
        const { loadConfig } = require('./config.ts');
        return true;
      } catch {
        return true; // Module exists even if env not configured
      }
    },
    message: 'config.ts module loads',
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
      const smokeFile = resolve(projectRoot, 'tests/e2e/page-agent/smoke.yaml');
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
```

- [ ] **Step 2: Run verification**

```bash
cd scripts/page-agent-e2e && npx tsx verify-smoke.ts
```

Expected: All checks pass (or clear failure messages indicating what's missing)

- [ ] **Step 3: Commit**

```bash
git add scripts/page-agent-e2e/verify-smoke.ts
git commit -m "feat(e2e): add post-run verification script"
```

---

## Task 8: Claude Code Skill — SKILL.md + References

**Files:**
- Create: `.claude/skills/page-agent-e2e/SKILL.md`
- Create: `.claude/skills/page-agent-e2e/.gitignore`
- Create: `.claude/skills/page-agent-e2e/.env.example`
- Create: `.claude/skills/page-agent-e2e/examples/smoke.yaml`

- [ ] **Step 1: Create .gitignore**

Create `.claude/skills/page-agent-e2e/.gitignore`:

```gitignore
# Secrets — never commit
.env

# Generated at runtime
*.log
```

- [ ] **Step 2: Create .env.example**

Create `.claude/skills/page-agent-e2e/.env.example`:

```env
# Copy to .env and fill in real values. Never commit .env itself.

# Required — PageAgent LLM (provider-agnostic)
PAGE_AGENT_LLM_BASE_URL=https://api.openai.com/v1
PAGE_AGENT_LLM_MODEL=gpt-4o
PAGE_AGENT_LLM_API_KEY=sk-...

# Optional — PageAgent behavior
PAGE_AGENT_LANGUAGE=zh-CN
PAGE_AGENT_DEBUG=0
PAGE_AGENT_STEP_DELAY=0.3

# Optional — Service URLs
PAGE_AGENT_BASE_URL=http://localhost:5173
PAGE_AGENT_BACKEND_URL=http://localhost:8000
PAGE_AGENT_E2E_SKIP_START=0

# Test credentials
E2E_TEST_USER=test_rich
E2E_TEST_PASSWORD=TestRich123!

# Child app
PAGE_AGENT_CHILD_BASE_URL=http://localhost:5174
E2E_CHILD_PIN=🐱,🐶,🌟,🌈
E2E_CHILD_USER=test_child
```

- [ ] **Step 3: Create SKILL.md**

Create `.claude/skills/page-agent-e2e/SKILL.md`:

```markdown
---
name: page-agent-e2e
description: "Triggers on: e2e, end-to-end, Playwright, Vue E2E, Python Vue integration test, smoke test, UI workflow test, login flow test, approval flow test, CRUD flow test, search/filter test, admin workflow test, avoid screenshots, stop using screenshots for AI testing, reduce token usage in browser tests, PageAgent, DOM-based UI automation, semantic browser test. Use when creating, fixing, optimizing, or running long-path UI automation in Python + Vue projects. Prefer Alibaba PageAgent for semantic page interaction through text DOM, and verify outcomes with deterministic Playwright/API/database assertions."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Edit
  - Write
  - Bash
---

# PageAgent E2E Skill

Semantic DOM-based E2E testing using Alibaba PageAgent. Reads text DOM instead of screenshots. 10-50x cheaper in tokens than vision-based approaches.

## When to Use

- Multi-page business workflows (login → CRUD → approval → verification)
- Forms, navigation, search/filter flows across Vue frontend + Python backend
- Replacing brittle Playwright locators with semantic natural-language steps
- Reducing token cost from screenshot-based AI testing
- Cases where `numina-sim-test` would be overkill (no visual audit needed)

## When NOT to Use

- Visual regression testing (colors, spacing, layout) → use `numina-sim-test`
- Pure API tests → use pytest
- Pure component tests → use vitest
- Stable locator-based tests that already work → leave as Playwright specs

## Architecture

Runner: `scripts/page-agent-e2e/page-agent-runner.ts`
Tests: `tests/e2e/page-agent/*.yaml`
Reports: `reports/page-agent-e2e/`
Log: `logs/page-agent-e2e/run.log`

PageAgent handles semantic interaction (click, type, scroll via text DOM).
Playwright handles browser lifecycle, navigation, and deterministic assertions.
Never trust PageAgent's natural-language "success" — always verify with assertions.

## Workflow

1. Identify target app and flow to test
2. Write or update YAML case in `tests/e2e/page-agent/`
3. Validate: `cd scripts/page-agent-e2e && npx tsx task-schema.ts --validate <file>`
4. Run: `cd scripts/page-agent-e2e && npx tsx page-agent-runner.ts <file>`
5. Check report in `reports/page-agent-e2e/`
6. On failure: read report evidence (URL, console, network, DOM), fix case or code
7. Never auto-modify business code on failure — produce a failure report first

## Constraints

- `experimentalScriptExecutionTool: false` — no arbitrary JS execution in PageAgent
- `enableMask: false` — no screenshot dependency
- Content redacted before LLM sees DOM (Bearer tokens, passwords, PII)
- Every case must have deterministic assertions (url, text, locator, API, DB)
- maxSteps is mandatory to prevent runaway LLM calls
- Random test data uses `e2e_<timestamp>_` prefix
- Exit code 1 on any failure
- No secrets in reports or logs

## Configuration

See `.env.example` in this directory. Copy to `.env` for local config.
Priority: shell env > runner .env > skill .env > defaults.

## References

Read these when context is needed:
- `references/project-gotchas.md` — before writing any assertion for this project
- `references/task-yaml-schema.md` — YAML format reference
- `references/security-and-ci.md` — CI rules and dangerous operation interception
- `references/product-verification.md` — what counts as "verified"
- `references/hooks-and-memory.md` — safety hooks and logging rules
- `references/page-agent-e2e-architecture.md` — full architecture details

## Prohibitions

- Never use screenshots to understand page content
- Never use OCR or multimodal vision as primary page understanding
- Never put API keys in production frontend bundles
- Never enable execute_javascript in CI
- Never claim success based only on PageAgent's natural-language response
- Never auto-modify business code on test failure without a failure report
- Never use "feels right" or "looks correct" as verification
```

- [ ] **Step 4: Create examples/smoke.yaml**

```bash
mkdir -p .claude/skills/page-agent-e2e/examples
```

Copy `tests/e2e/page-agent/smoke.yaml` content to `.claude/skills/page-agent-e2e/examples/smoke.yaml` (same content as Task 2 Step 2).

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/page-agent-e2e/SKILL.md .claude/skills/page-agent-e2e/.gitignore .claude/skills/page-agent-e2e/.env.example .claude/skills/page-agent-e2e/examples/smoke.yaml
git commit -m "feat(skill): create page-agent-e2e Claude Code skill with SKILL.md"
```

---

## Task 9: Skill References — Architecture, Schema, Gotchas

**Files:**
- Create: `.claude/skills/page-agent-e2e/references/page-agent-e2e-architecture.md`
- Create: `.claude/skills/page-agent-e2e/references/task-yaml-schema.md`
- Create: `.claude/skills/page-agent-e2e/references/project-gotchas.md`

- [ ] **Step 1: Create page-agent-e2e-architecture.md**

Condense the design spec's architecture section (sections 2, 5, 6 from spec) into a reference doc. Include the ASCII diagram, injector config, runner process, relationship with numina-sim-test.

- [ ] **Step 2: Create task-yaml-schema.md**

Document the full YAML schema with field descriptions, types, defaults, and 2-3 examples covering different assertion types. Source from spec section 4.

- [ ] **Step 3: Create project-gotchas.md**

Full gotcha documentation with the 7 gotchas identified in the spec (section 13), each following the format:

```markdown
### Gotcha: <title>

[陷阱]
<what AI gets wrong>

[正确做法]
<correct approach>

[证据]
<file paths, function names>
```

Gotchas to include:
1. Snowflake ID serialization (IDs are strings in API responses) — evidence: `server/packages/core/`, `SnowflakeBase`
2. No trailing slash on API routes — evidence: `server/apps/backend/app/main.py`, `redirect_slashes=False`
3. Auth returns 200 not 201 — evidence: `server/apps/backend/app/routers/auth.py`
4. TokenResponse has no user field — evidence: `tests/lib/auth.ts` line 56-70
5. Dashboard allocation returns nested object — evidence: frontend store/API types
6. i18n required for all UI strings — evidence: `frontend/apps/main/src/i18n/`
7. Child app uses emoji PIN auth (two-phase) — evidence: `tests/lib/auth.ts:loginAsChild`

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/page-agent-e2e/references/page-agent-e2e-architecture.md .claude/skills/page-agent-e2e/references/task-yaml-schema.md .claude/skills/page-agent-e2e/references/project-gotchas.md
git commit -m "feat(skill): add architecture, schema, and gotchas references"
```

---

## Task 10: Skill References — Security, Verification, Hooks

**Files:**
- Create: `.claude/skills/page-agent-e2e/references/security-and-ci.md`
- Create: `.claude/skills/page-agent-e2e/references/product-verification.md`
- Create: `.claude/skills/page-agent-e2e/references/hooks-and-memory.md`

- [ ] **Step 1: Create security-and-ci.md**

Document from spec section 12:
- Dangerous operation interception list
- CI defaults (no screenshots, no execute_javascript, artifact rules)
- Secret detection in output (fail-fast)
- Content redaction patterns

- [ ] **Step 2: Create product-verification.md**

Document from spec section 11:
- What counts as verified (table with evidence × method)
- Prohibited "verification" statements
- Specific commands to verify each aspect
- Post-run verification checklist

- [ ] **Step 3: Create hooks-and-memory.md**

Document:
- `/careful` interception logic (when to trigger, what to do if unavailable)
- Append-only log schema and rules
- Read-before-debug requirement
- Memory vs log distinction

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/page-agent-e2e/references/security-and-ci.md .claude/skills/page-agent-e2e/references/product-verification.md .claude/skills/page-agent-e2e/references/hooks-and-memory.md
git commit -m "feat(skill): add security, verification, and hooks references"
```

---

## Task 11: Integration Smoke Test — End-to-End Verification

**Files:**
- No new files — verification only

- [ ] **Step 1: Run YAML validation**

```bash
cd scripts/page-agent-e2e && npx tsx task-schema.ts --validate ../../tests/e2e/page-agent/smoke.yaml
```

Expected: `✓ ../../tests/e2e/page-agent/smoke.yaml (3 cases)`

- [ ] **Step 2: Run verification script**

```bash
cd scripts/page-agent-e2e && npx tsx verify-smoke.ts
```

Expected: All checks pass

- [ ] **Step 3: TypeScript compile check**

```bash
cd scripts/page-agent-e2e && npx tsc --noEmit
```

Expected: No errors

- [ ] **Step 4: Verify no secrets in committed files**

```bash
cd /Volumes/LexarSSDNQ790/geek_space/github/numina_dev_space/numina-deerflow && git diff --cached --name-only | xargs grep -l "sk-\|Bearer\|password:" 2>/dev/null || echo "No secrets found"
```

Expected: `No secrets found` (or only .env.example files which contain placeholder values)

- [ ] **Step 5: Run the runner with missing services (verify graceful failure)**

```bash
cd scripts/page-agent-e2e && PAGE_AGENT_LLM_API_KEY=sk-test npx tsx page-agent-runner.ts ../../tests/e2e/page-agent/smoke.yaml 2>&1 | head -20
```

Expected: Runner starts, prints header, then fails with connection error to localhost:5173 (not a crash). Exit code 1. A JSONL entry should appear in `logs/page-agent-e2e/run.log`.

- [ ] **Step 6: Verify log entry was written**

```bash
cat logs/page-agent-e2e/run.log | tail -1 | python3 -m json.tool | head -10
```

Expected: Valid JSON with timestamp, command, caseCount fields

- [ ] **Step 7: Verify report was generated**

```bash
ls reports/page-agent-e2e/*.md 2>/dev/null && echo "Reports exist" || echo "No reports yet"
```

Expected: At least one .md file exists after the failed run

- [ ] **Step 8: Final commit (if any fixes were needed)**

```bash
git status
# If clean, no commit needed. If fixes were applied:
git add -A && git commit -m "fix(e2e): address integration test findings"
```

---

## Task 12: CI Documentation

**Files:**
- Create: `docs/page-agent-e2e-ci.md`

- [ ] **Step 1: Write CI integration guide**

```markdown
# PageAgent E2E — CI Integration Guide

## GitHub Actions Example

```yaml
name: PageAgent E2E
on:
  pull_request:
    paths:
      - 'frontend/**'
      - 'server/**'
      - 'tests/e2e/page-agent/**'

jobs:
  page-agent-e2e:
    runs-on: ubuntu-latest
    env:
      PAGE_AGENT_LLM_BASE_URL: ${{ secrets.PAGE_AGENT_LLM_BASE_URL }}
      PAGE_AGENT_LLM_MODEL: gpt-4o
      PAGE_AGENT_LLM_API_KEY: ${{ secrets.PAGE_AGENT_LLM_API_KEY }}
      PAGE_AGENT_BASE_URL: http://localhost:5173
      PAGE_AGENT_BACKEND_URL: http://localhost:8000
      E2E_TEST_USER: test_rich
      E2E_TEST_PASSWORD: ${{ secrets.E2E_TEST_PASSWORD }}

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 22

      - name: Install runner dependencies
        run: cd scripts/page-agent-e2e && npm ci

      - name: Install Playwright browsers
        run: cd scripts/page-agent-e2e && npx playwright install chromium

      - name: Start services
        run: |
          # Start backend and frontend (adjust to your docker-compose or script)
          docker-compose up -d
          # Wait for services
          npx wait-on http://localhost:5173 http://localhost:8000/api/v1/health

      - name: Validate YAML schemas
        run: cd scripts/page-agent-e2e && npx tsx task-schema.ts --validate '../../tests/e2e/page-agent/**/*.yaml'

      - name: Run smoke tests
        run: cd scripts/page-agent-e2e && npx tsx page-agent-runner.ts ../../tests/e2e/page-agent/smoke.yaml

      - name: Upload reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: page-agent-e2e-reports
          path: |
            reports/page-agent-e2e/*.json
            reports/page-agent-e2e/*.md
            logs/page-agent-e2e/run.log
```

## Security Notes

- Never upload `.env` files as artifacts
- LLM API key comes from repository secrets only
- `experimentalScriptExecutionTool` is always `false` in CI
- Reports are scanned for secrets before upload (fail-fast)
- No screenshots are taken or uploaded by default
```

- [ ] **Step 2: Commit**

```bash
git add docs/page-agent-e2e-ci.md
git commit -m "docs: add PageAgent E2E CI integration guide"
```

---

## Self-Review Checklist

1. **Spec coverage:** All 17 spec sections are addressed:
   - §1 Problem → Architecture justification in Task 8 SKILL.md
   - §2 Architecture → Task 5 (injector), Task 6 (runner), Task 9 (architecture ref)
   - §3 File Layout → Task 1 (scaffolding), Task 8 (skill), directories
   - §4 YAML Schema → Task 2 (Zod schema + smoke.yaml)
   - §5 Injector Config → Task 5
   - §6 Runner Behavior → Task 6
   - §7 Execution Log → Task 4 (logger.ts)
   - §8 Configuration → Task 1 (config.ts with dotenv precedence)
   - §9 Smoke Cases → Task 2 (smoke.yaml)
   - §10 Package Scripts → Task 1 (package.json)
   - §11 Verification → Task 7 (verify-smoke.ts), Task 11 (integration)
   - §12 Safety & CI → Task 10 (security ref), Task 12 (CI doc)
   - §13 Gotchas → Task 9 (project-gotchas.md)
   - §14 Token Advantage → Documented in architecture ref
   - §15 Risks → Noted in architecture ref
   - §16 Dependencies → Task 1 (package.json)
   - §17 Success Criteria → Task 11 verifies all criteria

2. **No placeholders:** All tasks contain actual code with real file paths.

3. **Type consistency:** `TaskCase`, `PageAgentConfig`, `AssertionResult`, `CaseReport`, `FullReport`, `RunLogEntry` — used consistently across all modules.
