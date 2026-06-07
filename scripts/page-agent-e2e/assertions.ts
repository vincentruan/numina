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
      if (!assertion.value) {
        return { type: assertion.type, passed: false, message: 'Missing required field: value' };
      }
      try {
        await page.waitForURL(`**/*${assertion.value}*`, { timeout });
      } catch { /* URL didn't match within timeout, check current state */ }
      const url = page.url();
      const passed = url.includes(assertion.value);
      return { type: assertion.type, passed, message: passed ? 'URL matches' : `URL "${url}" does not contain "${assertion.value}"`, expected: assertion.value, actual: url };
    }

    case 'url_equals': {
      if (!assertion.value) {
        return { type: assertion.type, passed: false, message: 'Missing required field: value' };
      }
      try {
        await page.waitForURL(assertion.value, { timeout });
      } catch { /* URL didn't match within timeout */ }
      const url = page.url();
      const passed = url === assertion.value;
      return { type: assertion.type, passed, message: passed ? 'URL matches exactly' : `URL "${url}" !== "${assertion.value}"`, expected: assertion.value, actual: url };
    }

    case 'text_visible': {
      if (!assertion.value) {
        return { type: assertion.type, passed: false, message: 'Missing required field: value' };
      }
      try {
        await page.getByText(assertion.value, { exact: false }).first().waitFor({ timeout, state: 'visible' });
        return { type: assertion.type, passed: true, message: `Text "${assertion.value}" is visible` };
      } catch {
        return { type: assertion.type, passed: false, message: `Text "${assertion.value}" not found within ${timeout}ms`, expected: assertion.value };
      }
    }

    case 'text_not_visible': {
      if (!assertion.value) {
        return { type: assertion.type, passed: false, message: 'Missing required field: value' };
      }
      try {
        await page.getByText(assertion.value, { exact: false }).first().waitFor({ timeout, state: 'visible' });
        return { type: assertion.type, passed: false, message: `Text "${assertion.value}" is visible but should not be`, expected: 'not visible', actual: 'visible' };
      } catch {
        return { type: assertion.type, passed: true, message: `Text "${assertion.value}" correctly not visible` };
      }
    }

    case 'locator_visible': {
      if (!assertion.selector) {
        return { type: assertion.type, passed: false, message: 'Missing required field: selector' };
      }
      try {
        await page.locator(assertion.selector).first().waitFor({ timeout, state: 'visible' });
        return { type: assertion.type, passed: true, message: `Locator "${assertion.selector}" is visible` };
      } catch {
        return { type: assertion.type, passed: false, message: `Locator "${assertion.selector}" not visible within ${timeout}ms`, expected: 'visible' };
      }
    }

    case 'locator_count': {
      if (!assertion.selector) {
        return { type: assertion.type, passed: false, message: 'Missing required field: selector' };
      }
      if (assertion.count === undefined) {
        return { type: assertion.type, passed: false, message: 'Missing required field: count' };
      }
      const count = await page.locator(assertion.selector).count();
      const passed = count === assertion.count;
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
