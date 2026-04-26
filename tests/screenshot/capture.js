const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const BASE_URL = 'http://localhost/';
const SCREENSHOTS_DIR = path.join(__dirname, 'screenshots');
const VIEWPORT = { width: 375, height: 812 };

// 统一测试账号
const USERNAME = 'demouser';
const PASSWORD = 'DemoPass123';

// API base URL for getting token
const API_BASE = 'http://localhost/api/v1';

async function getAuthToken() {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: USERNAME, password: PASSWORD })
  });
  const data = await response.json();
  // API wraps responses in {code, message, data}
  const payload = data.data || data;
  return payload.access_token;
}

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function takeScreenshot(page, name, description) {
  if (!fs.existsSync(SCREENSHOTS_DIR)) {
    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  }
  const filepath = path.join(SCREENSHOTS_DIR, `${name}.png`);
  await page.screenshot({ path: filepath, fullPage: false });
  console.log(`✓ Screenshot: ${name}.png (${description})`);
  return filepath;
}

async function waitForPageLoad(page) {
  await page.waitForNetworkIdle({ idleTime: 1000, timeout: 10000 }).catch(() => {});
  await sleep(500);
}

async function main() {
  console.log('Starting acceptance test screenshots...');
  console.log('Test account: demouser');
  console.log('==========================================\n');

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport(VIEWPORT);

  // Login via form to get httpOnly cookie
  console.log('Logging in via form...');
  await page.goto(`${BASE_URL}login`, { waitUntil: 'networkidle2' });
  await sleep(500);

  // Fill username and password
  const usernameInput = await page.$('input[type="text"], input[name="username"], .van-field__control');
  const inputs = await page.$$('.van-field__control');
  if (inputs.length >= 2) {
    await inputs[0].click({ clickCount: 3 });
    await inputs[0].type(USERNAME);
    await inputs[1].click({ clickCount: 3 });
    await inputs[1].type(PASSWORD);
  }
  await sleep(300);

  // Click login button
  const loginBtn = await page.$('.van-button--primary, button[type="submit"]');
  if (loginBtn) {
    await loginBtn.click();
    await sleep(2000);
  }
  console.log('Login submitted, current URL:', page.url(), '\n');

  // ===========================================
  // 1. LOGIN & AUTH PAGES
  // ===========================================
  console.log('Section 1: Authentication Pages');
  console.log('----------------------------------');

  await page.goto(`${BASE_URL}login`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '01-login-page', 'Login page');

  await page.goto(`${BASE_URL}register`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '02-register-page', 'Register page');

  await page.goto(`${BASE_URL}join-family`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '03-join-family-page', 'Join family page');

  // ===========================================
  // 2. DASHBOARD
  // ===========================================
  console.log('\nSection 2: Dashboard');
  console.log('----------------------------------');

  await page.goto(BASE_URL, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '04-dashboard', 'Dashboard overview');

  await page.evaluate(() => window.scrollTo(0, 500));
  await sleep(300);
  await takeScreenshot(page, '05-dashboard-charts', 'Dashboard charts');

  // ===========================================
  // 3. ASSETS
  // ===========================================
  console.log('\nSection 3: Assets');
  console.log('----------------------------------');

  await page.goto(`${BASE_URL}assets`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '06-assets-list', 'Assets list');

  const filterBtn = await page.$('[data-testid="filter-btn"], .van-dropdown-menu');
  if (filterBtn) {
    await filterBtn.click();
    await sleep(300);
    await takeScreenshot(page, '07-assets-filter', 'Assets filter panel');
  }

  await page.goto(`${BASE_URL}assets`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  const firstAsset = await page.$('.asset-card, .van-cell-group');
  if (firstAsset) {
    await firstAsset.click();
    await waitForPageLoad(page);
    await takeScreenshot(page, '08-asset-detail', 'Asset detail page');
  }

  // Asset form (create) - 验证优化后的界面
  await page.goto(`${BASE_URL}assets/new`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '09-asset-create-form', 'Asset create form (optimized)');

  // ===========================================
  // 4. LIABILITIES
  // ===========================================
  console.log('\nSection 4: Liabilities');
  console.log('----------------------------------');

  await page.goto(`${BASE_URL}liabilities`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '10-liabilities-list', 'Liabilities list');

  const firstLiability = await page.$('.liability-card, .van-cell-group');
  if (firstLiability) {
    await firstLiability.click();
    await waitForPageLoad(page);
    await takeScreenshot(page, '11-liability-detail', 'Liability detail page');
  }

  // ===========================================
  // 5. WISHES
  // ===========================================
  console.log('\nSection 5: Wishes');
  console.log('----------------------------------');

  await page.goto(`${BASE_URL}wishes`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '12-wishes-list', 'Wishes list');

  // ===========================================
  // 6. STATS
  // ===========================================
  console.log('\nSection 6: Statistics');
  console.log('----------------------------------');

  await page.goto(`${BASE_URL}stats`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '13-stats-page', 'Statistics page');

  // ===========================================
  // 7. FAMILY
  // ===========================================
  console.log('\nSection 7: Family');
  console.log('----------------------------------');

  await page.goto(`${BASE_URL}family`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '14-family-page', 'Family page');

  // ===========================================
  // 8. SETTINGS & MANAGEMENT
  // ===========================================
  console.log('\nSection 8: Settings & Management');
  console.log('----------------------------------');

  await page.goto(`${BASE_URL}settings`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '15-settings-page', 'Settings page');

  await page.goto(`${BASE_URL}settings/categories`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '16-category-manage', 'Category management');

  await page.goto(`${BASE_URL}settings/tags`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '17-tag-manage', 'Tag management');

  // ===========================================
  // 9. AI CHAT PAGE
  // ===========================================
  console.log('\nSection 9: AI Chat');
  console.log('----------------------------------');

  await page.goto(`${BASE_URL}ai/chat`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '18-ai-chat-empty', 'AI chat empty state');

  // AI Hub
  await page.goto(`${BASE_URL}ai`, { waitUntil: 'networkidle2' });
  await waitForPageLoad(page);
  await takeScreenshot(page, '19-ai-hub', 'AI hub page');

  // ===========================================
  // SUMMARY
  // ===========================================
  console.log('==========================================');
  console.log('Screenshot capture completed!');
  console.log('==========================================\n');

  const files = fs.readdirSync(SCREENSHOTS_DIR).filter(f => f.endsWith('.png'));
  console.log(`Total screenshots: ${files.length}`);
  console.log('\nScreenshot files:');
  files.forEach(f => console.log(`  - screenshots/${f}`));

  await browser.close();
}

main().catch(console.error);