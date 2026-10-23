#!/usr/bin/env node
/* QA：用真实浏览器渲染 index.html，实测卡片高度分布。
   结构一致不等于视觉等高——只有布局引擎的能量出真高度。 */
const path = require('path');
const fs = require('fs');

const ROOT = path.join(__dirname, '..');
const HTML = path.join(ROOT, 'docs', 'index.html');

(async () => {
  const { chromium } = require('playwright');
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 }, deviceScaleFactor: 2 });
  await page.goto('file:///' + HTML.replace(/\\/g, '/'));
  await page.waitForSelector('.card', { timeout: 15000 });
  /* 必须关掉 content-visibility:auto —— 折叠卡量到的是 contain-intrinsic-size
     的占位高度，不是真实高度。不关掉会得到"等高"的假象。 */
  await page.addStyleTag({ content: '.card{content-visibility:visible!important}' });
  await page.waitForTimeout(400);

  async function measure(label) {
    const data = await page.evaluate(() => {
      const cards = [...document.querySelectorAll('#list > .card')];
      return cards.map((c) => ({
        h: Math.round(c.getBoundingClientRect().height),
        pinned: c.classList.contains('is-pinned'),
        name: (c.querySelector('.card-name') || {}).textContent || '',
        kids: [...c.children].map((k) => k.className.split(' ')[0]),
      }));
    });
    const hs = data.map((d) => d.h);
    const dist = {};
    hs.forEach((h) => { dist[h] = (dist[h] || 0) + 1; });
    const uniq = Object.keys(dist).map(Number).sort((a, b) => a - b);
    console.log('== ' + label + ' ==');
    console.log('  卡片数 ' + data.length);
    console.log('  高度取值 ' + JSON.stringify(dist));
    console.log('  min=' + Math.min(...hs) + ' max=' + Math.max(...hs) + ' 极差=' + (Math.max(...hs) - Math.min(...hs)));
    // 每张卡的子块序列必须一致
    const shapes = {};
    data.forEach((d) => { const k = d.kids.join('>'); shapes[k] = (shapes[k] || 0) + 1; });
    console.log('  子块序列: ' + JSON.stringify(shapes));
    return data;
  }

  const cfgs = await measure('整包配置（双列 @1440）');
  const tall = cfgs.filter((d) => d.h > 206).slice(0, 6).map((d) => d.name + ':' + d.h);
  if (tall.length) console.log('  偏高样本: ' + JSON.stringify(tall));
  await page.screenshot({ path: path.join(ROOT, 'data', 'qa-card-configs.png'), fullPage: false });

  // 切到站点源
  await page.click('#tab-sites');
  await page.waitForTimeout(500);
  const sites = await measure('站点源（双列 @1440）');
  await page.screenshot({ path: path.join(ROOT, 'data', 'qa-card-sites.png'), fullPage: false });

  // 手机单列
  await page.setViewportSize({ width: 390, height: 900 });
  await page.waitForTimeout(300);
  await page.click('#tab-configs');
  await page.waitForTimeout(400);
  await measure('整包配置（单列 @390）');
  await page.screenshot({ path: path.join(ROOT, 'data', 'qa-card-mobile.png'), fullPage: false });

  await browser.close();

  // 判定：双列下极差应 <= 2px（origin 卡造成的少量差异可接受）
  const hs = cfgs.map((d) => d.h);
  const span = Math.max(...hs) - Math.min(...hs);
  const shapes = new Set(cfgs.map((d) => d.kids.join('>')));
  console.log();
  console.log('配置卡高度极差 ' + span + 'px，子块序列种类 ' + shapes.size);
  if (span > 2) { console.log('FAIL：配置卡高度仍不齐'); process.exit(1); }
  if (shapes.size !== 1) { console.log('FAIL：配置卡子块结构不一致'); process.exit(1); }
  console.log('PASS：配置卡等高且结构一致');
})().catch((e) => { console.error('ERROR', e); process.exit(1); });
