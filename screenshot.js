const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost/numina';
const TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzZmI4ZGE5Ni1iMjQzLTQzYjgtOTI2My02M2U1M2M0MGE2MzYiLCJleHAiOjE3NzM5MjQ1MzUsInR5cGUiOiJhY2Nlc3MifQ.j7s_bREsYEFIXG33Zo98eHSScOUxlQFoktcuQZoBo8o';

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  const screenshotDir = path.join(__dirname, 'screenshots');
  if (!fs.existsSync(screenshotDir)) {
    fs.mkdirSync(screenshotDir, { recursive: true });
  }

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const results = [];

  try {
    const page = await browser.newPage();
    
    await page.setViewport({
      width: 375,
      height: 812,
      isMobile: true,
      hasTouch: true
    });

    // Set auth token via localStorage
    console.log('Setting auth token...');
    await page.goto(BASE_URL + '/', { waitUntil: 'networkidle0', timeout: 30000 });
    await page.evaluate((token) => {
      localStorage.setItem('token', token);
      localStorage.setItem('refreshToken', 'dummy');
      localStorage.setItem('user', JSON.stringify({username: 'uxtest', display_name: 'UX测试用户'}));
    }, TOKEN);

    // 1. Dashboard
    console.log('1. Loading dashboard...');
    await page.goto(BASE_URL + '/', { waitUntil: 'networkidle0', timeout: 30000 });
    await sleep(3000);
    await page.screenshot({ path: path.join(screenshotDir, '01-dashboard.png'), fullPage: true });
    results.push({ page: 'Dashboard', file: '01-dashboard.png' });

    // 2. Assets list
    console.log('2. Loading assets list...');
    await page.goto(BASE_URL + '/assets', { waitUntil: 'networkidle0', timeout: 30000 });
    await sleep(2000);
    await page.screenshot({ path: path.join(screenshotDir, '02-assets-list.png'), fullPage: true });
    results.push({ page: 'Assets List', file: '02-assets-list.png' });

    // 3. Asset detail (first asset)
    console.log('3. Loading asset detail...');
    const assetsData = await page.evaluate(() => document.body.innerHTML);
    const firstAssetMatch = assetsData.match(/\/assets\/([a-f0-9-]+)/);
    if (firstAssetMatch) {
      await page.goto(BASE_URL + '/assets/' + firstAssetMatch[1], { waitUntil: 'networkidle0', timeout: 30000 });
      await sleep(2000);
      await page.screenshot({ path: path.join(screenshotDir, '03-asset-detail.png'), fullPage: true });
      results.push({ page: 'Asset Detail', file: '03-asset-detail.png' });
    }

    // 4. Liabilities list
    console.log('4. Loading liabilities list...');
    await page.goto(BASE_URL + '/liabilities', { waitUntil: 'networkidle0', timeout: 30000 });
    await sleep(2000);
    await page.screenshot({ path: path.join(screenshotDir, '04-liabilities-list.png'), fullPage: true });
    results.push({ page: 'Liabilities List', file: '04-liabilities-list.png' });

    // 5. Family page
    console.log('5. Loading family page...');
    await page.goto(BASE_URL + '/family', { waitUntil: 'networkidle0', timeout: 30000 });
    await sleep(2000);
    await page.screenshot({ path: path.join(screenshotDir, '05-family.png'), fullPage: true });
    results.push({ page: 'Family', file: '05-family.png' });

    // 6. Settings page
    console.log('6. Loading settings page...');
    await page.goto(BASE_URL + '/settings', { waitUntil: 'networkidle0', timeout: 30000 });
    await sleep(2000);
    await page.screenshot({ path: path.join(screenshotDir, '06-settings.png'), fullPage: true });
    results.push({ page: 'Settings', file: '06-settings.png' });

    // 7. Categories
    console.log('7. Loading categories page...');
    await page.goto(BASE_URL + '/settings/categories', { waitUntil: 'networkidle0', timeout: 30000 });
    await sleep(2000);
    await page.screenshot({ path: path.join(screenshotDir, '07-categories.png'), fullPage: true });
    results.push({ page: 'Categories', file: '07-categories.png' });

    // 8. Login page (clear storage)
    console.log('8. Loading login page...');
    await page.evaluate(() => localStorage.clear());
    await page.goto(BASE_URL + '/login', { waitUntil: 'networkidle0', timeout: 30000 });
    await sleep(1000);
    await page.screenshot({ path: path.join(screenshotDir, '08-login.png'), fullPage: true });
    results.push({ page: 'Login', file: '08-login.png' });

    // 9. Register page
    console.log('9. Loading register page...');
    await page.goto(BASE_URL + '/register', { waitUntil: 'networkidle0', timeout: 30000 });
    await sleep(1000);
    await page.screenshot({ path: path.join(screenshotDir, '09-register.png'), fullPage: true });
    results.push({ page: 'Register', file: '09-register.png' });

    console.log('\nScreenshots saved:');
    results.forEach(r => console.log(`  - ${r.file}: ${r.page}`));

  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
}

main();