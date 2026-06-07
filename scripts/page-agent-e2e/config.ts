import { config } from 'dotenv';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

config({ path: resolve(__dirname, '../../.claude/skills/page-agent-e2e/.env') });
config({ path: resolve(__dirname, '.env') });

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
