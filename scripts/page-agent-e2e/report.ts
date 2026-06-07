import { writeFileSync, mkdirSync, existsSync, readdirSync, readFileSync } from 'fs';
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

  writeFileSync(jsonPath, JSON.stringify(report, null, 2), 'utf-8');

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

  lines.push('## Summary');
  lines.push('');
  lines.push('| Case | App | Status | Duration | Tokens |');
  lines.push('|------|-----|--------|----------|--------|');
  for (const c of report.cases) {
    const status = c.passed ? '✅ PASS' : '❌ FAIL';
    lines.push(`| ${c.id} | ${c.app} | ${status} | ${(c.durationMs / 1000).toFixed(1)}s | ${c.tokenUsage.totalTokens} |`);
  }
  lines.push('');

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
  console.log(readFileSync(latest, 'utf-8'));
}
