/* CTA 专项：full-only 站点必须复制 zijian-full.json；main 站点复制 zijian.json */
const PWCORE = 'C:/Users/Administrator/.workbuddy/binaries/node/versions/22.22.2-6/node_modules/@playwright/cli/node_modules/playwright-core';
const { chromium } = require(PWCORE);

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', args: ['--no-proxy-server', '--proxy-bypass-list=*'] });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, permissions: ['clipboard-read', 'clipboard-write'] });
  const page = await ctx.newPage();
  await page.goto('http://127.0.0.1:8765/index.html', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => document.querySelectorAll('.card').length > 30, { timeout: 20000 });

  // --- 多仓配置卡：totalSites=null 时怎么渲染 ---
  const multiIds = ['fish2018-ol-all', 'niubihu-tv8', 'noimank-muti', 'qist-0707', 'tushen6-lmw'];
  console.log('=== 多仓配置卡（totalSites = null）渲染文本 ===');
  for (const id of multiIds) {
    const t = await page.evaluate(id => {
      const c = document.getElementById('cfg-' + id);
      return c ? c.innerText.replace(/\n+/g, ' | ') : '(卡片不在 DOM 中)';
    }, id);
    console.log(`  ${id}: ${t}`);
  }
  const nullish = await page.evaluate(() => [...document.querySelectorAll('.card')]
    .map(c => ({ id: c.id, t: c.innerText.replace(/\n+/g, ' | ') }))
    .filter(x => /undefined|null|NaN/.test(x.t)));
  console.log('  含 undefined/null/NaN 的卡片:', nullish.length ? JSON.stringify(nullish) : '0 张');

  // --- 切到站点源 ---
  await page.click('#tab-sites');
  await page.waitForFunction(() => document.querySelectorAll('.card').length > 400, { timeout: 25000 });
  await page.waitForTimeout(600);

  console.log('\n=== full-only 站点卡结构 ===');
  const fHtml = await page.evaluate(() => {
    const c = [...document.querySelectorAll('.card')].find(x => /南瓜/.test(x.innerText));
    return c ? { id: c.id, html: c.outerHTML.slice(0, 1200) } : null;
  });
  console.log(fHtml ? fHtml.html : 'NOT FOUND');

  async function cta(hint) {
    return await page.evaluate(async (hint) => {
      const c = [...document.querySelectorAll('.card')].find(x => x.innerText.includes(hint));
      if (!c) return { err: 'card-not-found' };
      const btns = [...c.querySelectorAll('button')].map(b => ({
        txt: b.textContent.trim().slice(0, 20),
        aria: (b.getAttribute('aria-label') || '').slice(0, 30), cls: b.className,
      }));
      // 主 CTA：优先 btn-primary，否则第一个含"复制"的按钮
      const btn = c.querySelector('button.btn-primary') || [...c.querySelectorAll('button')].find(b => /复制/.test(b.textContent));
      if (!btn) return { err: 'cta-not-found', btns, cardText: c.innerText.slice(0, 200) };
      const label = btn.textContent.trim();
      const note = (c.innerText.match(/此站仅在扩展配置中[^\n]*/) || [''])[0];
      btn.click();
      await new Promise(r => setTimeout(r, 500));
      let clip = null; try { clip = await navigator.clipboard.readText(); } catch (e) { clip = 'ERR:' + e; }
      return { label, note, clip, btns };
    }, hint);
  }

  const cases = await page.evaluate(() => {
    const items = window.__TVBOX_FALLBACK__.sites.items;
    const f = items.filter(s => s.includedIn === 'full').slice(0, 2).map(s => s.name);
    const m = items.filter(s => s.includedIn === 'main').slice(0, 2).map(s => s.name);
    return { f, m };
  });
  console.log('\n=== 抽样 ===');
  console.log('  full-only:', JSON.stringify(cases.f), ' main:', JSON.stringify(cases.m));

  for (const n of cases.f) {
    const r = await cta(n);
    console.log(`\n  [full-only] ${n}`);
    console.log(`    主 CTA 文案 = ${JSON.stringify(r.label)}`);
    console.log(`    "仅扩展配置"提示 = ${JSON.stringify(r.note)}`);
    console.log(`    剪贴板 = ${JSON.stringify(r.clip)}`);
    console.log(`    卡片按钮 = ${JSON.stringify(r.btns)}`);
    console.log(`    判定: ${/zijian-full\.json$/.test((r.clip || '').trim()) ? '✅ 指向扩展配置' : '❌ 指向错误'}`);
  }
  for (const n of cases.m) {
    const r = await cta(n);
    console.log(`\n  [main] ${n}`);
    console.log(`    主 CTA 文案 = ${JSON.stringify(r.label)}`);
    console.log(`    剪贴板 = ${JSON.stringify(r.clip)}`);
    console.log(`    卡片按钮 = ${JSON.stringify(r.btns)}`);
    console.log(`    判定: ${/\/zijian\.json$/.test((r.clip || '').trim()) ? '✅ 指向主配置' : '❌ 指向错误'}`);
  }

  await browser.close();
})().catch(e => { console.error('FATAL', e); process.exit(1); });
