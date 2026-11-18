/* 临时授权页（P2）、签发（P3/P4）、待确认浮层（P5：命令确认和登录请求）、规则（P6）、执行记录详情、浏览器登录。
   数据来自 /api/grants、/api/approvals、/api/logs、/api/logins，之后靠事件流更新；按钮只发请求。 */
(function () {
  'use strict';
  var MC = window.MC;
  if (!MC) return;
  var $ = function (id) { return document.getElementById(id); };
  var esc = MC.esc, api = MC.api, toast = MC.toast;

  var state = {
    grants: [], filter: 'active', logs: [], logGrant: '', open: {}, approvals: [], loginReqs: [], pendAll: false, pendMin: false,
    status: null, last: null, issued: null, folders: [], loaded: false, skew: 0, logins: [], pickLogins: [], win: null,
    keepLogin: true, winSites: {}
  };

  function nowS() { return Date.now() / 1000 + state.skew; }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function left(sec) {
    if (sec <= 0) return '0:00';
    var h = Math.floor(sec / 3600), m = Math.floor(sec / 60) % 60, s = Math.floor(sec) % 60;
    return h ? h + ':' + pad(m) + ':' + pad(s) : m + ':' + pad(s);
  }
  function segSet(el, v) { el.querySelectorAll('button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.v === String(v))); }); }
  function segGet(el) { var b = el.querySelector('button[aria-pressed="true"]'); return b ? b.dataset.v : null; }
  function segBind(el, fn) {
    el.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      segSet(el, b.dataset.v); if (fn) fn(b.dataset.v);
    });
  }
  function fav(domain) { return '<span class="mc-fav" aria-hidden="true">' + esc((domain || '?').replace(/^www\./, '').slice(0, 2)) + '</span>'; }

  /* ---------------- 授权列表 ---------------- */
  var STATE_WORD = { active: '生效中', expired: '已到期', used: '已用完', revoked: '已吊销' };

  function grantCard(g) {
    var total = (g.minutes || 60) * 60, rem = Math.max(0, g.expires - nowS());
    var active = g.state === 'active', hasF = g.folders.length > 0;
    var tPct = active ? Math.max(0, Math.min(100, 100 * rem / total)) : 0;
    var lim = g.limit < 0 ? '不限' : g.used + '/' + g.limit;
    var uPct = g.limit < 0 ? 0 : Math.min(100, 100 * g.used / Math.max(1, g.limit));
    var logins = g.logins && g.logins.length ? g.logins.join('、') : '无登录';
    var tags = [];
    if (hasF && g.browser) tags = [['浏览器', logins], ['确认', g.confirm ? '需要' : '不需要']];
    else if (hasF) tags = [['联网', g.net ? '允许' : '不允许'], ['确认', g.confirm ? '需要' : '不需要'], ['到期', g.expires_at]];
    else tags = [['登录', logins], ['到期', g.expires_at]];
    var act;
    if (active) act = '<button class="pill pill--sm" type="button" data-log="' + g.id + '"><span class="lbl">查看记录</span></button>' +
      '<button class="btn btn--ghost ibtn btn--sm" type="button" aria-label="吊销" title="吊销" data-revoke="' + g.id + '"><svg class="ic"><use href="#i-trash"></use></svg></button>';
    else if (g.restorable) act = '<span class="mc-gstate">已吊销</span><button class="pill pill--sm" type="button" data-restore="' + g.id + '"><span class="lbl">恢复</span></button>';
    else act = '<span class="mc-gstate">' + (STATE_WORD[g.state] || g.state) + '</span><button class="pill pill--sm pill--muted" type="button" data-log="' + g.id + '"><span class="lbl">查看记录</span></button>';
    var second = hasF ?
      '<div class="prog" role="progressbar" aria-valuenow="' + Math.round(uPct) + '" aria-valuemin="0" aria-valuemax="100" aria-label="已用次数"><span class="prog-label">已用次数</span>' +
      '<div class="prog-line"><div class="prog-track"><div class="prog-fill" style="--v:' + uPct + '%"></div></div><span class="v">' + lim + '</span></div></div>' :
      '<div class="prog" aria-label="浏览器操作"><span class="prog-label">浏览器操作</span><div class="prog-line"><span class="v" style="text-align:left">' + (g.browser_ops || 0) + ' 次</span></div></div>';
    return '<div class="mc-grant' + (active ? '' : ' is-off') + '" data-theme="dark" data-id="' + g.id + '">' +
      '<div class="mc-gmain"><p class="mc-grant-name" title="' + esc(g.name) + '">' + esc(g.name) + '</p>' +
      '<p class="mc-m" style="text-transform:none" title="' + esc(g.folders.join('\n')) + '">' + (hasF ? esc(g.folders.join('、')) : '仅浏览器') + '</p>' +
      '<p class="mc-tags">' + tags.map(function (t) { return '<span>' + t[0] + '<b>' + esc(t[1]) + '</b></span>'; }).join('') + '</p></div>' +
      '<div class="prog" role="progressbar" aria-valuenow="' + Math.round(tPct) + '" aria-valuemin="0" aria-valuemax="100" aria-label="剩余时间"><span class="prog-label">剩余时间</span>' +
      '<div class="prog-line"><div class="prog-track"><div class="prog-fill" style="--v:' + tPct + '%"></div></div><span class="v" data-left="' + g.id + '">' + (active ? left(rem) : '—') + '</span></div></div>' +
      second + '<div class="mc-grant-act">' + act + '</div></div>';
  }

  function renderGrants() {
    var list = state.grants.filter(function (g) { return state.filter === 'all' || g.state === 'active' || g.restorable; });
    var box = $('grant-list');
    box.innerHTML = list.length ? list.map(grantCard).join('') :
      '<div class="mc-empty">' + (state.filter === 'active' ? '没有生效中的授权。' : '暂无授权记录。') + '</div>';
    $('grant-n').textContent = state.grants.filter(function (g) { return g.state === 'active'; }).length;
    renderLogFilter();
  }

  function upsertGrant(g) {
    var i = state.grants.findIndex(function (x) { return x.id === g.id; });
    if (i >= 0) state.grants[i] = g; else state.grants.unshift(g);
    renderGrants();
  }

  function loadGrants() {
    return api('GET', '/api/grants?status=all').then(function (r) {
      if (!r.ok) return;
      state.grants = r.grants;
      if (!state.last && r.last_issue) state.last = r.last_issue;
      renderGrants();
    });
  }

  segBind($('grant-filter'), function (v) { state.filter = v; renderGrants(); });

  $('grant-list').addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    if (b.dataset.log) { setLogGrant(b.dataset.log); return; }
    if (b.dataset.revoke) {
      b.setAttribute('aria-busy', 'true');
      api('POST', '/api/grants/' + b.dataset.revoke + '/revoke').then(function (r) {
        b.removeAttribute('aria-busy');
        if (!r.ok) return MC.after(r);
        upsertGrant(r.grant);
        toast('info', '已吊销“' + r.grant.name + '”，地址已失效', '恢复', function () { restore(r.grant.id); });
      });
    }
    if (b.dataset.restore) restore(b.dataset.restore);
  });

  function restore(id) {
    api('POST', '/api/grants/' + id + '/restore').then(function (r) {
      if (!r.ok) return MC.after(r);
      upsertGrant(r.grant);
      toast('success', '已恢复“' + r.grant.name + '”');
    });
  }

  setInterval(function () {
    var expired = false;
    state.grants.forEach(function (g) {
      if (g.state !== 'active') return;
      var rem = g.expires - nowS();
      var el = document.querySelector('[data-left="' + g.id + '"]');
      if (el) {
        el.textContent = left(rem);
        var fill = el.parentNode.querySelector('.prog-fill');
        if (fill) fill.style.setProperty('--v', Math.max(0, 100 * rem / ((g.minutes || 60) * 60)) + '%');
      }
      if (rem <= 0) expired = true;
    });
    if (expired) setTimeout(loadGrants, 3500);
  }, 1000);

  /* ---------------- 执行记录 ---------------- */
  var OP = { run: '执行', read: '读取', write: '写入', list: '列目录' };
  var RES = { ok: ['已执行', ''], done: ['已完成', ''], running: ['执行中', ' is-busy'], pending: ['待确认', ' is-busy'],
    blocked: ['已拦截', ' is-err'], denied: ['已拒绝', ' is-off'], error: ['出错', ' is-err'], timeout: ['超时', ' is-err'],
    cancelled: ['已取消', ' is-off'] };

  function logRow(l) {
    var r = RES[l.result] || [l.result, ''];
    var open = !!state.open[l.id];
    return '<div class="mc-lrow' + (open ? ' is-open' : '') + '" data-log-id="' + l.id + '" role="button" tabindex="0" aria-expanded="' + open + '">' +
      '<span class="t">' + esc(l.time) + '</span><span class="o">' + (OP[l.op] || esc(l.op)) + '</span>' +
      '<span class="c" title="' + esc(l.target) + '">' + esc(l.target) + '</span><span class="s' + r[1] + '">' + r[0] + '</span>' +
      '<span class="x" title="' + esc(l.note) + '">' + esc(l.note || '') + '</span><span class="d">' + (l.seconds ? Number(l.seconds).toFixed(1) + 's' : '0.0s') + '</span></div>' +
      (open ? '<div class="mc-ldetail" data-detail="' + l.id + '">' + detailHtml(state.open[l.id], l) + '</div>' : '');
  }

  function detailHtml(d, l) {
    if (d === true) return '<p class="mc-k">读取中</p>';
    var g = state.grants.find(function (x) { return x.id === l.grant_id; });
    return '<dl><dt>授权</dt><dd>' + esc(g ? g.name : l.grant || l.grant_id) + '</dd><dt>时间</dt><dd>' + esc(d.full_time) + '</dd>' +
      (d.cwd ? '<dt>工作目录</dt><dd>' + esc(d.cwd) + '</dd>' : '') + (d.shell ? '<dt>shell</dt><dd>' + esc(d.shell) + '</dd>' : '') +
      (d.exit !== null && d.exit !== undefined ? '<dt>退出码</dt><dd>' + d.exit + '</dd>' : '') + '</dl>' +
      '<div class="mc-lcmd"><code>' + esc(d.target) + '</code><button class="btn btn--ghost btn--sm" type="button" data-copy="' + d.id + '"><span class="lbl">复制</span></button></div>' +
      (d.output ? '<pre class="mc-out">' + esc(d.output) + '</pre>' : '');
  }

  function renderLogs() {
    var rows = state.logs.filter(function (l) { return !state.logGrant || l.grant_id === state.logGrant; });
    $('log-body').innerHTML = rows.length ? rows.map(logRow).join('') :
      '<div class="mc-empty">' + (state.logGrant ? '该授权暂无调用记录。' : '暂无调用记录。') + '</div>';
  }

  function renderLogFilter() {
    var el = $('log-filter');
    if (!state.logGrant) { el.hidden = true; return; }
    var g = state.grants.find(function (x) { return x.id === state.logGrant; });
    el.hidden = false;
    el.innerHTML = '<span class="tag tag--sm">' + esc(g ? g.name : state.logGrant) +
      '<button class="rm" type="button" aria-label="显示全部记录"><svg class="ic"><use href="#i-close"></use></svg></button></span>';
  }

  function setLogGrant(id) { state.logGrant = id || ''; renderLogFilter(); loadLogs(); }
  $('log-filter').addEventListener('click', function (e) { if (e.target.closest('.rm')) setLogGrant(''); });

  function loadLogs() {
    return api('GET', '/api/logs?limit=200' + (state.logGrant ? '&grant=' + encodeURIComponent(state.logGrant) : '')).then(function (r) {
      if (!r.ok) return;
      if (state.logGrant) {
        var others = state.logs.filter(function (l) { return l.grant_id !== state.logGrant; });
        state.logs = r.logs.concat(others).sort(function (a, b) { return b.id - a.id; });
      } else state.logs = r.logs;
      renderLogs();
    });
  }

  function toggleLog(id) {
    if (state.open[id]) { delete state.open[id]; renderLogs(); return; }
    state.open[id] = true; renderLogs();
    api('GET', '/api/logs/' + id).then(function (r) {
      if (!state.open[id]) return;
      state.open[id] = r.ok ? r.log : { full_time: '', target: '', output: r.msg || '读取失败' };
      renderLogs();
    });
  }

  $('log-body').addEventListener('click', function (e) {
    var c = e.target.closest('[data-copy]');
    if (c) {
      var d = state.open[c.dataset.copy];
      copy(d && d.target).then(function (ok) { toast(ok ? 'success' : 'error', ok ? '已复制' : '复制失败'); });
      return;
    }
    if (e.target.closest('.mc-ldetail')) return;
    var row = e.target.closest('[data-log-id]');
    if (row) toggleLog(+row.dataset.logId);
  });
  $('log-body').addEventListener('keydown', function (e) {
    var row = e.target.closest('[data-log-id]');
    if (row && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); toggleLog(+row.dataset.logId); }
  });

  /* ---------------- 待确认浮层：命令确认和登录请求 ---------------- */
  function pendItems() {
    var a = state.approvals.map(function (x) { return { kind: 'cmd', at: x.at, d: x }; })
      .concat(state.loginReqs.map(function (x) { return { kind: 'login', at: x.at, d: x }; }));
    a.sort(function (x, y) { return x.at - y.at; });
    // 正在登录的那一条排在最前
    var w = state.win && state.win.request;
    if (w) a.sort(function (x, y) { return (y.kind === 'login' && y.d.id === w) - (x.kind === 'login' && x.d.id === w); });
    return a;
  }

  function cmdBody(p) {
    return '<div class="mc-pend-body"><p class="mc-cmd">' + esc(p.command) + '</p>' +
      '<dl><dt>授权</dt><dd>' + esc(p.grant) + '</dd><dt>工作目录</dt><dd title="' + esc(p.cwd) + '">' + esc(p.cwd) + '</dd>' +
      '<dt>shell</dt><dd>' + esc(p.shell) + '</dd><dt>请求时间</dt><dd>' + esc(p.time) + '</dd></dl>' +
      '<div class="mc-pend-act"><button class="pill" type="button" data-deny="' + p.id + '"><span class="lbl">拒绝</span></button>' +
      '<button class="pill" type="button" data-allow="' + p.id + '"><span class="lbl">允许</span></button></div></div>';
  }

  function loginBody(r) {
    var w = state.win, mine = w && w.request === r.id && w.state === 'open';
    var head = '<div class="mc-site">' + fav(r.domain) + '<p class="mc-cmd">' + esc(r.domain) + '</p></div>';
    if (!mine) {
      return '<div class="mc-pend-body">' + head +
        '<dl><dt>授权</dt><dd>' + esc(r.grant) + '</dd><dt>页面</dt><dd title="' + esc(r.url) + '">' + esc(r.url) + '</dd>' +
        (r.reason ? '<dt>原因</dt><dd title="' + esc(r.reason) + '">' + esc(r.reason) + '</dd>' : '') +
        '<dt>请求时间</dt><dd>' + esc(r.time) + '</dd></dl>' +
        '<div class="mc-pend-act">' + (r.state === 'active' ?
          '<button class="pill" type="button" data-lcancel="' + r.id + '"><span class="lbl">取消</span></button>' :
          '<button class="pill" type="button" data-ldecline="' + r.id + '"><span class="lbl">拒绝</span></button>') +
        '<button class="pill" type="button" data-lstart="' + r.id + '"><span class="lbl">去登录</span></button></div></div>';
    }
    var sites = (w.sites || []);
    return '<div class="mc-pend-body">' + head +
      '<p class="mc-live"><i></i><span>登录窗口已打开</span></p>' +
      '<dl><dt>授权</dt><dd>' + esc(r.grant) + '</dd></dl>' +
      (sites.length ? '<ul class="mc-rec">' + sites.map(function (s) {
        var on = state.winSites[s.domain] !== undefined ? state.winSites[s.domain] : s.default;
        return '<li><input type="checkbox" data-site="' + esc(s.domain) + '"' + (on ? ' checked' : '') + ' aria-label="' + esc(s.domain) + '">' +
          '<span><b>' + esc(s.domain) + '</b>' + (s.title ? '<span class="t">' + esc(s.title) + '</span>' : '') + '</span></li>';
      }).join('') + '</ul>' : '') +
      '<label class="mc-keep"><input type="checkbox" id="keep-login"' + (state.keepLogin ? ' checked' : '') + '>保存到浏览器登录</label>' +
      '<div class="mc-pend-act"><button class="pill" type="button" data-wcancel="1"><span class="lbl">取消</span></button>' +
      '<button class="pill" type="button" data-wfinish="1"><span class="lbl">完成</span></button></div></div>';
  }

  function renderPend() {
    var box = $('pend'), a = pendItems();
    if (!a.length) { box.hidden = true; box.innerHTML = ''; return; }
    box.hidden = false;
    var items = state.pendAll ? a : [a[0]];
    var first = a[0], w = state.win;
    var title = state.pendAll ? '待确认' : first.kind === 'cmd' ? '待确认' :
      (w && w.request === first.d.id && w.state === 'open' ? '登录中' : '登录请求');
    box.innerHTML = '<div class="mc-pend-card">' +
      '<div class="alert-strip"><span class="alert-title">' + title + '</span><button class="meta mc-pend-more" type="button" aria-expanded="' + state.pendAll + '" title="' +
      (a.length > 1 ? (state.pendAll ? '仅显示第一条' : '展开全部') : '') + '">' + (state.pendAll ? a.length + ' 条' : '1/' + a.length) + '</button>' +
      '<button class="cbtn mc-pend-min" type="button" aria-label="' + (state.pendMin ? '展开' : '收起') + '" title="' + (state.pendMin ? '展开' : '收起') + '">' +
      '<svg class="ic"><use href="#' + (state.pendMin ? 'i-plus' : 'i-minus') + '"></use></svg></button></div>' +
      '<div class="mc-pend-list"' + (state.pendMin ? ' hidden' : '') + '>' + items.map(function (it) {
        return it.kind === 'cmd' ? cmdBody(it.d) : loginBody(it.d);
      }).join('') + '</div></div>';
  }

  $('pend').addEventListener('change', function (e) {
    if (e.target.id === 'keep-login') state.keepLogin = e.target.checked;
    if (e.target.dataset.site) state.winSites[e.target.dataset.site] = e.target.checked;
  });

  $('pend').addEventListener('click', function (e) {
    if (e.target.closest('.mc-pend-min')) { state.pendMin = !state.pendMin; renderPend(); return; }
    if (e.target.closest('.mc-pend-more')) { state.pendMin = false; if (pendItems().length > 1) { state.pendAll = !state.pendAll; renderPend(); } return; }
    var b = e.target.closest('button'); if (!b) return;
    if (b.dataset.allow || b.dataset.deny) {
      var id = b.dataset.allow || b.dataset.deny, allow = !!b.dataset.allow;
      b.setAttribute('aria-busy', 'true');
      api('POST', '/api/approvals/' + id, { allow: allow }).then(function (r) {
        if (!r.ok && r._status !== 409) { b.removeAttribute('aria-busy'); return MC.after(r); }
        removeApproval(id);
        toast(allow ? 'success' : 'info', allow ? '已允许，命令开始执行' : '已拒绝，不计次数');
      });
    } else if (b.dataset.ldecline || b.dataset.lcancel) {
      var rid = b.dataset.ldecline || b.dataset.lcancel;
      api('POST', '/api/logins/requests/' + rid, { action: b.dataset.ldecline ? 'decline' : 'cancel' }).then(function (r) {
        if (!r.ok && r._status !== 409) return MC.after(r);
        removeLoginReq(rid);
      });
    } else if (b.dataset.lstart) {
      var req = state.loginReqs.find(function (x) { return x.id === b.dataset.lstart; });
      if (!req) return;
      b.setAttribute('aria-busy', 'true');
      state.winSites = {}; state.keepLogin = true;
      api('POST', '/api/logins/window', { url: req.url, request: req.id }).then(function (r) {
        b.removeAttribute('aria-busy');
        if (!r.ok) return MC.after(r);
        state.win = r.window; renderPend();
      });
    } else if (b.dataset.wcancel) {
      api('POST', '/api/logins/window/cancel').then(function () {});
    } else if (b.dataset.wfinish) {
      finishWindow(b, state.keepLogin);
    }
  });

  function chosenSites() {
    return ((state.win && state.win.sites) || []).filter(function (s) {
      return state.winSites[s.domain] !== undefined ? state.winSites[s.domain] : s.default;
    }).map(function (s) { return s.domain; });
  }

  function finishWindow(b, save) {
    var domains = chosenSites();
    if (!domains.length) return toast('error', '请选择要使用的网站');
    var isReq = !!(state.win && state.win.request);
    b.setAttribute('aria-busy', 'true');
    api('POST', '/api/logins/window/finish', { domains: domains, save: save }).then(function (r) {
      b.removeAttribute('aria-busy');
      if (!r.ok) return MC.after(r);
      toast('success', isReq ? '已登录 ' + domains.join('、') + (save ? '，并已保存' : '') : '已保存 ' + domains.join('、') + ' 的登录');
      loadLogins();
    });
  }

  function removeApproval(id) {
    state.approvals = state.approvals.filter(function (x) { return x.id !== id; });
    if (pendItems().length < 2) state.pendAll = false;
    renderPend();
  }
  function removeLoginReq(id) {
    state.loginReqs = state.loginReqs.filter(function (x) { return x.id !== id; });
    if (pendItems().length < 2) state.pendAll = false;
    renderPend();
  }

  function loadApprovals() {
    return Promise.all([api('GET', '/api/approvals'), api('GET', '/api/logins/requests'), api('GET', '/api/logins/window')]).then(function (rs) {
      if (rs[0].ok) state.approvals = rs[0].approvals;
      if (rs[1].ok) state.loginReqs = rs[1].requests;
      if (rs[2].ok) state.win = rs[2].window;
      renderPend();
    });
  }

  /* ---------------- 浏览器登录 ---------------- */
  function loadLogins() {
    return api('GET', '/api/logins').then(function (r) {
      if (!r.ok) return;
      state.logins = r.logins;
      $('logins-n').textContent = r.logins.length;
      $('logins-meta').textContent = r.logins.map(function (x) { return x.domain; }).join('、');
      renderLoginList();
      renderLoginChips();
    });
  }

  var ldlg = $('dlg-logins'), ndlg = $('dlg-loginnew');
  function renderLoginList() {
    $('logins-list').innerHTML = state.logins.length ? state.logins.map(function (x) {
      return '<li>' + fav(x.domain) + '<div><b>' + esc(x.domain) + '</b><span class="t' + (x.stale ? ' is-stale' : '') + '">' +
        esc(x.stale ? '登录可能已失效' : (x.title || '')) + '</span></div><span class="when">' + esc(x.saved_at) + '</span>' +
        '<button class="btn btn--secondary btn--sm" type="button" data-relogin="' + esc(x.domain) + '"><span class="lbl">重新登录</span></button>' +
        '<button class="btn btn--ghost ibtn btn--sm" type="button" aria-label="删除 ' + esc(x.domain) + '" data-ldel="' + esc(x.domain) + '"><svg class="ic"><use href="#i-trash"></use></svg></button></li>';
    }).join('') : '<li><span></span><span class="t">暂无保存的登录。</span></li>';
  }
  $('btn-logins').addEventListener('click', function () { loadLogins(); ldlg.showModal(); });
  $('logins-list').addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    if (b.dataset.ldel) {
      api('POST', '/api/logins/' + encodeURIComponent(b.dataset.ldel) + '/delete').then(function (r) {
        if (!r.ok) return MC.after(r);
        toast('info', '已删除 ' + b.dataset.ldel); loadLogins();
      });
    }
    if (b.dataset.relogin) openNewLogin('https://' + b.dataset.relogin, true);
  });
  $('btn-login-new').addEventListener('click', function () { openNewLogin('', false); });

  function openNewLogin(url, go) {
    $('loginnew-url').value = url;
    state.winSites = {};
    renderNewLogin();
    if (ldlg.open) ldlg.close();
    ndlg.showModal();
    if (go) openWindow();
  }
  function openWindow() {
    var url = $('loginnew-url').value.trim();
    if (!url) return toast('error', '请填写登录页地址');
    var b = $('loginnew-open'); b.setAttribute('aria-busy', 'true');
    api('POST', '/api/logins/window', { url: url }).then(function (r) {
      b.removeAttribute('aria-busy');
      if (!r.ok) return MC.after(r);
      state.win = r.window; renderNewLogin();
    });
  }
  function renderNewLogin() {
    var w = state.win, mine = w && w.state === 'open' && !w.request;
    $('loginnew-state').hidden = !mine;
    $('loginnew-sites-box').hidden = !(mine && w.sites.length);
    $('loginnew-save').disabled = !(mine && w.sites.length);
    $('loginnew-sites').innerHTML = mine ? w.sites.map(function (s) {
      var on = state.winSites[s.domain] !== undefined ? state.winSites[s.domain] : s.default;
      return '<li><input type="checkbox" data-site="' + esc(s.domain) + '"' + (on ? ' checked' : '') + ' aria-label="' + esc(s.domain) + '">' + fav(s.domain) +
        '<span><b>' + esc(s.domain) + '</b>' + (s.title ? '<span class="t">' + esc(s.title) + '</span>' : '') + '</span></li>';
    }).join('') : '';
  }
  $('loginnew-sites').addEventListener('change', function (e) { if (e.target.dataset.site) state.winSites[e.target.dataset.site] = e.target.checked; });
  $('loginnew-open').addEventListener('click', openWindow);
  $('loginnew-url').addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); openWindow(); } });
  $('loginnew-save').addEventListener('click', function () { finishWindow(this, true); });
  function closeNew() {
    if (state.win && state.win.state === 'open' && !state.win.request) api('POST', '/api/logins/window/cancel').then(function () {});
    if (ndlg.open) ndlg.close();
  }
  $('loginnew-cancel').addEventListener('click', closeNew);
  $('loginnew-x').addEventListener('click', closeNew);
  ndlg.addEventListener('cancel', function (e) { e.preventDefault(); closeNew(); });

  /* ---------------- 签发（P3 / P4） ---------------- */
  var dlg = $('dlg-issue');
  function caps() { return { folder: $('issue-cap-folder').checked, browser: $('issue-cap-browser').checked }; }
  function applyCaps() {
    var c = caps();
    $('sec-folder').hidden = !c.folder;
    $('sec-browser').hidden = !c.browser;
    $('cmd-limit').hidden = !c.folder;
    $('cmd-opts').hidden = !c.folder;
    $('web-only').hidden = c.folder || !c.browser;
    $('issue-name').placeholder = c.folder ? '默认使用文件夹名' : '默认为“浏览器”';
    summary();
  }
  $('issue-cap-folder').addEventListener('change', applyCaps);
  $('issue-cap-browser').addEventListener('change', applyCaps);

  function renderLoginChips() {
    var box = $('issue-logins');
    if (!box) return;
    box.innerHTML = state.logins.map(function (x) {
      var on = state.pickLogins.indexOf(x.domain) >= 0;
      return '<button class="mc-login' + (x.stale ? ' is-stale' : '') + '" type="button" aria-pressed="' + on + '" data-dom="' + esc(x.domain) + '">' +
        esc(x.domain) + (x.stale ? ' <small>' + esc(x.saved_at.split(' ')[0]) + ' 保存</small>' : '') + '</button>';
    }).join('') + '<button class="btn btn--ghost btn--sm" type="button" id="issue-newlogin"><span class="lbl">新建登录</span></button>';
    $('issue-login-warn').hidden = !state.pickLogins.length;
  }
  $('issue-logins').addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    if (b.id === 'issue-newlogin') { dlg.close(); openNewLogin('', false); return; }
    var d = b.dataset.dom, i = state.pickLogins.indexOf(d);
    if (i >= 0) state.pickLogins.splice(i, 1); else state.pickLogins.push(d);
    renderLoginChips();
  });

  function folderChips() {
    $('issue-folders').innerHTML = state.folders.map(function (f, i) {
      var name = f.replace(/[\\\/]+$/, '').split(/[\\\/]/).pop();
      return '<li><svg class="ic" aria-hidden="true"><use href="#i-box"></use></svg><span class="mc-pk-name">' + esc(name) + '</span>' +
        '<span class="mc-pk-path" title="' + esc(f) + '">' + esc(f) + '</span>' +
        '<button class="cbtn" type="button" data-rm="' + i + '" aria-label="移除 ' + esc(name) + '"><svg class="ic"><use href="#i-close"></use></svg></button></li>';
    }).join('');
    summary();
  }

  function addFolder(p) {
    p = (p || '').trim().replace(/^"+|"+$/g, '').replace(/^file:\/\/\//, '');
    try { p = decodeURIComponent(p); } catch (e) {}
    if (/^[A-Za-z]:/.test(p)) p = p.replace(/\//g, '\\');
    if (!p) return Promise.resolve(false);
    return api('POST', '/api/fs/check', { folder: p }).then(function (r) {
      if (!r.ok) { toast('error', p + '：' + (r.msg || '不可授权')); return false; }
      if (!state.folders.some(function (f) { return f.toLowerCase() === r.real.toLowerCase(); })) state.folders.push(r.real);
      folderChips();
      return true;
    });
  }

  function dropBusy(text) {
    $('issue-drop').classList.toggle('is-busy', !!text);
    $('issue-drop-t').innerHTML = text ? esc(text) : '拖入文件夹，或<b>点击选择</b>';
  }

  $('issue-folders').addEventListener('click', function (e) {
    var b = e.target.closest('[data-rm]'); if (!b) return;
    state.folders.splice(+b.dataset.rm, 1); folderChips();
  });

  function pick() {
    if ($('issue-drop').classList.contains('is-busy')) return;
    dropBusy('已在桌面打开选择窗口');
    api('POST', '/api/fs/pick', { start: state.folders[0] ? state.folders[0].replace(/\\[^\\]+$/, '') : '' }).then(function (r) {
      dropBusy('');
      if (!r.ok) return MC.after(r);
      (r.paths || []).forEach(addFolder);
    });
  }
  $('issue-drop').addEventListener('click', pick);
  $('issue-drop').addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } });

  function readNames(dir) {
    return new Promise(function (res) {
      try { dir.createReader().readEntries(function (es) { res(es.slice(0, 200).map(function (x) { return x.name; })); }, function () { res([]); }); }
      catch (e) { res([]); }
    });
  }
  var depth = 0;
  dlg.addEventListener('dragenter', function (e) { e.preventDefault(); if (++depth === 1) $('issue-drop').classList.add('is-over'); });
  dlg.addEventListener('dragleave', function () { if (--depth <= 0) { depth = 0; $('issue-drop').classList.remove('is-over'); } });
  dlg.addEventListener('dragover', function (e) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; });
  dlg.addEventListener('drop', function (e) {
    e.preventDefault(); depth = 0; $('issue-drop').classList.remove('is-over');
    if ($('issue-form').hidden || !caps().folder) return;
    var dt = e.dataTransfer;
    var entries = [].slice.call(dt.items || []).map(function (it) { return it.webkitGetAsEntry ? it.webkitGetAsEntry() : null; }).filter(Boolean);
    var text = dt.getData('text/uri-list') || dt.getData('text/plain');
    if (!entries.length) {
      if (text) text.split(/\r?\n/).filter(function (x) { return x && x[0] !== '#'; }).forEach(addFolder);
      return;
    }
    var dirs = entries.filter(function (x) { return x.isDirectory; });
    if (dirs.length < entries.length) toast('info', '只能授权文件夹，已忽略拖入的文件');
    if (!dirs.length) return;
    dropBusy('正在定位 ' + dirs.map(function (x) { return x.name; }).join('、'));
    Promise.all(dirs.map(readNames)).then(function (kids) {
      return api('POST', '/api/fs/resolve', { items: dirs.map(function (d, i) { return { name: d.name, children: kids[i] }; }) });
    }).then(function (r) {
      dropBusy('');
      if (!r.ok) return MC.after(r);
      r.results.forEach(function (x) {
        if (x.path) addFolder(x.path);
        else if (x.candidates.length > 1) toast('info', '存在多个名为“' + x.name + '”的文件夹，请点击选择');
        else toast('info', '未找到“' + x.name + '”的位置，请从资源管理器窗口拖入或点击选择');
      });
    });
  });
  window.addEventListener('dragover', function (e) { e.preventDefault(); });
  window.addEventListener('drop', function (e) { e.preventDefault(); });

  dlg.addEventListener('paste', function (e) {
    if ($('issue-form').hidden || !caps().folder || e.target.closest('input')) return;
    var t = (e.clipboardData || window.clipboardData).getData('text');
    if (!t) return;
    e.preventDefault();
    t.split(/\r?\n/).filter(function (x) { return x.trim(); }).forEach(addFolder);
  });

  function limitValue() {
    var v = segGet($('issue-limit'));
    if (v === 'custom') { var n = parseInt($('issue-custom').value, 10); return n > 0 ? Math.min(n, 100000) : 0; }
    return parseInt(v, 10);
  }

  function summary() {
    var c = caps(), m = parseInt(segGet($('issue-minutes')) || '60', 10), lim = limitValue();
    var end = new Date(Date.now() + m * 60000), today = new Date().getDate() === end.getDate();
    var when = '到期 <b>' + (today ? '' : '明天 ') + pad(end.getHours()) + ':' + pad(end.getMinutes()) + '</b>';
    var msg = '', ok = true;
    if (!c.folder && !c.browser) { msg = '请选择授权内容'; ok = false; }
    else if (c.folder && !state.folders.length) { msg = '请选择文件夹'; ok = false; }
    else if (c.folder && lim === 0) { msg = '次数须大于 0'; ok = false; }
    else msg = when + (c.folder ? (lim > 0 ? ' 或用完 <b>' + lim + ' 次</b>' : '，次数不限') : '');
    $('issue-sum').innerHTML = msg;
    $('issue-go').disabled = !ok;
  }
  ['issue-minutes', 'issue-net', 'issue-confirm'].forEach(function (id) { segBind($(id), summary); });
  segBind($('issue-limit'), function (v) { $('issue-custom-box').hidden = v !== 'custom'; summary(); });
  $('issue-custom').addEventListener('input', function () { this.value = this.value.replace(/\D/g, ''); summary(); });

  function openIssue() {
    var last = state.last || {};
    state.folders = (last.folders || []).slice(0, 1);
    state.pickLogins = [];
    $('issue-cap-folder').checked = last.browser && !(last.folders || []).length ? false : true;
    $('issue-cap-browser').checked = !!last.browser;
    $('issue-name').value = '';
    dropBusy('');
    segSet($('issue-minutes'), last.minutes || 60);
    var lim = last.limit === undefined ? 20 : last.limit;
    var preset = ['5', '20', '50', '-1'].indexOf(String(lim)) >= 0;
    segSet($('issue-limit'), preset ? lim : 'custom');
    $('issue-custom-box').hidden = preset;
    if (!preset) $('issue-custom').value = lim;
    segSet($('issue-net'), last.net ? 1 : 0);
    segSet($('issue-confirm'), last.confirm ? 1 : 0);
    $('issue-form').hidden = false; $('issue-foot').hidden = false;
    $('issue-done').hidden = true; $('issue-foot2').hidden = true;
    $('dlg-issue-h').textContent = '签发临时授权';
    state.issued = null;
    folderChips();
    renderLoginChips();
    applyCaps();
    dlg.showModal();
    loadLogins();
  }
  $('btn-issue').addEventListener('click', openIssue);

  function copy(text) {
    if (!text) return Promise.resolve(false);
    function fallback() {
      var ta = document.createElement('textarea');
      ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.opacity = '0';
      (dlg.open ? dlg : document.body).appendChild(ta); ta.select();
      var ok = false; try { ok = document.execCommand('copy'); } catch (e) {}
      ta.remove(); return ok;
    }
    if (navigator.clipboard && navigator.clipboard.writeText)
      return navigator.clipboard.writeText(text).then(function () { return true; }, function () { return fallback(); });
    return Promise.resolve(fallback());
  }

  $('issue-go').addEventListener('click', function () {
    var b = this;
    if (b.disabled) return;
    var c = caps();
    b.disabled = true; b.querySelector('.lbl').textContent = '签发中';
    var body = { folders: c.folder ? state.folders : [], browser: c.browser, logins: c.browser ? state.pickLogins : [],
      name: $('issue-name').value.trim(), minutes: parseInt(segGet($('issue-minutes')), 10),
      limit: limitValue(), net: c.folder && segGet($('issue-net')) === '1', confirm: c.folder && segGet($('issue-confirm')) === '1' };
    api('POST', '/api/grants', body).then(function (r) {
      b.disabled = false; b.querySelector('.lbl').textContent = '签发';
      if (!r.ok) return MC.after(r);
      state.last = { folders: r.grant.folders, minutes: body.minutes, limit: body.limit, net: body.net, confirm: body.confirm, browser: body.browser };
      state.issued = r;
      upsertGrant(r.grant);
      copy(r.prompt).then(function (ok) { showIssued(r, ok); });
    });
  });

  function showIssued(r, copied) {
    var g = r.grant, s = state.status, hasF = g.folders.length > 0;
    var reachable = s && s.tunnel.state === 'on' && s.routes.some(function (x) { return x.id === 'grant' && x.service.state === 'running'; });
    $('dlg-issue-h').textContent = '已签发';
    $('issue-form').hidden = true; $('issue-foot').hidden = true;
    $('issue-done').hidden = false; $('issue-foot2').hidden = false;
    $('issue-done').innerHTML =
      (copied ? '<p class="mc-ok">提示词已复制到剪贴板，包含连接地址和授权范围。</p>' :
        '<p class="mc-bad">自动复制失败，请点击“再次复制提示词”。</p>') +
      (reachable ? '' : '<p class="mc-bad">外网访问已关闭或临时授权服务未运行，开启后对方才能连接。</p>') +
      '<dl class="mc-dl"><dt>用途</dt><dd>' + esc(g.name) + '</dd>' +
      (hasF ? '<dt>文件夹</dt><dd>' + esc(g.folders.join('、')) + '</dd>' : '') +
      (g.browser ? '<dt>浏览器</dt><dd>' + (g.logins.length ? '登录 ' + esc(g.logins.join('、')) : '无登录') + '</dd>' : '') +
      '<dt>到期</dt><dd>' + esc(g.expires_at) + '</dd>' +
      (hasF ? '<dt>次数</dt><dd>' + (g.limit < 0 ? '不限' : g.limit + ' 次') + '</dd><dt>命令联网</dt><dd>' + (g.net ? '允许' : '不允许') +
        '</dd><dt>执行前确认</dt><dd>' + (g.confirm ? '需要' : '不需要') + '</dd>' : '') + '</dl>' +
      '<p class="mc-k">连接地址仅显示一次，关闭后无法再次获取；如遗失，请吊销后重新签发。</p>';
  }
  $('issue-copy').addEventListener('click', function () {
    if (!state.issued) return;
    copy(state.issued.prompt).then(function (ok) { toast(ok ? 'success' : 'error', ok ? '提示词已复制' : '复制失败'); });
  });
  dlg.addEventListener('close', function () { state.issued = null; });

  /* ---------------- 规则（P6） ---------------- */
  var rdlg = $('dlg-rules');
  $('btn-rules').addEventListener('click', function () {
    $('verify-out').hidden = true;
    api('GET', '/api/rules').then(function (r) {
      if (!r.ok) return MC.after(r);
      $('rules-blocked').textContent = r.blocked_today;
      $('rules-list').innerHTML = r.rules.map(function (x) { return '<dt>' + esc(x.name) + '</dt><dd>' + esc(x.desc) + '</dd>'; }).join('');
      rdlg.showModal();
    });
  });
  $('btn-verify').addEventListener('click', function () {
    var b = this, out = $('verify-out');
    b.setAttribute('aria-busy', 'true'); b.querySelector('.lbl').textContent = '检查中';
    out.hidden = false; out.innerHTML = '<p class="mc-k">正在以 aitemp 身份逐项检查，约 30 秒。</p>';
    api('POST', '/api/sandbox/verify').then(function (r) {
      b.removeAttribute('aria-busy'); b.querySelector('.lbl').textContent = '检查沙盒权限';
      if (!r.ok) { out.innerHTML = '<p class="mc-bad">' + esc(r.msg || '检查失败') + '</p>'; return; }
      var bad = r.checks.filter(function (c) { return !c[1]; });
      out.innerHTML = (r.passed ? '<p class="mc-ok">通过：' + r.checks.length + ' 项均被拒绝。</p>' :
        '<p class="mc-bad">未通过 ' + bad.length + ' 项：</p>') +
        (r.fixed && r.fixed.length ? '<p class="mc-k">已自动修复：' + esc(r.fixed.join('；')) + '</p>' : '') +
        '<ul class="mc-checks">' + (r.passed ? r.checks : bad).map(function (c) {
          return '<li class="' + (c[1] ? '' : 'is-bad') + '"><span>' + esc(c[0]) + '</span><span class="mc-m">' + esc(c[2]) + '</span></li>';
        }).join('') + '</ul>';
    });
  });

  /* ---------------- 状态与提示（R4.6） ---------------- */
  MC.on('status', function (s) {
    state.status = s;
    var g = s.grants || {};
    $('blocked-n').textContent = g.blocked_today || 0;
    var route = s.routes.find(function (x) { return x.id === 'grant'; });
    var warn = $('grant-warn'), msg = '';
    if (!g.deployed) msg = '临时授权未安装。';
    else if (!route || route.service.state !== 'running' || !g.online) msg = '临时授权服务未运行，所有授权地址暂不可用。';
    else if (!g.helper || !g.helper.ok) msg = '授权助手（Windows 服务 AITempHelper）未就绪：' + ((g.helper && g.helper.msg) || '') + '。命令暂无法执行。';
    else if (s.tunnel.state !== 'on') msg = '外网访问已关闭，所有授权地址暂不可用；仍可签发。';
    warn.hidden = !msg;
    warn.innerHTML = msg ? esc(msg) + (g.deployed ? ' <button class="pill pill--sm" type="button" data-go-status><span class="lbl">去开启</span></button>' : '') : '';
    $('helper-meta').textContent = g.helper && g.helper.version ? '授权助手 ' + g.helper.version : '';
    $('btn-issue').disabled = !(g.deployed && g.online);
    if (g.deployed && g.online && !state.loaded) { state.loaded = true; init(); }
  });
  $('grant-warn').addEventListener('click', function (e) { if (e.target.closest('[data-go-status]')) MC.go('status'); });

  /* ---------------- 事件 ---------------- */
  MC.on('grant.changed', upsertGrant);
  MC.on('approval.created', function (a) {
    if (!state.approvals.some(function (x) { return x.id === a.id; })) state.approvals.push(a);
    state.pendMin = false;
    renderPend();
  });
  MC.on('approval.resolved', function (d) { removeApproval(d.id); });
  MC.on('login.created', function (r) {
    if (!state.loginReqs.some(function (x) { return x.id === r.id; })) state.loginReqs.push(r);
    state.pendMin = false;
    renderPend();
  });
  MC.on('login.changed', function (r) {
    var i = state.loginReqs.findIndex(function (x) { return x.id === r.id; });
    if (i >= 0) state.loginReqs[i] = r; else state.loginReqs.push(r);
    renderPend();
  });
  MC.on('login.resolved', function (d) { removeLoginReq(d.id); });
  MC.on('logins.changed', function () { loadLogins(); });
  MC.on('loginwin.changed', function (w) {
    var was = state.win;
    state.win = w;
    if (w.state === 'done' && ndlg.open) ndlg.close();
    if ((w.state === 'closed' || w.state === 'cancelled') && was && was.state === 'open') {
      if (ndlg.open) ndlg.close();
      if (w.state === 'closed') toast('info', '登录窗口已关闭');
    }
    renderPend();
    renderNewLogin();
  });
  MC.on('log.created', function (l) {
    if (state.logs.some(function (x) { return x.id === l.id; })) return;
    state.logs.unshift(l);
    if (state.logs.length > 500) state.logs.length = 500;
    renderLogs();
  });
  MC.on('log.updated', function (l) {
    var i = state.logs.findIndex(function (x) { return x.id === l.id; });
    if (i >= 0) state.logs[i] = l; else state.logs.unshift(l);
    if (state.open[l.id] && state.open[l.id] !== true) {
      api('GET', '/api/logs/' + l.id).then(function (r) { if (r.ok && state.open[l.id]) { state.open[l.id] = r.log; renderLogs(); } });
    }
    renderLogs();
  });
  MC.on('reconnect', function () { if (state.loaded) init(); });

  function init() {
    loadGrants(); loadLogs(); loadApprovals(); loadLogins();
  }
})();
