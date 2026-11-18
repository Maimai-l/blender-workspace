/* MCP 控制台前端：状态全部来自 GET /api/status 和事件流 /api/events，按钮只发请求，不自己改界面状态。 */
(function () {
  'use strict';
  var TOKEN = '';
  try {
    var u = new URL(location.href);
    TOKEN = u.searchParams.get('t') || sessionStorage.getItem('bmcp-token') || '';
    if (u.searchParams.get('t')) { sessionStorage.setItem('bmcp-token', TOKEN); history.replaceState(null, '', '/'); }
  } catch (e) {}

  var $ = function (id) { return document.getElementById(id); };
  var snap = null;

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  function api(method, path, body) {
    return fetch(path, {
      method: method, headers: { 'X-Panel-Token': TOKEN, 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) { j._status = r.status; return j; });
    });
  }

  function toast(type, msg, action, onAction) {
    if (!window.Endfield) return;
    var t = Endfield.toast(type, msg, action);
    if (t && action && onAction) { var b = t.querySelector('.act'); if (b) b.addEventListener('click', onAction); }
  }

  /* ---------------- 缩放：按 1280×720 绘制，整体缩放到窗口 ---------------- */
  function fit() {
    var k = Math.min(window.innerWidth / 1280, window.innerHeight / 720);
    $('screen').style.setProperty('--k', String(k));
  }
  window.addEventListener('resize', fit);
  fit();

  /* ---------------- 页面切换 ---------------- */
  var HANDLERS = {};
  function on(ev, fn) { (HANDLERS[ev] = HANDLERS[ev] || []).push(fn); }
  function emit(ev, d) { (HANDLERS[ev] || []).forEach(function (fn) { try { fn(d); } catch (e) { console.error(e); } }); }

  function go(page) {
    document.querySelectorAll('.mtab').forEach(function (t) {
      var on = t.dataset.page === page;
      t.setAttribute('aria-selected', String(on)); t.tabIndex = on ? 0 : -1;
    });
    $('page-status').hidden = page !== 'status';
    $('page-grants').hidden = page !== 'grants';
    emit('page', page);
  }
  document.querySelectorAll('.mtab').forEach(function (t) { t.addEventListener('click', function () { go(t.dataset.page); }); });
  document.querySelectorAll('[data-go]').forEach(function (b) { b.addEventListener('click', function () { go(b.dataset.go); }); });

  /* ---------------- 渲染 ---------------- */
  var SVC_WORD = { running: '运行中', stopped: '已停止', starting: '正在启动', stopping: '正在停止' };
  var APP_WORD = { connected: '已连接', open: '未连接', closed: '未连接', launching: '正在打开', reloading: '重载中' };
  var GATE_WORD = { on: '已开启', off: '已关闭', starting: '正在开启', stopping: '正在关闭' };

  function pill(label, attrs, muted) {
    return '<button class="pill pill--sm' + (muted ? ' pill--muted' : '') + '" type="button" ' + attrs + '><span class="lbl">' + label + '</span></button>';
  }

  function result(r) {
    if (r.live.break === 'undeployed') return '<b class="mc-dim">未部署</b>';
    var c = r.check && !r.check.stale ? r.check : null;
    var ok = c ? c.ok : r.live.ok;
    var where = c ? c.where : { tunnel: '外网访问', service: '服务', app: '应用', domain: '外网域名', exit: '出口' }[r.live.break];
    if (ok && c && c.slow) return '<b class="is-err">不稳</b><span title="' + esc((c.times || []).map(function (x) { return x === null ? '无响应' : x + 's'; }).join(' / ')) + '">' + esc(c.msg) + '</span>';
    var last = r.check;   // 状态变过以后结论按实时状态，响应时间仍显示最近一次检测的
    if (ok) return '<b>正常</b>' + (last && last.median !== null && last.median !== undefined ? '<i>' + last.median + 's</i>' : '');
    return '<b class="is-err">不通</b>断在' + esc(where || '');
  }

  function row(r, i, s) {
    var tunnelOn = s.tunnel.state === 'on';
    var row = i + 2, h = '';
    var svc = r.service, app = r.app, grant = r.id === 'grant';
    var deployed = !grant || s.grants.deployed;
    var svcUp = svc.state === 'running';
    var appUp = !app || app.state === 'connected';
    h += '<div class="mc-rail' + (tunnelOn ? '' : ' is-off') + '" style="grid-column:2;grid-row:' + row + '"></div>';
    // 外网域名
    h += '<div class="mc-st' + (tunnelOn ? '' : ' is-down') + '" data-next="' + (svcUp ? 'on' : 'off') + '" style="grid-row:' + row + '">' +
      '<p class="mc-name">' + esc(r.name) + '</p><p class="mc-m">' + esc(r.host) + '</p><p class="mc-res">' + result(r) + '</p></div>';
    // MCP 服务
    var word, cls = '', act = '';
    if (!deployed) { word = '未部署'; cls = ' is-off'; }
    else {
      word = SVC_WORD[svc.state] || svc.state;
      if (svc.state === 'stopped') { cls = ' is-err'; act = pill('启动', 'data-act="svc" data-id="' + r.id + '" data-on="1"'); }
      else if (svc.state === 'running') { act = pill('停止', 'data-act="svc" data-id="' + r.id + '" data-on="0"', true); }
      else { cls = ' is-busy'; }
    }
    h += '<div class="mc-st' + (svcUp ? '' : ' is-down') + '" data-next="' + (app ? (appUp ? 'on' : 'off') : 'none') + '" style="grid-row:' + row + '">' +
      '<p class="mc-m">:' + svc.port + '</p><div class="mc-line"><span class="mc-v' + cls + '">' + word + '</span>' + act + '</div></div>';
    // 下游应用
    if (!app) { h += '<div style="grid-row:' + row + '"></div>'; return h; }
    if (grant) {
      var gOk = app.state === 'connected';
      var gWord = !deployed ? '未部署' : gOk ? '授权管理' : !svcUp || !app.gateway ? '网关未运行' : '助手未运行';
      h += '<div class="mc-st' + (gOk ? '' : ' is-down') + '" data-next="none" style="grid-row:' + row + '"' +
        (app.helper && app.helper.msg ? ' title="' + esc(app.helper.msg) + '"' : '') + '>' +
        '<p class="mc-m">生效 ' + (app.active || 0) + '，待确认 ' + (app.pending || 0) + '</p>' +
        '<div class="mc-line"><span class="mc-v' + (gOk ? '' : deployed ? ' is-err' : ' is-off') + '">' + gWord + '</span>' +
        (deployed ? pill('进入', 'data-go-grants') : '') + '</div></div>';
      return h;
    }
    if (r.id === 'browser') {
      var ok = app.state === 'connected';
      var meta = '出口' + (app.port ? ' CLASH :' + app.port : '') + (ok && app.delay ? ' · ' + app.delay + 'MS' : '');
      var word = !app.installed ? '未部署' : !app.port ? '未经代理' : ok ? esc(app.node) : '直连，会被墙挡住';
      var wcls = !app.installed ? ' is-off' : ok ? ' is-node' : ' is-err';
      h += '<div class="mc-st' + (ok ? '' : ' is-down') + '" data-next="none" style="grid-row:' + row + '" title="' + esc((app.chain || []).join(' ← ')) + '">' +
        '<p class="mc-m">' + meta + '</p><div class="mc-line"><span class="mc-v' + wcls + '">' + word + '</span></div></div>';
      return h;
    }
    var aw = APP_WORD[app.state] || app.state, acls = '', aact = '';
    if (app.state === 'closed') { acls = ' is-off'; aact = pill('打开', 'data-act="app" data-id="' + r.id + '"'); }
    else if (app.state === 'open') { acls = ' is-off'; }
    else if (app.state === 'launching' || app.state === 'reloading') { acls = ' is-busy'; }
    h += '<div class="mc-st' + (appUp ? '' : ' is-down') + '" data-next="none" style="grid-row:' + row + '">' +
      '<p class="mc-m">' + esc(app.label) + (app.port ? ' :' + app.port : '') + '</p>' +
      '<div class="mc-line"><span class="mc-v' + acls + '">' + aw + '</span>' + aact + '</div></div>';
    return h;
  }

  function render(s) {
    snap = s;
    $('hero-n').textContent = s.online; $('hero-d').textContent = '/' + s.total;
    var btn = $('btn-check');
    btn.setAttribute('aria-busy', String(!!s.check.running));
    btn.querySelector('.lbl').textContent = s.check.running ? '检测中' : '检测';
    $('check-at').textContent = s.check.at || '还没检测';

    // 网络代理（Clash）
    var p = s.proxy, c = p.clash || {};
    var pw = { on: '已开启', off: '已关闭', starting: '正在开启', stopping: '正在关闭' }[p.state] || p.state;
    $('proxy-state').textContent = pw;
    $('proxy-state').className = 'mc-v' + (p.state === 'starting' || p.state === 'stopping' ? ' is-busy' : '');
    var pb = $('btn-proxy');
    pb.querySelector('.lbl').textContent = p.state === 'on' ? '关闭' : '开启';
    pb.className = 'pill pill--sm' + (p.state === 'on' ? ' pill--muted' : '');
    pb.setAttribute('aria-busy', String(p.state === 'starting' || p.state === 'stopping'));
    $('proxy-meta').textContent = c.running ? 'CLASH :' + p.port + (c.mode ? ' · ' + c.mode : '') : 'CLASH 未运行';
    $('proxy-node').textContent = !c.running ? '' : c.mode === 'direct' ? 'Clash 是直连模式，不经过节点' :
      c.node ? '节点 ' + c.node + (c.delay ? ' · ' + c.delay + 'MS' : '') : '';

    // 线路图
    var t = s.tunnel, on = t.state === 'on';
    var h = '<div style="grid-column:3" class="mc-colh"><span class="mc-en">Domain</span><span class="mc-k">外网域名</span></div>' +
      '<div class="mc-colh"><span class="mc-en">Service</span><span class="mc-k">MCP 服务</span></div>' +
      '<div class="mc-colh"><span class="mc-en">App</span><span class="mc-k">下游应用</span></div>';
    var gbtn = t.state === 'on' ? pill('关闭', 'data-act="tunnel" data-on="0"') :
      t.state === 'off' ? pill('开启', 'data-act="tunnel" data-on="1"') : '';
    h += '<div class="mc-gate" data-theme="dark"><p class="mc-en">Tunnel</p><p class="mc-k">外网访问</p>' +
      '<p class="mc-gate-state' + (t.state === 'off' ? ' is-err' : '') + '">' + (GATE_WORD[t.state] || t.state) + '</p>' +
      '<dl><div><dt class="mc-k">隧道连接</dt><dd>' + (on ? t.connections : 0) + '</dd></div></dl>' + gbtn + '</div>';
    s.routes.forEach(function (r, i) { h += row(r, i, s); });
    var board = $('board');
    board.innerHTML = h;

    // 顶栏
    $('hud-pending').textContent = s.grants.pending; $('hud-active').textContent = s.grants.active;
    $('grant-n').textContent = s.grants.active;
    $('tab-badge').hidden = !s.grants.pending;
    emit('status', s);
    var off = $('agent-offline');
    off.hidden = s.agent.online;
    off.textContent = s.agent.online ? '' : 'blender 账号的代理没在运行，服务和应用的状态读不到：' + (s.agent.msg || '') + '。登录一次 blender 账号即可。';
  }

  /* ---------------- 动作 ---------------- */
  function busy(el, on) { if (el) el.setAttribute('aria-busy', String(on)); }

  function after(res, el) {
    busy(el, false);
    if (res._status === 401) toast('error', '令牌失效：请从桌面的“Blender MCP 控制台”重新打开');
    else if (res.ok === false) toast('error', res.msg || '操作失败');
  }

  $('board').addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    if (b.hasAttribute('data-go-grants')) return go('grants');
    var act = b.dataset.act; busy(b, true);
    if (act === 'tunnel') api('POST', '/api/tunnel', { on: b.dataset.on === '1' }).then(function (r) { after(r, b); });
    else if (act === 'svc') api('POST', '/api/routes/' + b.dataset.id + '/service', { on: b.dataset.on === '1' }).then(function (r) { after(r, b); });
    else if (act === 'app') api('POST', '/api/routes/' + b.dataset.id + '/app/launch').then(function (r) { after(r, b); });
  });

  $('btn-check').addEventListener('click', function () {
    var b = this; busy(b, true); b.querySelector('.lbl').textContent = '检测中';
    api('POST', '/api/routes/check').then(function (r) {
      after(r, b);
      if (r.ok) refresh();
    });
  });

  $('btn-proxy').addEventListener('click', function () {
    var b = this, on = !(snap && snap.proxy.state === 'on'); busy(b, true);
    api('POST', '/api/proxy', { on: on }).then(function (r) {
      after(r, b);
      if (r.ok && r.msg) toast('info', r.msg);
      refresh();
    });
  });

  /* ---------------- 数据 ---------------- */
  function refresh() { return api('GET', '/api/status').then(function (s) { if (s.ok) render(s); else if (s._status === 401) after(s); }); }

  function connect() {
    var es = new EventSource('/api/events?t=' + encodeURIComponent(TOKEN));
    es.addEventListener('status.changed', function (e) { render(JSON.parse(e.data)); });
    es.addEventListener('action.done', function (e) {
      var d = JSON.parse(e.data);
      if (!d.ok) return toast('error', d.msg || '操作失败');
      if (d.undo) toast('info', d.msg, '撤销', function () { api('POST', d.undo.path, d.undo.body).then(function (r) { after(r); }); });
    });
    ['approval.created', 'approval.resolved', 'log.created', 'log.updated', 'grant.changed', 'counts'].forEach(function (ev) {
      es.addEventListener(ev, function (e) { emit(ev, JSON.parse(e.data)); });
    });
    es.addEventListener('open', function () { emit('reconnect'); });
  }

  window.MC = { api: api, toast: toast, esc: esc, go: go, on: on, after: after, snap: function () { return snap; } };
  if (window.Endfield) Endfield.init(document);
  refresh().then(connect, connect);
})();
