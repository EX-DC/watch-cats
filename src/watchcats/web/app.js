(function () {
  'use strict';
  const S = { live: null, summary: null, hist: [], connected: false, open: null, lines: [] };
  const $ = (id) => document.getElementById(id);
  const now = () => Math.floor(Date.now() / 1000);

  function renderLive() {
    const l = S.live;
    $('alerts').innerHTML = WC.alertsHtml(WC.alertsFor(l, S.connected));
    if (!l) return;
    const max = l.system.net.link_mbps || 1000;
    $('gauges').innerHTML =
      WC.gaugeHtml({ title: 'سرعت سرو از کش (HIT)', value: WC.avg(S.hist, 'serve', 5), instant: l.live.serve_mbps, max: max, color: '#3ddc97', sub: 'ارسال کارت شبکه به کلاینت‌ها · میانگین ۵ ثانیه' }) +
      WC.gaugeHtml({ title: 'سرعت دانلود از اینترنت و ذخیره (MISS)', value: WC.avg(S.hist, 'fill', 5), instant: l.live.fill_mbps, max: max, color: '#f5a524', sub: 'دریافت کارت شبکه از اینترنت · میانگین ۵ ثانیه' });
    $('clients-live').innerHTML = WC.clientsLiveHtml(l);
    $('hw').innerHTML = WC.hwHtml(l);
    $('services').innerHTML = WC.serviceCardsHtml(WC.serviceRows(l, S.summary), max);
    $('kpis').innerHTML = WC.kpisHtml(l, S.summary);
    $('chart60').innerHTML = WC.chart60Html(S.hist, max);
    $('ver').textContent = 'v' + l.version;
    $('sub').textContent = 'سرور ' + location.hostname + ' · بروزرسانی ' + new Date(l.ts * 1000).toLocaleTimeString();
  }
  function renderSummary() {
    $('chart24').innerHTML = WC.chart24Html(S.summary, now());
    $('table').innerHTML = WC.tableHtml(S.summary, now());
    renderErrors();
    renderLive();
  }
  function renderErrors() {
    $('errors').innerHTML = WC.errorsHtml(WC.errorGroups(S.summary && S.summary.errors), S.open, S.lines, now());
  }
  function loadSummary() {
    fetch('/api/summary?hours=24').then((r) => r.json()).then((s) => { S.summary = s; renderSummary(); }).catch(() => {});
  }
  function connect() {
    const es = new EventSource('/api/stream');
    es.onopen = () => { S.connected = true; renderLive(); };
    es.onmessage = (e) => {
      S.connected = true;
      S.live = JSON.parse(e.data);
      S.hist.push({ serve: S.live.live.serve_mbps, fill: S.live.live.fill_mbps });
      if (S.hist.length > 60) S.hist.shift();
      renderLive();
    };
    es.onerror = () => { S.connected = false; renderLive(); };
  }
  $('errors').addEventListener('click', (ev) => {
    const b = ev.target.closest('.errbtn');
    if (!b) return;
    const kind = b.getAttribute('data-kind');
    S.open = S.open === kind ? null : kind;
    S.lines = [];
    renderErrors();
    if (S.open) {
      fetch('/api/errors?kind=' + encodeURIComponent(kind) + '&limit=20').then((r) => r.json()).then((d) => {
        if (S.open === kind) { S.lines = d.items; renderErrors(); }
      }).catch(() => {});
    }
  });
  renderLive();
  loadSummary();
  setInterval(loadSummary, 30000);
  connect();
})();
