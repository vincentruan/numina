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
