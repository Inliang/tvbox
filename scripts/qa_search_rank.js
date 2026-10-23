#!/usr/bin/env node
/* QA：搜索排序「完全匹配 > 名称前缀 > 名称包含 > 其他字段」
   1) 配置 tab：四级匹配各就各位
   2) 完全匹配压过置顶（同级内才按 pin）
   3) 无关键词时保持置顶+随机的原顺序
   4) 站点 tab：同样四级 + 同级按可用性
   5) emoji 名称去符号后仍能完全匹配
   6) 真实数据：搜「肥猫」置顶肥猫排最前
*/
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'docs', 'index.html'), 'utf8');

function grab(startMark, endMark) {
  const i = html.indexOf(startMark);
  const j = html.indexOf(endMark, i);
  if (i < 0 || j < 0) throw new Error('marker not found: ' + startMark + ' / ' + endMark);
  return html.slice(i, j);
}

const src = grab('var shuffleRank = null;', '/* ---------- render ----------');
if (!/function searchTier/.test(src) || !/function sortItems/.test(src)) {
  throw new Error('抽取结果里没有 searchTier / sortItems');
}

const WEIGHT = { ok: 0, reachable: 1, unknown: 2, untestable: 2, fail: 3 };
const stripEmoji = (s) => String(s || '').replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/gu, '');
const stateOf = (it) => it.__state || 'ok';

const factory = new Function('WEIGHT', 'stripEmoji', 'stateOf',
  'var tab = "configs"; var store = { configs: [] }; var q = "";\n' + src +
  '\nreturn { sortItems: sortItems, searchTier: searchTier, ensureShuffle: ensureShuffle,' +
  ' setTab: function(t){ tab = t; }, setStore: function(s){ store = s; },' +
  ' setQ: function(v){ q = v; } };'
);
const api = factory(WEIGHT, stripEmoji, stateOf);

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log('  ok   ' + name); }
  else { fail++; console.log('  FAIL ' + name + (extra ? '  -> ' + extra : '')); }
}
const ids = (arr) => arr.map((x) => x.id || x.name).join(',');

console.log('== 1) 配置 tab 四级匹配 ==');
api.setTab('configs');
api.setStore({ configs: [
  { id: 'note-hit', name: '别的配置', note: '饭太硬的备用源', pin: 0 },
  { id: 'contains', name: '某某饭太硬镜像', pin: 0 },
  { id: 'prefix',   name: '饭太硬备用域名', pin: 0 },
  { id: 'exact',    name: '饭太硬', pin: 2 },
  { id: 'url-exact', name: '未知配置', url: 'https://x.example/api.json', pin: 0 },
] });
api.setQ('饭太硬');
let r = api.sortItems([
  { id: 'note-hit', name: '别的配置', note: '饭太硬的备用源', pin: 0 },
  { id: 'contains', name: '某某饭太硬镜像', pin: 0 },
  { id: 'prefix',   name: '饭太硬备用域名', pin: 0 },
  { id: 'exact',    name: '饭太硬', pin: 2 },
]);
check('完全 > 前缀 > 包含 > 备注', ids(r) === 'exact,prefix,contains,note-hit', ids(r));

console.log('== 2) 完全匹配压过置顶 ==');
api.setQ('abc');
r = api.sortItems([
  { id: 'pin-fuzzy', name: 'ABC-长名称', pin: 1 },
  { id: 'plain-exact', name: 'abc', pin: 0 },
  { id: 'pin-exact', name: 'Abc', pin: 4 },
]);
check('两个完全匹配都在前（pin 序），模糊的置顶殿后',
  ids(r) === 'pin-exact,plain-exact,pin-fuzzy', ids(r));

console.log('== 3) 无关键词时保持原顺序 ==');
api.setQ('');
const noQ = [
  { id: 'n1', name: 'ZZZ', pin: 0 }, { id: 'n2', name: 'AAA', pin: 0 },
  { id: 'p1', name: '肥猫', pin: 1 }, { id: 'p2', name: '饭太硬', pin: 2 },
  { id: 'p3', name: '王二小', pin: 3 }, { id: 'p4', name: '自建综合配置', pin: 4 },
];
api.setStore({ configs: noQ });
r = api.sortItems(noQ.map((x) => ({ ...x })));
check('置顶四条仍排最前', ids(r).startsWith('p1,p2,p3,p4'), ids(r));
check('关键词为空时 searchTier 返回 9（不干预）', api.searchTier({ name: 'x' }, '') === 9);

console.log('== 4) 站点 tab 四级 + 同级按可用性 ==');
api.setTab('sites');
api.setQ('cctv1');
r = api.sortItems([
  { id: 's-api',  name: '别的台',       api: 'cctv1-rtmp', __state: 'ok' },
  { id: 's-ct',   name: '高清 CCTV1',   api: 'y',          __state: 'ok' },
  { id: 's-pre',  name: 'CCTV1 综合',   api: 'x',          __state: 'ok' },
  { id: 's-ex',   name: 'CCTV1',        api: 'z',          __state: 'fail' },
]);
check('完全 > 前缀 > 包含 > api 命中', ids(r) === 's-ex,s-pre,s-ct,s-api', ids(r));
api.setQ('央视');
r = api.sortItems([
  { id: 'a', name: '央视一套', __state: 'fail' },
  { id: 'b', name: '央视二套', __state: 'ok' },
]);
check('同级（都是前缀）按可用性排：ok 在前', ids(r) === 'b,a', ids(r));

console.log('== 5) emoji 名称去符号后完全匹配 ==');
api.setQ('肥猫');
check('🐱肥猫 去符号后 === 肥猫 → tier 0',
  api.searchTier({ name: '🐱肥猫', api: 'x' }, '肥猫') === 0);
check('🐱肥猫线路 去符号后前缀命中 → tier 1',
  api.searchTier({ name: '🐱肥猫线路', api: 'x' }, '肥猫') === 1);

console.log('== 6) 真实数据 ==');
api.setTab('configs');
const real = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'docs', 'data', 'configs.json'), 'utf8'));
api.setStore({ configs: real.items.map((x) => ({ ...x })) });
api.setQ('肥猫');
r = api.sortItems(real.items.map((x) => ({ ...x })));
check('总数不变 48', r.length === 48, String(r.length));
check('「肥猫」置顶条排第一（完全匹配）', r[0].name === '肥猫', r.slice(0, 3).map((x) => x.name).join(','));
const tier0 = r.filter((x) => api.searchTier(x, '肥猫') === 0).length;
check('完全匹配的排在模糊匹配之前',
  api.searchTier(r[r.length - 1], '肥猫') >= 2 &&
  r.findIndex((x) => api.searchTier(x, '肥猫') >= 2) >= tier0,
  'tier0=' + tier0);

console.log('== 7) 真实站点数据 ==');
api.setTab('sites');
const realSites = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'docs', 'data', 'sites.json'), 'utf8'));
const sItems = (realSites.items || []).map((x) => ({ ...x }));
api.setStore({ configs: [] });
api.setQ('腾讯');
r = api.sortItems(sItems.slice(0, 200).map((x) => ({ ...x })));
const tiers = r.map((x) => api.searchTier(x, '腾讯'));
let mono = true;
for (let i = 1; i < tiers.length; i++) if (tiers[i] < tiers[i - 1]) { mono = false; break; }
check('站点排序按 tier 单调不减', mono, tiers.slice(0, 12).join(','));

console.log();
console.log(pass + ' 通过 / ' + fail + ' 失败');
process.exit(fail ? 1 : 0);
