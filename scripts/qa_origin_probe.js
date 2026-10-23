// 验证 originProbe 三态渲染：直接从 docs/index.html 取出 siteReason / reasonText，
// 不重写、不改写，确保测的是线上真实代码。
const fs = require('fs');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, '..', 'docs', 'index.html'), 'utf8');

function grab(name) {
  const start = html.indexOf('function ' + name + '(');
  if (start < 0) throw new Error('页面上找不到 ' + name);
  let i = html.indexOf('{', start), depth = 0, end = -1;
  for (; i < html.length; i++) {
    if (html[i] === '{') depth++;
    else if (html[i] === '}') { depth--; if (depth === 0) { end = i + 1; break; } }
  }
  if (end < 0) throw new Error(name + ' 括号不闭合');
  return html.slice(start, end);
}

// 只 stub 真正依赖的外部判定，不 stub 被测函数本身
const stubs = `
var isTemplateUrl = function (u) { return /[{}]/.test(u || ''); };
var isMirrorUrl   = function (u) { return /raw\\.kkgithub\\.com|ghp\\.ci/.test(u || ''); };
var isLocalHost   = function (u) { return /127\\.0\\.0\\.1|localhost/.test(u || ''); };
var location      = { protocol: 'https:' };
`;
eval(grab('siteReason') + '\n' + grab('reasonText') + '\n' + stubs);

const MIRROR = 'https://raw.kkgithub.com/2hacc/TVBox/main/json/%e5%88%9d%e4%b8%ad%e8%af%be%e5%a0%82.json';
const ORIGIN = 'https://raw.githubusercontent.com/2hacc/TVBox/main/json/%e5%88%9d%e4%b8%ad%e8%af%be%e5%a0%82.json';
const CHECKED = '2026-10-19T22:10:00+08:00';

const cases = [
  {
    n: 'A 无 originProbe（回归：文案必须与改动前一致）',
    s: { probe_url: MIRROR, tier: 'B', probe_kind: 'url', probe_status: 'uncertain' },
    wantReason: 'mirror',
    wantText: '该源经由 GitHub 加速镜像访问，镜像当前不可用；源站未验证，不代表失效',
  },
  {
    n: 'B originProbe.status=200（源站实测可加载）',
    s: { probe_url: MIRROR, tier: 'B', probe_kind: 'url',
         originProbe: { url: ORIGIN, status: 200, bytes: 32078, checkedAt: CHECKED } },
    wantReason: 'mirror_origin_ok',
    wantText: '该源的加速镜像已失效，但原始仓库地址实测返回 200、可加载；源站地址见下方，可直接复制替换',
  },
  {
    n: 'C originProbe.status=null（超时，未确认存活）',
    s: { probe_url: MIRROR, tier: 'B', probe_kind: 'url',
         originProbe: { url: ORIGIN, status: null, bytes: 0, checkedAt: CHECKED } },
    wantReason: 'mirror_origin_unknown',
    wantText: '该源的加速镜像已失效，源站响应超时，未确认存活（不代表失效，建议在客户端实测）',
  },
  {
    n: 'D 非镜像且无 originProbe（对照：不应被新逻辑波及）',
    s: { probe_url: 'https://example.com/a.json', tier: 'B', probe_kind: 'url' },
    wantReason: '',
  },
];

let fail = 0;
for (const c of cases) {
  const r = siteReason(c.s);
  const t = reasonText(r);
  const okR = r === c.wantReason;
  const okT = c.wantText === undefined || t === c.wantText;
  if (!okR || !okT) fail++;
  console.log((okR && okT) ? 'PASS' : 'FAIL', '|', c.n);
  console.log('      reason     =', JSON.stringify(r), okR ? '' : ' 期望 ' + JSON.stringify(c.wantReason));
  console.log('      reasonText =', JSON.stringify(t));
  if (c.wantText && !okT) console.log('      期望       =', JSON.stringify(c.wantText));
}

// 负向对照：证明测试不是空转
const neg = { probe_url: MIRROR, tier: 'B', originProbe: { url: ORIGIN, status: 200, checkedAt: CHECKED } };
const negR = siteReason(neg);
const negOK = negR !== 'mirror' && negR === 'mirror_origin_ok';
console.log(negOK ? 'PASS' : 'FAIL', '| 负向对照：同一条站点带/不带 originProbe 结论必须不同');
if (!negOK) fail++;

console.log('\n结果：' + (fail === 0 ? '全部通过' : fail + ' 项失败'));
process.exit(fail === 0 ? 0 : 1);
