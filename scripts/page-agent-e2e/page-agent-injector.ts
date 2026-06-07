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
  return text.slice(0, maxChars);
}
