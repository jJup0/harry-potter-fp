const puppeteer = require('puppeteer');
const path = require('path');
const assert = require('assert');

const DASHBOARD = 'file://' + path.resolve(__dirname, '../output/dashboard.html');
const SCREENSHOT_DIR = '/tmp/dashboard_screenshots';

async function run() {
  const fs = require('fs');
  if (!fs.existsSync(SCREENSHOT_DIR)) fs.mkdirSync(SCREENSHOT_DIR, {recursive: true});

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  const page = await browser.newPage();
  await page.setViewport({width: 1400, height: 900});
  await page.goto(DASHBOARD, {waitUntil: 'networkidle0', timeout: 30000});

  // Test 1: Page loads with characters
  const charCount = await page.evaluate(() => CHARACTER_DATA.length);
  console.log(`✓ Loaded ${charCount} characters`);
  assert(charCount > 100, `Expected >100 characters, got ${charCount}`);

  // Test 2: Presence filter shows correct count
  const presenceText = await page.$eval('#presence-count', el => el.textContent);
  console.log(`✓ Presence count: ${presenceText}`);

  // Test 3: Check screenplay_words are actual word counts (not minutes)
  const maxScreenplay = await page.evaluate(() =>
    Math.max(...CHARACTER_DATA.map(c => c.screenplay_words))
  );
  console.log(`✓ Max screenplay words: ${maxScreenplay}`);
  assert(maxScreenplay > 1000, `screenplay_words looks like minutes not words: max=${maxScreenplay}`);

  // Test 4: Click a character and check justification panel
  await page.evaluate(() => {
    showCharacterPanel('Harry Potter');
  });
  await page.waitForSelector('#detail-panel.active', {timeout: 5000});
  const detailText = await page.$eval('#detail-panel', el => el.textContent);
  const hasJustification = !detailText.includes('No justification available');
  console.log(`✓ Harry Potter detail panel: justification ${hasJustification ? 'present' : 'MISSING'}`);
  assert(hasJustification, 'Harry Potter should have justifications');
  await page.screenshot({path: path.join(SCREENSHOT_DIR, '01_harry_detail.png'), fullPage: false});

  // Test 5: Check Ginny has justification too
  await page.evaluate(() => showCharacterPanel('Ginny Weasley'));
  await new Promise(r => setTimeout(r, 500));
  const ginnyText = await page.$eval('#detail-panel', el => el.textContent);
  const ginnyHasJust = !ginnyText.includes('No justification available');
  console.log(`✓ Ginny Weasley detail panel: justification ${ginnyHasJust ? 'present' : 'MISSING'}`);
  assert(ginnyHasJust, 'Ginny Weasley should have justifications');
  await page.screenshot({path: path.join(SCREENSHOT_DIR, '02_ginny_detail.png'), fullPage: false});

  // Test 6: Set filter to min 1000 screenplay words
  await page.evaluate(() => {
    const slider = document.getElementById('film-slider');
    slider.value = 1000;
    slider.dispatchEvent(new Event('input'));
  });
  await new Promise(r => setTimeout(r, 500));
  const filteredText = await page.$eval('#presence-count', el => el.textContent);
  console.log(`✓ After filter (1000 screenplay words): ${filteredText}`);
  await page.screenshot({path: path.join(SCREENSHOT_DIR, '03_filtered.png'), fullPage: false});

  // Test 7: Plotly charts rendered
  const plotlyCharts = await page.$$('.plotly-graph-div');
  console.log(`✓ ${plotlyCharts.length} Plotly charts rendered`);
  assert(plotlyCharts.length >= 2, `Expected >=2 charts, got ${plotlyCharts.length}`);

  // Test 8: Full page screenshot
  await page.evaluate(() => {
    const slider = document.getElementById('film-slider');
    slider.value = 0;
    slider.dispatchEvent(new Event('input'));
  });
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({path: path.join(SCREENSHOT_DIR, '04_full_page.png'), fullPage: true});
  console.log('✓ Full page screenshot saved');

  await browser.close();
  console.log(`\nAll tests passed! Screenshots in ${SCREENSHOT_DIR}`);
}

run().catch(e => {
  console.error('FAILED:', e.message);
  process.exit(1);
});
