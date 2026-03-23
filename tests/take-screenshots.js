const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');
const http = require('http');

const SCREENSHOT_DIR = path.join(__dirname, 'screenshots');
if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

// 先用 http 模块获取 token（不依赖浏览器）
function getToken() {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({ username: 'uxtest', password: 'Test123456' });
    const req = http.request({
      hostname: 'localhost', port: 80, path: '/numina/api/v1/auth/login',
      method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': data.length }
    }, (res) => {
      let body = '';
      // 跟随重定向
      if (res.statusCode === 307) {
        const loc = res.headers.location;
        const req2 = http.request(loc, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': data.length } }, (res2) => {
          let b = '';
          res2.on('data', c => b += c);
          res2.on('end', () => resolve(JSON.parse(b).access_token));
        });
        req2.write(data);
        req2.end();
        return;
      }
      res.on('data', c => body += c);
      res.on('end', () => resolve(JSON.parse(body).access_token));
    });
    req.on('error', reject);
    req.write(data);
    req.end();
  });
}

// 每个页面用独立浏览器实例截图
async function captureOne(name, urlPath, token, clearStorage) {
  let browser;
  try {
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--single-process']
    });
    const page = await browser.newPage();
    await page.setViewport({ width: 375, height: 812, isMobile: true });

    if (!clearStorage && token) {
      // 先访问一个页面设置 localStorage
      await page.goto('http://localhost/numina/login', { waitUntil: 'domcontentloaded', timeout: 10000 });
      await page.evaluate((t) => {
        localStorage.setItem('token', t);
        localStorage.setItem('refreshToken', 'dummy');
      }, token);
    }

    if (clearStorage) {
      await page.goto('http://localhost/numina/login', { waitUntil: 'domcontentloaded', timeout: 10000 });
      await page.evaluate(() => localStorage.clear());
    }

    await page.goto('http://localhost/numina' + urlPath, { waitUntil: 'networkidle2', timeout: 20000 });
    await new Promise(r => setTimeout(r, 3000));
    const filePath = path.join(SCREENSHOT_DIR, name + '.png');
    await page.screenshot({ path: filePath, fullPage: true });
    console.log(`✓ ${name}.png`);
    return true;
  } catch (e) {
    console.log(`✗ ${name}: ${e.message}`);
    return false;
  } finally {
    if (browser) await browser.close().catch(() => {});
  }
}

(async () => {
  console.log('Getting token...');
  const token = await getToken();
  console.log('Token:', token ? 'OK' : 'FAIL');

  const tasks = [
    { name: '01-dashboard', path: '/' },
    { name: '02-assets', path: '/assets' },
    { name: '03-liabilities', path: '/liabilities' },
    { name: '04-family', path: '/family' },
    { name: '05-settings', path: '/settings' },
    { name: '06-login', path: '/login', clear: true },
    { name: '07-register', path: '/register', clear: true },
  ];

  let ok = 0, fail = 0;
  for (const t of tasks) {
    const result = await captureOne(t.name, t.path, token, t.clear);
    result ? ok++ : fail++;
  }
  console.log(`\nDone: ${ok} ok, ${fail} failed`);
})();
