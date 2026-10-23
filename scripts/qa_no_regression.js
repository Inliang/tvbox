// 全量无回归验证：用 docs/data/sites.json 里真实的 583 条数据跑 buildSiteCard，
// 证明 originProbe 改动没有把任何一张卡渲染炸掉。
// 做法：从 index.html 原样取出 buildSiteCard，只 stub 它依赖的外部函数，
// 用一个极简 DOM 替身接住 appendChild / addEventListener。
const fs = require('fs');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, '..', 'docs', 'index.html'), 'utf8');
const data = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'docs', 'data', 'sites.json'), 'utf8'));

function grab(name) {
  const start = html.indexOf('function ' + name + '(');
  if (start < 0) throw new Error('页面上找不到 ' + name);
  const open = html.indexOf('{', start);
  let depth = 0, end = -1;
  for (let i = open; i < html.length; i++) {
    if (html[i] === '{') depth++;
    else if (html[i] === '}') { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  return html.slice(start, end);
}

// 极简 DOM 替身：只记录结构，不真的建节点
function El(tag, props) {
  this.tag = tag; this.props = props || {}; this.children = []; this.listeners = {};
  this._text = '';
}
El.prototype.appendChild = function (c) { this.children.push(c); return c; };
El.prototype.addEventListener = function (t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); };
Object.defineProperty(El.prototype, 'textContent', {
  get: function () {
    return this._text + this.children.map(c => c.textContent || '').join('');
  },
  set: function (v) { this._text = String(v); this.children = []; }
});

// 只 stub 被测函数之外的依赖，全部返回无害替身
const stubs = `
function h(tag, props){ var e = new El(tag, props || {});
  if(props && props.text !== undefined) e.textContent = props.text;
  var kids = Array.prototype.slice.call(arguments, 2);
  kids.forEach(function(k){ if(k) e.appendChild(typeof k === 'string' ? new El('#text', {text:k}) : k); });
  return e; }
function icon(){ return new El('svg'); }
function doCopy(){}
function gotoConfig(){}
function openSiteSheet(){}
function cfgForSite(){ return null; }
function ctaFor(s){ return null; }
function siteDomId(s){ return 's_' + (s.id || Math.random().toString(36).slice(2)); }
function statusPill(){ return new El('span'); }
function siteState(s){ return 'untestable'; }
function hostOf(u){ return String(u || '').replace(/^https?:\\/\\//,'').split('/')[0]; }
function isLocalHost(u){ return /127\\.0\\.0\\.1|localhost/.test(u || ''); }
function isTemplateUrl(u){ return /[{}]/.test(u || ''); }
function isMirrorUrl(u){ return /raw\\.kkgithub\\.com|ghp\\.ci/.test(u || ''); }
var location = { protocol: 'https:' };
`;
eval(stubs + grab('siteReason') + '\n' + grab('reasonText') + '\n' + grab('buildSiteCard'));

const items = data.items || data;
let fail = 0, withOp = 0, originRendered = 0;
const errs = [];

for (const s of items) {
  try {
    const card = buildSiteCard(s);
    if (s.originProbe && s.originProbe.url) {
      withOp++;
      // 卡片里是否真的渲染出了 .origin 块
      const flat = JSON.stringify(card);
      if (flat.indexOf('"origin"') >= 0 || flat.indexOf('origin-head') >= 0) originRendered++;
    }
  } catch (e) {
    fail++;
    if (errs.length < 5) errs.push((s.name || s.id) + ' -> ' + e.message);
  }
}

console.log('站点总数          :', items.length);
console.log('带 originProbe 的 :', withOp);
console.log('卡片渲染出 origin :', originRendered);
console.log('渲染抛错          :', fail);
if (errs.length) { console.log('前几条错误:'); errs.forEach(e => console.log('   ', e)); }

// 断言：带 originProbe 的必须全部渲染出卡片，且全部渲染出 origin 块
const ok = fail === 0 && withOp === 11 && originRendered === 11;
console.log('\n结果：' + (ok ? '通过' : '失败'));
process.exit(ok ? 0 : 1);
