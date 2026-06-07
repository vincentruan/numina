import type { Page } from '@playwright/test';
import type { PageAgentConfig } from './config.ts';
import type { TaskCase } from './task-schema.ts';

export interface PageAgentResult {
  success: boolean;
  data: unknown;
  history: Array<{ step: number; action: string; result: string }>;
  usage: { promptTokens: number; completionTokens: number; totalTokens: number; cachedTokens: number };
}

const REDACTION_PATTERNS: Array<[RegExp, string]> = [
  [/Bearer\s+[A-Za-z0-9\-._~+/]+=*/g, 'Bearer [REDACTED]'],
  [/Authorization:\s*.+/gi, 'Authorization: [REDACTED]'],
  [/1[3-9]\d{9}/g, '[PHONE_REDACTED]'],
  [/\w+@\w+\.\w+/g, '[EMAIL_REDACTED]'],
  [/\d{6}(18|19|20)\d{2}(0[1-9]|1[0-2])\d{6}/g, '[ID_REDACTED]'],
  [/access_token["\s:=]+[^\s"&]+/gi, 'access_token=[REDACTED]'],
  [/refresh_token["\s:=]+[^\s"&]+/gi, 'refresh_token=[REDACTED]'],
  [/password["\s:=]+[^\s"&]+/gi, 'password=[REDACTED]'],
];

export function redactContent(content: string): string {
  let result = content;
  for (const [pattern, replacement] of REDACTION_PATTERNS) {
    result = result.replace(pattern, replacement);
  }
  return result;
}

export async function injectPageAgent(
  page: Page,
  config: PageAgentConfig,
  testCase: TaskCase
): Promise<void> {
  // Inject only non-sensitive config into page context using JSON.stringify for safety.
  // API key is NOT sent to the browser — PageAgent calls are made server-side.
  const pageConfig = {
    model: config.llm.model,
    language: config.language,
    maxSteps: testCase.maxSteps,
    stepDelay: config.stepDelay,
    enableMask: false,
    experimentalScriptExecutionTool: false,
    instructions: {
      system: '你是 E2E 测试执行器。优先使用页面可见文本、表单标签、按钮文本和 DOM 语义完成操作。不要依赖截图。不要等待超过必要时间。任务完成后必须调用 done，并说明完成状态。自然语言完成说明不能替代确定性断言。',
    },
  };

  await page.evaluate((cfg) => {
    (window as any).__pageAgentE2EConfig = cfg;
  }, pageConfig);
}

export async function runPageAgentTask(
  page: Page,
  task: string,
  config: PageAgentConfig,
  testCase: TaskCase
): Promise<PageAgentResult> {
  const result = await page.evaluate(
    async ({ task: taskText, maxSteps, stepDelay }) => {
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
    return body.innerText || '';
  });
  return redactContent(text.slice(0, maxChars));
}
