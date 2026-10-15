/* Pure view/helper functions. Works in the browser (global WC) and in Node (tests). */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.WC = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  const BRAND = {
    steam: ['ST', '#2a475e', '#fff'], epicgames: ['EG', '#3a3a3a', '#fff'], sony: ['PS', '#0050c8', '#fff'],
    wsus: ['WU', '#0078d4', '#fff'], xbox_console: ['XB', '#107c10', '#fff'], xbox_windows: ['XW', '#0b5f0b', '#fff'],
    xboxlive: ['XB', '#107c10', '#fff'], riot: ['RG', '#d13639', '#fff'], uplay: ['UB', '#0070ff', '#fff'],
    origin: ['EA', '#e03a3a', '#fff'], blizzard: ['BZ', '#00aeff', '#0f1419'], rockstar: ['RS', '#fcaf17', '#0f1419'],
    cod: ['CD', '#4a4a4a', '#fff'], nintendo: ['NS', '#e60012', '#fff'], wargaming: ['WG', '#c8601a', '#fff'],
    warframe: ['WF', '#5b6b8c', '#fff']
  };
  const DEVICE = {
    windows: ['⊞', '#0078d4', 'ویندوز'], ps5: ['PS', '#0050c8', 'PS5'], ps4: ['PS', '#0050c8', 'PS4'],
    xbox_console: ['XB', '#107c10', 'Xbox'], pc: ['PC', '#4a5568', 'کامپیوتر'], tool: ['⚙', '#4a5568', 'ابزار'],
    unknown: ['؟', '#4a5568', 'ناشناس']
  };
  const KIND_FA = {
    upstream_timeout: 'تایم‌اوت اتصال به سرور مبدأ', upstream_403: 'خطای 403 از سمت CDN',
    dns_unresolved: 'خطای شناسایی دامنه در کش', dns_timed_out: 'تایم‌اوت DNS', other: 'سایر خطاها',
    upstream_unavailable: 'سرور مبدأ در دسترس نیست', upstream_connect_failed: 'اتصال به سرور مبدأ برقرار نشد',
    upstream_closed: 'سرور مبدأ اتصال را قطع کرد', upstream_reset: 'اتصال با سرور مبدأ ریست شد', upstream_ssl: 'خطای SSL با سرور مبدأ'
  };
  const STATE_FA = { serving: 'در حال سرو', filling: 'در حال ذخیره', idle: 'بی‌کار' };

  const ltr = (s) => '\u2066' + s + '\u2069'; // LTR isolate: keeps number and unit in order inside RTL text
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function fmtBytes(n) {
    if (n == null) return '—';
    const u = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0, v = n;
    while (v >= 1000 && i < 4) { v /= 1000; i++; }
    return ltr(((i < 2 || v >= 100) ? Math.round(v) : Math.round(v * 10) / 10) + ' ' + u[i]);
  }
  const fmtMbps = (n) => ltr(Math.round(n || 0) + ' Mbps');

  function avg(arr, key, n) {
    const s = arr.slice(-n);
    return s.length ? s.reduce((a, x) => a + x[key], 0) / s.length : 0;
  }
  function niceMax(v) {
    if (!(v > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const m of [1, 2, 5, 10]) if (v <= m * p) return m * p;
    return 10 * p;
  }
  function hourlyBars(hourly, nowSec, n) {
    n = n || 24;
    const map = {};
    (hourly || []).forEach((r) => { map[r.hour] = r; });
    const cur = Math.floor(nowSec / 3600) * 3600, out = [];
    for (let i = n - 1; i >= 0; i--) {
      const h = cur - i * 3600, r = map[h] || {};
      out.push({ hour: h, hit: r.hit_bytes || 0, miss: r.miss_bytes || 0 });
    }
    return out;
  }
  function serviceState(r) { return r.serve > 0 ? 'serving' : r.fill > 0 ? 'filling' : 'idle'; }
  function serviceRows(live, summary) {
    const map = {};
    const base = (s) => ({ key: s.key, name: s.name, total: 0, serve: 0, fill: 0, sc: 0, fc: 0 });
    ((summary && summary.services) || []).forEach((s) => {
      map[s.key] = Object.assign(base(s), { total: s.hit_bytes + s.miss_bytes });
    });
    ((live && live.live && live.live.services) || []).forEach((s) => {
      const r = map[s.key] || (map[s.key] = base(s));
      r.serve = s.serve_mbps; r.fill = s.fill_mbps; r.sc = s.serve_clients; r.fc = s.fill_clients;
    });
    return Object.values(map).sort((a, b) =>
      ((b.serve + b.fill > 0) - (a.serve + a.fill > 0)) || (b.total - a.total));
  }
  function errorGroups(errors) {
    const g = {};
    (errors || []).forEach((e) => {
      const x = g[e.kind] || (g[e.kind] = { kind: e.kind, count: 0, last: 0, hosts: {} });
      x.count += e.count; x.last = Math.max(x.last, e.last);
      x.hosts[e.host || '-'] = (x.hosts[e.host || '-'] || 0) + e.count;
    });
    return Object.values(g).sort((a, b) => b.count - a.count).map((x) => Object.assign(x, {
      topHosts: Object.entries(x.hosts).sort((a, b) => b[1] - a[1]).slice(0, 3).map((h) => h[0])
    }));
  }
  function relTime(ts, nowSec) {
    const d = nowSec - ts;
    if (d < 90) return 'اکنون';
    if (d < 3600) return Math.round(d / 60) + ' دقیقه پیش';
    if (d < 86400) return Math.round(d / 3600) + ' ساعت پیش';
    return Math.round(d / 86400) + ' روز پیش';
  }
  const pad2 = (n) => String(n).padStart(2, '0');
  function fmtDateTime(ts) {
    const d = new Date(ts * 1000);
    return ltr(d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) + ' ' + pad2(d.getHours()) + ':' + pad2(d.getMinutes()));
  }
  const fmtClock = (ts) => { const d = new Date(ts * 1000); return ltr(pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds())); };
  const LIVE_SECONDS = 120; // log times are per minute, so "live" means seen within the last ~2 minutes
  function lastSeenHtml(ts, nowSec) {
    if (nowSec - ts < LIVE_SECONDS) return '<span class="live"><i class="live-dot"></i>live</span>';
    return '<span class="stack"><span>' + esc(relTime(ts, nowSec)) + '</span><small class="muted">' + fmtDateTime(ts) + '</small></span>';
  }
  function kindName(kind) {
    if (KIND_FA[kind]) return KIND_FA[kind];
    const m = /^upstream_(\d{3})$/.exec(kind);
    return m ? 'خطای ' + m[1] + ' از سمت سرور مبدأ' : kind;
  }
  function alertsFor(live, connected) {
    const out = [];
    out.push(connected ? { s: 'سالم', c: 'ok', n: 'اتصال زنده', d: 'هر ۱ ثانیه' }
      : { s: 'قطع', c: 'bad', n: 'اتصال به سرور', d: 'تلاش مجدد خودکار' });
    if (live) {
      const d = live.system.disk;
      out.push(d.pct >= 90 ? { s: 'هشدار', c: 'warn', n: 'فضای دیسک', d: d.pct + '٪ · حد ۹۰٪' }
        : { s: 'سالم', c: 'ok', n: 'فضای دیسک', d: d.pct + '٪ · حد ۹۰٪' });
      out.push(live.collector_errors > 0 ? { s: 'هشدار', c: 'warn', n: 'خواندن لاگ', d: live.collector_errors + ' خطا' }
        : { s: 'سالم', c: 'ok', n: 'خواندن لاگ', d: 'بدون خطا' });
    }
    return out;
  }

  /* ---------- HTML views (every dynamic value goes through esc) ---------- */
  const badge = (ic, bg, fg, cls) =>
    '<span class="badge ' + (cls || '') + '" style="background:' + esc(bg) + ';color:' + esc(fg) + '">' + esc(ic) + '</span>';
  const svcBadge = (key, cls) => { const b = BRAND[key] || ['؟', '#4a5568', '#fff']; return badge(b[0], b[1], b[2], cls); };
  const devInfo = (kind) => DEVICE[kind] || DEVICE.unknown;
  const devBadge = (kind, cls) => { const d = devInfo(kind); return badge(d[0], d[1], '#fff', cls); };

  function alertsHtml(list) {
    return list.map((a) => '<div class="alert ' + a.c + '"><b>' + esc(a.s) + '</b><span>' + esc(a.n) +
      '</span><small>' + esc(a.d) + '</small></div>').join('') +
      '<div class="alert soon"><b>به‌زودی</b><span>هشدار DNS، کانتینرها، تلگرام</span><small>نسخهٔ ۰.۵.۰</small></div>';
  }
  function gaugeHtml(o) {
    const f = Math.max(0, Math.min(1, o.value / o.max)), deg = Math.round(f * 180);
    return '<div class="card gauge-card"><h3>' + esc(o.title) + '</h3><div class="gauge">' +
      '<div class="arc" style="background:conic-gradient(from -90deg,' + esc(o.color) + ' 0deg ' + deg + 'deg,#26303d ' + deg + 'deg 180deg,transparent 180deg)"></div>' +
      '<div class="hole"></div><div class="needle" style="transform:rotate(' + (deg - 90) + 'deg)"></div></div>' +
      '<div class="gval" style="color:' + esc(o.color) + '">' + esc(fmtMbps(o.value)) + '</div>' +
      '<div class="muted">لحظه‌ای: ' + esc(fmtMbps(o.instant)) + ' · سقف ' + esc(o.max) + '</div>' +
      '<div class="muted">' + esc(o.sub) + '</div></div>';
  }
  function clientsLiveHtml(live) {
    const act = ((live && live.live.clients) || []).filter((c) => c.serve_mbps > 0 || c.fill_mbps > 0);
    const nServe = act.filter((c) => c.serve_mbps > 0).length;
    const nFill = act.filter((c) => c.fill_mbps > 0 && !(c.serve_mbps > 0)).length;
    const head = '<h2>' + (act.length ? act.length + ' سیستم در حال دریافت' : 'هیچ سیستمی در حال دریافت نیست') + '</h2>' +
      (act.length ? '<p class="muted">' + nServe + ' سیستم از کش · ' + nFill + ' سیستم در حال دانلود از اینترنت (و ذخیره)</p>' : '');
    const cards = act.slice(0, 6).map((c) => {
      const svc = ((live.live && live.live.services) || []).find((s) => c.services.indexOf(s.name) >= 0);
      const d = devInfo(c.kind);
      const speeds = (c.serve_mbps > 0 ? '<strong class="speed green">' + esc(fmtMbps(c.serve_mbps)) + '</strong><small class="green">از کش</small>' : '') +
        (c.fill_mbps > 0 ? '<strong class="speed amber">' + esc(fmtMbps(c.fill_mbps)) + '</strong><small class="amber">از اینترنت</small>' : '');
      return '<div class="cl"><div class="cl-main"><div class="row">' + devBadge(c.kind) + '<b>' + esc(d[2]) + '</b></div>' +
        '<small class="muted"><bdi>' + esc(c.ip) + '</bdi></small></div><div class="cl-side">' +
        svcBadge(svc ? svc.key : null, 'big') + '<span>' + esc(c.services.join('، ')) + '</span>' + speeds + '</div></div>';
    }).join('');
    return head + '<div class="grid3">' + cards + '</div>';
  }
  function serviceCardsHtml(rows, max) {
    if (!rows.length) return '<p class="muted">هنوز ترافیکی ثبت نشده است.</p>';
    return '<div class="grid2">' + rows.map((r) => {
      const st = serviceState(r);
      const bar = (label, mbps, cls) => '<div class="bar-row"><div class="bar-head"><span class="' + cls + '">' + label +
        '</span><strong class="' + cls + '">' + esc(fmtMbps(mbps)) + '</strong></div><div class="track"><div class="fill ' + cls +
        '-bg" style="width:' + Math.min(100, mbps / max * 100) + '%"></div></div></div>';
      return '<div class="svc ' + st + '"><div class="svc-head"><span class="row">' + svcBadge(r.key, 'big') + '<b>' + esc(r.name) +
        '</b></span><span class="chip ' + st + '">' + STATE_FA[st] + '</span></div>' +
        bar('در حال دانلود و ذخیره', r.fill, 'amber') +
        bar('در حال سرو از کش · ' + esc(r.sc) + ' سیستم', r.serve, 'green') + '</div>';
    }).join('') + '</div>';
  }
  function kpisHtml(live, summary) {
    const d = live && live.system.disk;
    const k = [
      ['فضای دیسک', d ? d.pct + '٪' : '—', d ? fmtBytes(d.used) + ' از ' + fmtBytes(d.total) + (d.cache_bytes != null ? ' · کش ' + fmtBytes(d.cache_bytes) : '') : ''],
      ['نرخ HIT (۲۴ ساعت)', summary && summary.hit_ratio != null ? Math.round(summary.hit_ratio * 100) + '٪' : '—', 'درخواست از کش / کل'],
      ['گرفته‌شده از اینترنت (۲۴ ساعت)', summary ? fmtBytes(summary.miss_bytes) : '—', 'حجم MISS'],
      ['دستگاه‌های فعال (۲۴ ساعت)', summary ? String(summary.clients.length) : '—', 'دستگاه متمایز']
    ];
    return k.map((x) => '<div class="card kpi"><span class="muted">' + esc(x[0]) + '</span><strong>' + esc(x[1]) +
      '</strong><small class="muted">' + esc(x[2]) + '</small></div>').join('');
  }
  function hwHtml(live) {
    if (!live) return '';
    const s = live.system, n = s.net, d = s.disk;
    const t = (l, v, pct, c, sub) => '<div class="hw"><span class="muted">' + l + '</span><strong>' + esc(v) +
      '</strong><div class="track"><div class="fill" style="background:' + c + ';width:' + Math.min(100, pct) + '%"></div></div><small class="muted">' + esc(sub) + '</small></div>';
    return t('CPU', s.cpu.pct + '٪', s.cpu.pct, '#4da3ff', s.cpu.cores + ' هسته') +
      t('RAM', fmtBytes(s.ram.used) + ' / ' + fmtBytes(s.ram.total), s.ram.pct, '#4da3ff', s.ram.pct + '٪ مصرف') +
      t('کارت شبکه', '↑ ' + fmtMbps(n.tx_mbps) + ' · ↓ ' + fmtMbps(n.rx_mbps), Math.max(n.tx_mbps, n.rx_mbps) / (n.link_mbps || 1000) * 100, '#3ddc97', 'ارسال به کلاینت‌ها · دریافت از اینترنت · ' + (n.iface || '')) +
      t('دیسک', d.pct + '٪ پر', d.pct, '#f5a524', 'خواندن ' + ltr(d.read_mb_s + ' MB/s') + ' · نوشتن ' + ltr(d.write_mb_s + ' MB/s'));
  }
  const linScale = (yMax) => (v) => v / yMax;
  const logScale = (minV, yMax) => (v) => (v <= minV ? 0 : Math.log10(v / minV) / Math.log10(yMax / minV));
  /* bars = MISS (amber columns), line = HIT (green line); both on the same axis, never stacked */
  function comboChart(o) {
    const n = o.line.length, pct = (v) => (v == null ? 0 : Math.max(0, Math.min(1, o.scale(v))) * 100), x = (i) => (((i + 0.5) / n) * 100).toFixed(2);
    const grid = o.ticks.map((t) => '<div class="gl" style="bottom:' + (t.p * 100) + '%"></div>').join('');
    const yl = o.ticks.map((t) => '<span style="bottom:' + (t.p * 100) + '%">' + esc(t.l) + '</span>').join('');
    const bars = o.bars.map((v, i) => '<div class="slot" title="' + esc(o.titles[i] || '') + '"><i class="bar-m" style="height:' + pct(v) + '%"></i></div>').join('');
    const pts = o.line.map((v, i) => (v == null ? null : x(i) + ',' + (100 - pct(v)).toFixed(2))).filter(Boolean).join(' ');
    const dots = o.dots ? o.line.map((v, i) => (v > 0 ? '<b class="pt" style="left:' + x(i) + '%;bottom:' + pct(v) + '%"></b>' : '')).join('') : '';
    const xs = o.xLabels.map((t) => '<span>' + esc(t) + '</span>').join('');
    return '<div class="chart" dir="ltr"><div class="yaxis">' + yl + '</div><div class="plot-wrap"><div class="plot">' + grid +
      '<div class="slots">' + bars + '</div><svg class="overlay" viewBox="0 0 100 100" preserveAspectRatio="none"><polyline points="' + pts +
      '" fill="none" stroke="#3ddc97" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>' + dots +
      '</div><div class="xaxis">' + xs + '</div></div></div><p class="muted center">' + esc(o.caption) + '</p><div class="legend">' + o.legend + '</div>';
  }
  const LEG = '<span><b class="green">━ خط سبز · HIT</b> — از حافظهٔ کش سرو شد</span><span><b class="amber">▮ ستون نارنجی · MISS</b> — از اینترنت گرفته و ذخیره شد</span>';
  function chart24Html(summary, nowSec, mode) {
    const bars = hourlyBars(summary && summary.hourly, nowSec, 24);
    const maxV = Math.max.apply(null, bars.map((b) => Math.max(b.hit, b.miss)).concat([1]));
    const lab = (h) => { const d = new Date(h * 1000); return pad2(d.getHours()) + ':00'; };
    let scale, ticks;
    if (mode === 'log') {
      const minV = 1e6, K = Math.max(1, Math.ceil(Math.log10(Math.max(maxV, 2e6) / minV))), yMax = minV * Math.pow(10, K);
      scale = logScale(minV, yMax);
      ticks = Array.from({ length: K + 1 }, (_, k) => ({ p: k / K, l: fmtBytes(minV * Math.pow(10, k)) }));
    } else {
      const yMax = niceMax(maxV);
      scale = linScale(yMax);
      ticks = [0, 0.25, 0.5, 0.75, 1].map((p) => ({ p: p, l: p === 0 ? '0' : fmtBytes(yMax * p) }));
    }
    return comboChart({
      bars: bars.map((b) => b.miss), line: bars.map((b) => b.hit), scale: scale, ticks: ticks, dots: true,
      titles: bars.map((b) => lab(b.hour) + ' · HIT ' + fmtBytes(b.hit) + ' · MISS ' + fmtBytes(b.miss)),
      xLabels: [0, 6, 12, 18, 23].map((i) => lab(bars[i].hour)),
      caption: mode === 'log' ? 'مقیاس لگاریتمی: مقدارهای کوچک هم دیده می‌شوند · محور افقی: ساعت (ساعت محلی مرورگر)' : 'مقیاس خطی · محور عمودی: حجم ترافیک هر ساعت · محور افقی: ساعت (ساعت محلی مرورگر)',
      legend: LEG
    });
  }
  function chart60Html(hist) {
    const s = hist.slice(-60), pad = 60 - s.length;
    const zeros = Array.from({ length: pad }, () => 0), nulls = Array.from({ length: pad }, () => null);
    const maxV = Math.max.apply(null, s.map((x) => Math.max(x.serve, x.fill)).concat([100]));
    const yMax = niceMax(maxV);
    return comboChart({
      bars: zeros.concat(s.map((x) => x.fill)), line: nulls.concat(s.map((x) => x.serve)), scale: linScale(yMax), dots: false,
      ticks: [0, 0.25, 0.5, 0.75, 1].map((p) => ({ p: p, l: String(Math.round(yMax * p)) })),
      titles: zeros.map(() => '').concat(s.map((x) => Math.round(x.serve) + ' Mbps از کش · ' + Math.round(x.fill) + ' Mbps از اینترنت')),
      xLabels: ['۶۰ ثانیه پیش', '۴۰', '۲۰', 'اکنون'],
      caption: 'محور عمودی: سرعت (Mbps) · محور افقی: زمان از لحظهٔ باز شدن این صفحه · هر ستون یک ثانیه', legend: LEG
    });
  }
  function tableHtml(summary, nowSec) {
    const rows = (summary && summary.clients) || [];
    if (!rows.length) return '<p class="muted">در بازهٔ انتخاب‌شده کلاینتی ثبت نشده است.</p>';
    return '<div class="trow thead"><span>آی‌پی</span><span>دستگاه (خودکار)</span><span>سرویس اصلی</span><span>HIT</span><span>MISS</span><span>آخرین فعالیت</span></div>' +
      rows.slice(0, 15).map((r) => '<div class="trow"><span><bdi>' + esc(r.ip) + '</bdi></span><span class="row">' + devBadge(r.kind, 'sm') + esc(devInfo(r.kind)[2]) +
        '</span><span>' + esc(r.top_service || '—') + '</span><span class="green">' + esc(fmtBytes(r.hit_bytes)) + '</span><span class="amber">' + esc(fmtBytes(r.miss_bytes)) +
        '</span>' + lastSeenHtml(r.last_seen, nowSec).replace(/^<span class="live">/, '<span class="live">') + '</div>').join('');
  }
  function errorsHtml(groups, open, lines, nowSec) {
    if (!groups.length) return '<p class="muted">در ۲۴ ساعت اخیر خطایی ثبت نشده است. ✔</p>';
    return groups.map((g) => {
      const isOpen = open === g.kind;
      const body = isOpen ? '<div class="logbox" dir="ltr">' + ((lines && lines.length) ? lines.map((l) =>
        '<div>' + fmtDateTime(l.ts) + ' · ' + esc(l.ip || '-') + ' · ' + esc(l.host || '-') + ' · ' + esc(l.detail) + '</div>').join('') :
        '<div>در حال بارگذاری…</div>') + '</div>' : '';
      return '<div class="err"><button type="button" class="errbtn" data-kind="' + esc(g.kind) + '"><span><b>' + esc(kindName(g.kind)) +
        '</b> · <bdi>' + esc(g.topHosts.join('، ')) + '</bdi></span><span>' + esc(g.count) + ' مورد · آخرین: ' + esc(relTime(g.last, nowSec)) + ' · ' + fmtDateTime(g.last) + ' ' + (isOpen ? '▲' : '▼') + '</span></button>' + body + '</div>';
    }).join('');
  }
  return { ltr, esc, fmtBytes, fmtMbps, fmtDateTime, fmtClock, lastSeenHtml, kindName, linScale, logScale, avg, niceMax, hourlyBars, serviceRows, serviceState, errorGroups, relTime, alertsFor,
    alertsHtml, gaugeHtml, clientsLiveHtml, serviceCardsHtml, kpisHtml, hwHtml, chart24Html, chart60Html, tableHtml, errorsHtml, BRAND, DEVICE };
});
