import { chromium } from '@playwright/test';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync, readFileSync } from 'fs';
import { loadConfig } from './config.ts';
import { validateTaskFile, type TaskCase } from './task-schema.ts';
import { injectPageAgent, runPageAgentTask, extractDomSummary, redactContent } from './page-agent-injector.ts';
import { executeAssertions, type AssertionResult } from './assertions.ts';
import { generateReport, type CaseReport } from './report.ts';
import { appendRunLog } from './logger.ts';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, '../..');

async function runCase(testCase: TaskCase, config: ReturnType<typeof loadConfig>): Promise<CaseReport> {
  const startTime = Date.now();
  const consoleErrors: string[] = [];
  const networkFailures: string[] = [];

  const baseUrl = testCase.app === 'child' ? config.childBaseUrl : config.baseUrl;
  const targetUrl = testCase.baseUrl || baseUrl;

  const browser = await chromium.launch({ headless: !config.debug });

  try {
    let contextOptions: Record<string, unknown> = {
      baseURL: targetUrl,
      viewport: { width: 390, height: 844 },
    };

    // Validate and load storageState
    if (testCase.storageState) {
      const storageStatePath = resolve(PROJECT_ROOT, testCase.storageState);
      if (!storageStatePath.startsWith(PROJECT_ROOT)) {
        throw new Error(`storageState path escapes project root: ${testCase.storageState}`);
      }
      if (!existsSync(storageStatePath)) {
        throw new Error(`storageState file not found: ${storageStatePath}. Run auth setup first.`);
      }
      contextOptions = { ...contextOptions, storageState: storageStatePath };
    }

    const context = await browser.newContext(contextOptions);
    const page = await context.newPage();

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(redactContent(msg.text()));
      }
    });

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
      await page.goto(testCase.route, { waitUntil: 'networkidle', timeout: testCase.timeoutMs });
      await injectPageAgent(page, config, testCase);
      pageAgentResult = await runPageAgentTask(page, testCase.task, config, testCase);
    } catch (err: any) {
      consoleErrors.push(`Runner error: ${err.message}`);
    }

    let assertionResults: AssertionResult[] = [];
    let finalUrl = '';
    let domSummary = '';

    try {
      assertionResults = await executeAssertions(page, testCase.assertions, consoleErrors, networkFailures);
      finalUrl = page.url();
      domSummary = await extractDomSummary(page);
    } catch (err: any) {
      consoleErrors.push(`Post-run error: ${err.message}`);
      try { finalUrl = page.url(); } catch { /* page closed */ }
    }

    const durationMs = Date.now() - startTime;
    const allPassed = assertionResults.length > 0 && assertionResults.every((a) => a.passed);

    return {
      id: testCase.id,
      app: testCase.app || 'main',
      route: testCase.route,
      passed: allPassed,
      durationMs,
      assertions: assertionResults,
      pageAgentHistory: pageAgentResult.history.map((h) => ({
        step: h.step,
        action: redactContent(h.action),
        result: redactContent(h.result),
      })),
      tokenUsage: pageAgentResult.usage,
      consoleErrors,
      networkFailures,
      finalUrl,
      domSummary,
    };
  } finally {
    await browser.close();
  }
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
  console.log(`   Task file: ${taskFilePath}`);
  console.log(`   Base URL: ${config.baseUrl}`);
  console.log(`   LLM: ${config.llm.model} @ ${config.llm.baseURL}`);
  console.log(`   Debug: ${config.debug}\n`);

  const taskFile = validateTaskFile(taskFilePath);
  console.log(`   Found ${taskFile.cases.length} test case(s)\n`);

  const caseReports: CaseReport[] = [];

  for (const testCase of taskFile.cases) {
    console.log(`  ▸ Running: ${testCase.id}...`);
    try {
      const report = await runCase(testCase, config);
      caseReports.push(report);
      const icon = report.passed ? '✅' : '❌';
      console.log(`  ${icon} ${testCase.id} (${(report.durationMs / 1000).toFixed(1)}s, ${report.tokenUsage.totalTokens} tokens)`);
    } catch (err: any) {
      const failedReport: CaseReport = {
        id: testCase.id,
        app: testCase.app || 'main',
        route: testCase.route,
        passed: false,
        durationMs: 0,
        assertions: [],
        pageAgentHistory: [],
        tokenUsage: { promptTokens: 0, completionTokens: 0, totalTokens: 0, cachedTokens: 0 },
        consoleErrors: [`Setup error: ${err.message}`],
        networkFailures: [],
        finalUrl: '',
        domSummary: '',
      };
      caseReports.push(failedReport);
      console.log(`  ❌ ${testCase.id} (setup error: ${err.message})`);
    }
  }

  const { jsonPath, mdPath, report } = generateReport(taskFilePath, caseReports);
  console.log(`\n📊 Report: ${mdPath}`);
  console.log(`   JSON: ${jsonPath}`);

  const totalTokens = caseReports.reduce((sum, c) => sum + c.tokenUsage.totalTokens, 0);
  appendRunLog({
    command: `tsx page-agent-runner.ts ${taskFilePath}`,
    targetApp: taskFile.cases[0]?.app || 'main',
    targetBaseUrl: config.baseUrl,
    taskFile: taskFilePath,
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
