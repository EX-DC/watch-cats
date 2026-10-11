const test = require('node:test');
const assert = require('node:assert');
const WC = require('../../src/watchcats/web/lib.js');

const LIVE = {
  version: '0.4.0', ts: 1000, collector_errors: 0,
  system: { cpu: { pct: 12, cores: 2 }, ram: { total: 8e9, used: 4e9, pct: 50 },
    net: { iface: 'enp0s31f6', rx_mbps: 20, tx_mbps: 640, link_mbps: 1000 },
    disk: { pct: 8.5, used: 40e9, total: 500e9, free: 400e9, read_mb_s: 1, write_mb_s: 2, cache_bytes: null } },
  live: { serve_mbps: 640, fill_mbps: 20, serving_clients: 1,
    services: [{ key: 'epicgames', name: 'Epic Games', serve_mbps: 430, fill_mbps: 0, serve_clients: 1, fill_clients: 0 }],
    clients: [{ ip: '192.168.1.101', kind: 'windows', label: 'Windows', serve_mbps: 430, fill_mbps: 0, services: ['Epic Games'] }] }
};

test('esc neutralises html', () => {
  assert.strictEqual(WC.esc('<img src=x onerror="a()">&\''), '&lt;img src=x onerror=&quot;a()&quot;&gt;&amp;&#39;');
  assert.strictEqual(WC.esc(null), '');
});
const plain = (x) => x.replace(/[\u2066\u2069]/g, '');
test('fmtBytes', () => {
  assert.strictEqual(plain(WC.fmtBytes(999)), '999 B');
  assert.strictEqual(plain(WC.fmtBytes(15e6)), '15 MB');
  assert.strictEqual(plain(WC.fmtBytes(2.5e9)), '2.5 GB');
  assert.strictEqual(WC.fmtBytes(null), '—');
});
test('numbers with units are wrapped in LTR isolates (RTL pages show them in order)', () => {
  assert.strictEqual(WC.fmtMbps(134.4), '\u2066134 Mbps\u2069');
  assert.ok(WC.fmtBytes(5e9).startsWith('\u2066') && WC.fmtBytes(5e9).endsWith('\u2069'));
});
test('niceMax', () => {
  assert.strictEqual(WC.niceMax(0), 1);
  assert.strictEqual(WC.niceMax(3.2), 5);
  assert.strictEqual(WC.niceMax(7), 10);
  assert.strictEqual(WC.niceMax(120), 200);
  assert.strictEqual(WC.niceMax(0.8), 1);
});
test('avg uses only the last n samples', () => {
  const h = [{ s: 100 }, { s: 0 }, { s: 0 }];
  assert.strictEqual(WC.avg(h, 's', 2), 0);
  assert.strictEqual(WC.avg(h, 's', 3), 100 / 3);
  assert.strictEqual(WC.avg([], 's', 5), 0);
});
test('hourlyBars returns n slots ending at the current hour, gaps are zero', () => {
  const now = 10 * 3600 + 123;
  const b = WC.hourlyBars([{ hour: 10 * 3600, hit_bytes: 5, miss_bytes: 2 }, { hour: 8 * 3600, hit_bytes: 1, miss_bytes: 0 }], now, 24);
  assert.strictEqual(b.length, 24);
  assert.deepStrictEqual(b[23], { hour: 36000, hit: 5, miss: 2 });
  assert.deepStrictEqual(b[22], { hour: 32400, hit: 0, miss: 0 });
  assert.strictEqual(b[21].hit, 1);
});
test('serviceRows merges live and 24h data, active first', () => {
  const summary = { services: [{ key: 'steam', name: 'Steam', hit_bytes: 900, miss_bytes: 100 }, { key: 'epicgames', name: 'Epic Games', hit_bytes: 1, miss_bytes: 1 }] };
  const rows = WC.serviceRows(LIVE, summary);
  assert.deepStrictEqual(rows.map((r) => r.key), ['epicgames', 'steam']);
  assert.strictEqual(rows[0].serve, 430);
  assert.strictEqual(WC.serviceState(rows[0]), 'serving');
  assert.strictEqual(WC.serviceState(rows[1]), 'idle');
  assert.strictEqual(WC.serviceRows(null, null).length, 0);
});
test('errorGroups aggregates by kind', () => {
  const g = WC.errorGroups([
    { kind: 'upstream_timeout', host: 'a.com', count: 5, last: 10 },
    { kind: 'upstream_timeout', host: 'b.com', count: 7, last: 20 },
    { kind: 'upstream_403', host: 'c.com', count: 1, last: 5 }]);
  assert.strictEqual(g[0].kind, 'upstream_timeout');
  assert.strictEqual(g[0].count, 12);
  assert.strictEqual(g[0].last, 20);
  assert.deepStrictEqual(g[0].topHosts, ['b.com', 'a.com']);
});
test('relTime', () => {
  assert.strictEqual(WC.relTime(100, 150), 'اکنون');
  assert.strictEqual(WC.relTime(0, 600), '10 دقیقه پیش');
  assert.strictEqual(WC.relTime(0, 7200), '2 ساعت پیش');
  assert.strictEqual(WC.relTime(0, 3 * 86400), '3 روز پیش');
});
test('alertsFor: disk threshold is 90 percent', () => {
  const mk = (pct) => Object.assign({}, LIVE, { system: Object.assign({}, LIVE.system, { disk: Object.assign({}, LIVE.system.disk, { pct }) }) });
  assert.strictEqual(WC.alertsFor(mk(89.9), true).find((a) => a.n === 'فضای دیسک').c, 'ok');
  assert.strictEqual(WC.alertsFor(mk(90), true).find((a) => a.n === 'فضای دیسک').c, 'warn');
  assert.strictEqual(WC.alertsFor(null, false)[0].c, 'bad');
});
test('gaugeHtml needle angle and clamping', () => {
  const half = WC.gaugeHtml({ title: 't', value: 500, max: 1000, instant: 1, color: '#3ddc97', sub: 's' });
  assert.match(half, /rotate\(0deg\)/);
  assert.match(half, /conic-gradient/);
  const over = WC.gaugeHtml({ title: 't', value: 5000, max: 1000, instant: 1, color: '#3ddc97', sub: 's' });
  assert.match(over, /rotate\(90deg\)/);
  const zero = WC.gaugeHtml({ title: 't', value: 0, max: 1000, instant: 0, color: '#3ddc97', sub: 's' });
  assert.match(zero, /rotate\(-90deg\)/);
});
test('views escape hostile data', () => {
  const evil = '<script>alert(1)</script>';
  const svc = WC.serviceCardsHtml([{ key: 'x', name: evil, serve: 0, fill: 0, sc: 0, fc: 0, total: 0 }], 1000);
  assert.ok(!svc.includes('<script>'));
  const live = JSON.parse(JSON.stringify(LIVE)); live.live.clients[0].ip = evil; live.live.clients[0].services = [evil];
  assert.ok(!WC.clientsLiveHtml(live).includes('<script>'));
  const tbl = WC.tableHtml({ clients: [{ ip: evil, kind: 'ps5', hit_bytes: 1, miss_bytes: 1, last_seen: 0, top_service: evil }] }, 100);
  assert.ok(!tbl.includes('<script>'));
  const er = WC.errorsHtml([{ kind: evil, count: 1, last: 0, topHosts: [evil] }], evil, [{ ts: 0, ip: evil, host: evil, detail: evil }], 10);
  assert.ok(!er.includes('<script>'));
});
test('charts have the expected number of bars and labelled axes', () => {
  const c24 = WC.chart24Html({ hourly: [] }, 100000);
  assert.strictEqual((c24.match(/class="bar"/g) || []).length, 24);
  assert.match(c24, /محور عمودی/);
  const c60 = WC.chart60Html([{ serve: 1, fill: 1 }], 1000);
  assert.strictEqual((c60.match(/class="bar"/g) || []).length, 60);
  assert.match(c60, /اکنون/);
});
test('client count counts every active client, serving or filling', () => {
  const live = JSON.parse(JSON.stringify(LIVE));
  live.live.clients.push({ ip: '192.168.1.150', kind: 'pc', label: 'PC', serve_mbps: 0, fill_mbps: 10, services: ['Steam'] });
  live.live.clients.push({ ip: '192.168.1.99', kind: 'pc', label: 'PC', serve_mbps: 0, fill_mbps: 0, services: [] });
  assert.match(WC.clientsLiveHtml(live), /2 سیستم در حال دریافت از کش/);
});
test('clientsLiveHtml and kpis render real numbers', () => {
  const html = WC.clientsLiveHtml(LIVE);
  assert.match(html, /1 سیستم در حال دریافت از کش/);
  assert.match(html, /430 Mbps/);
  assert.match(WC.clientsLiveHtml(null), /هیچ سیستمی/);
  const k = WC.kpisHtml(LIVE, { hit_ratio: 0.62, miss_bytes: 3.1e9, clients: [1, 2, 3] });
  assert.match(k, /62٪/);
  assert.match(k, /3\.1 GB/);
});
test('errorsHtml: closed shows no log lines, open shows them', () => {
  const g = [{ kind: 'upstream_403', count: 3, last: 0, topHosts: ['gs2.example'] }];
  assert.ok(!WC.errorsHtml(g, null, [], 10).includes('logbox'));
  assert.match(WC.errorsHtml(g, 'upstream_403', [{ ts: 0, ip: '1.1.1.1', host: 'h', detail: 'd' }], 10), /logbox/);
  assert.match(WC.errorsHtml([], null, [], 10), /خطایی ثبت نشده/);
});
