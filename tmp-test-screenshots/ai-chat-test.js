const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const SCREENSHOT_DIR = path.join(__dirname);
const BASE_URL = 'http://localhost:5173';

async function screenshot(page, name) {
  const filepath = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: filepath, fullPage: false });
  console.log(`✓ Screenshot: ${name}.png`);
  return filepath;
}

async function waitForStreamComplete(page, timeoutMs = 120000) {
  // Wait for streaming indicator to disappear
  const startTime = Date.now();
  while (Date.now() - startTime < timeoutMs) {
    const isStreaming = await page.evaluate(() => {
      // Check if streaming indicator exists
      const indicator = document.querySelector('.streaming-indicator, .typing-indicator, [class*="streaming"]');
      return indicator !== null;
    });
    if (!isStreaming) {
      // Wait a bit more for final render
      await page.waitForTimeout(2000);
      return true;
    }
    await page.waitForTimeout(1000);
  }
  console.log('⚠ Stream timeout reached');
  return false;
}

async function testQuery(page, query, mode, testName) {
  console.log(`\n=== Testing: ${testName} (mode: ${mode}) ===`);
  console.log(`Query: ${query}`);

  // Navigate to AI chat
  await page.goto(`${BASE_URL}/ai/chat`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  // Select mode
  const modeSelector = await page.$('.mode-selector, [class*="mode-selector"]');
  if (modeSelector) {
    await modeSelector.click();
    await page.waitForTimeout(500);

    // Click the mode option
    const modeOption = await page.$(`text=${mode}`);
    if (modeOption) {
      await modeOption.click();
      await page.waitForTimeout(1000);
    }
  }

  // Type query
  const inputBox = await page.$('textarea, input[type="text"], [class*="input-box"]');
  if (inputBox) {
    await inputBox.fill(query);
    await page.waitForTimeout(500);

    // Submit
    const sendButton = await page.$('button[type="submit"], [class*="send-button"]');
    if (sendButton) {
      await sendButton.click();
    } else {
      await inputBox.press('Enter');
    }

    // Wait for response
    await waitForStreamComplete(page);

    // Take screenshots
    await screenshot(page, `${testName}-${mode}-final`);

    // Scroll through response to capture all content
    const messageContainer = await page.$('.message-container, [class*="message-list"]');
    if (messageContainer) {
      const scrollHeight = await page.evaluate(el => el.scrollHeight, messageContainer);
      const clientHeight = await page.evaluate(el => el.clientHeight, messageContainer);

      if (scrollHeight > clientHeight) {
        // Scroll to middle
        await page.evaluate((el) => el.scrollTop = el.scrollHeight / 2, messageContainer);
        await page.waitForTimeout(1000);
        await screenshot(page, `${testName}-${mode}-middle`);

        // Scroll to top
        await page.evaluate((el) => el.scrollTop = 0, messageContainer);
        await page.waitForTimeout(1000);
        await screenshot(page, `${testName}-${mode}-top`);
      }
    }

    // Extract key metrics
    const metrics = await page.evaluate(() => {
      const tokenUsage = document.querySelector('[class*="token-usage"], [class*="TokenUsage"]');
      const chainOfThought = document.querySelector('[class*="chain-of-thought"], [class*="ChainOfThought"]');
      const citations = document.querySelectorAll('[class*="citation"], [class*="Citation"]');
      const toolCalls = document.querySelectorAll('[class*="tool-call"], [class*="ToolCall"]');

      return {
        hasTokenUsage: tokenUsage !== null,
        hasChainOfThought: chainOfThought !== null,
        citationCount: citations.length,
        toolCallCount: toolCalls.length,
        messageCount: document.querySelectorAll('[class*="message"], [class*="Message"]').length
      };
    });

    console.log('Metrics:', metrics);
    return metrics;
  }

  return null;
}

async function main() {
  console.log('Starting AI Chat E2E tests...\n');

  const browser = await chromium.launch({
    headless: false,
    args: ['--window-size=1400,900']
  });

  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    deviceScaleFactor: 2
  });

  const page = await context.newPage();

  // Login
  console.log('Logging in...');
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  await page.fill('input[placeholder*="用户名"], input[name="username"]', 'demouser');
  await page.fill('input[placeholder*="密码"], input[name="password"]', 'DemoPass123');
  await page.click('button:has-text("登录"), button:has-text("下一步")');

  await page.waitForNavigation({ waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await screenshot(page, '00-login-success');

  // Test queries and modes
  const queries = [
    { query: '帮我研究下比亚迪的市场趋势', name: 'byd-research' },
    { query: '分析家庭资产负债，联网搜索优化建议', name: 'asset-analysis' }
  ];

  const modes = ['普通', 'Pro', 'Ultra'];

  const results = [];

  for (const { query, name } of queries) {
    for (const mode of modes) {
      try {
        const metrics = await testQuery(page, query, mode, name);
        results.push({ query, mode, metrics });
      } catch (err) {
        console.error(`Error testing ${name} with ${mode}:`, err.message);
        results.push({ query, mode, error: err.message });
      }
    }
  }

  // Summary
  console.log('\n=== Test Summary ===');
  console.log(JSON.stringify(results, null, 2));

  await browser.close();
  console.log('\n✓ Tests complete');
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
