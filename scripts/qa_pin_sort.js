#!/usr/bin/env node
/* QA：从 index.html 原样抽取 sortItems / ensureShuffle，验证
   1) 置顶四条恒定排最前且按 pin 顺序
   2) 非置顶部分是洗牌序（不等于名字序），且同一会话内稳定
   3) sites tab 的旧排序分支不被破坏
   4) 真实 48 条数据跑通
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
if (!/function sortItems/.test(src) || !/function ensureShuffle/.test(src)) {
  throw new Error('抽取结果里没有 sortItems / ensureShuffle');
}

const WEIGHT = { ok: 0, reachable: 1, unknown: 2, untestable: 2, fail: 3 };
const stripEmoji = (s) => String(s || '').replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/gu, '');
const stateOf = (it) => it.__state || 'ok';

/* 被测代码把 tab / store 当自由变量用，这里必须提供同名 var 绑定，
   否则 new Function 里会抛 ReferenceError。 */
const factory = new Function('WEIGHT', 'stripEmoji', 'stateOf',
  'var tab = "configs"; var store = { configs: [] };\n' + src +
  '\nreturn { sortItems: sortItems, ensureShuffle: ensureShuffle,' +
  ' rankLen: function(){ return shuffleRank ? Object.keys(shuffleRank).length : 0; },' +
  ' setTab: function(t){ tab = t; }, setStore: function(s){ store = s; } };'
);
const api = factory(WEIGHT, stripEmoji, stateOf);

const pinned = [
  { id: 'feimao', name: '肥猫', pin: 1 },
  { id: 'qist-fty', name: '饭太硬', pin: 2 },
  { id: '9280-kstore', name: '王二小', pin: 3 },
  { id: 'github-inliang', name: '自建综合配置', pin: 4 },
];
const rest = [
  { id: 'a1', name: 'AAA', pin: 0 }, { id: 'b2', name: 'BBB', pin: 0 },
  { id: 'c3', name: 'CCC', pin: 0 }, { id: 'd4', name: 'DDD', pin: 0 },
  { id: 'e5', name: 'EEE', pin: 0 }, { id: 'f6', name: 'FFF', pin: 0 },
  { id: 'g7', name: 'GGG', pin: 0 }, { id: 'h8', name: 'HHH', pin: 0 },
];
api.setStore({ configs: [...rest, ...pinned] }); // 故意把置顶打散在后面

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log('  ok   ' + name); }
  else { fail++; console.log('  FAIL ' + name + (extra ? '  -> ' + extra : '')); }
}

console.log('== 1) 置顶顺序 ==');
const out1 = api.sortItems([...rest, ...pinned]);
const names1 = out1.map((x) => x.name);
check('前四条是肥猫/饭太硬/王二小/自建',
  JSON.stringify(names1.slice(0, 4)) === JSON.stringify(['肥猫', '饭太硬', '王二小', '自建综合配置']),
  names1.slice(0, 4).join(','));
check('pin 严格 1,2,3,4',
  JSON.stringify(out1.slice(0, 4).map((x) => x.pin)) === '[1,2,3,4]',
  out1.slice(0, 4).map((x) => x.pin).join(','));

console.log('== 2) 其余随机且同一会话稳定 ==');
const rest1 = out1.slice(4).map((x) => x.id);
const nameOrder = rest.map((x) => x.id).sort();
check('非置顶不是名字序（确实洗过牌）', JSON.stringify(rest1) !== JSON.stringify(nameOrder), rest1.join(','));
check('非置顶 8 条齐全无重复', rest1.length === 8 && new Set(rest1).size === 8);
const out2 = api.sortItems([...pinned, ...rest]);
check('输入顺序打乱后结果一致（排序确定）',
  JSON.stringify(out2.map((x) => x.id)) === JSON.stringify(out1.map((x) => x.id)));

console.log('== 3) 会话内 rank 覆盖全量配置 ==');
check('shuffleRank 覆盖 12 条', api.rankLen() === 12, String(api.rankLen()));

console.log('== 4) sites tab 旧分支不被破坏 ==');
api.setTab('sites');
const siteList = [
  { name: '乙站', type: 3, __state: 'ok' },
  { name: '甲站', type: 3, __state: 'ok' },
  { name: '丙站', type: 3, __state: 'fail' },
];
let s2 = null, threw = false;
try { s2 = api.sortItems(siteList.map((x) => ({ ...x }))); } catch (e) { threw = true; console.log(e.message); }
check('sites 排序不抛错且保持 3 条', !threw && Array.isArray(s2) && s2.length === 3,
  s2 ? s2.map((x) => x.name).join(',') : 'n/a');
api.setTab('configs');

console.log('== 5) 真实 48 条数据 ==');
const real = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'docs', 'data', 'configs.json'), 'utf8'));
api.setStore({ configs: real.items.map((x) => ({ ...x })) });
const r1 = api.sortItems(real.items.map((x) => ({ ...x })));
check('总数 48', r1.length === 48, String(r1.length));
check('置顶四条在最前',
  JSON.stringify(r1.slice(0, 4).map((x) => x.name)) === JSON.stringify(['肥猫', '饭太硬', '王二小', '自建综合配置']),
  r1.slice(0, 4).map((x) => x.name).join(','));
const r2 = api.sortItems(real.items.map((x) => ({ ...x })));
check('两次渲染顺序一致', JSON.stringify(r1.map((x) => x.id)) === JSON.stringify(r2.map((x) => x.id)));

console.log();
console.log(pass + ' 通过 / ' + fail + ' 失败');
process.exit(fail ? 1 : 0);
