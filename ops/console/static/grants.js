/* 临时授权页（P2）、签发（P3/P4）、待确认浮层（P5）、规则（P6）、执行记录详情。
   数据来自 /api/grants、/api/approvals、/api/logs，之后靠事件流更新；按钮只发请求。 */
(function () {
  'use strict';
  var MC = window.MC;
  if (!MC) return;
  var $ = function (id) { return document.getElementById(id); };
  var esc = MC.esc, api = MC.api, toast = MC.toast;

  var state = {
    grants: [], filter: 'active', logs: [], logGrant: '', open: {}, approvals: [], pendAll: false,
    status: null, last: null, issued: null, folders: [], loaded: false, skew: 0
  };

  function nowS() { return Date.now() / 1000 + state.skew; }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function left(sec) {
    if (sec <= 0) return '0:00';
    var h = Math.floor(sec / 3600), m = Math.floor(sec / 60) % 60, s = Math.floor(sec) % 60;
    return h ? h + ':' + pad(m) + ':' + pad(s) : m + ':' + pad(s);
  }
  function hm(t) { var d = new Date(t * 1000); return pad(d.getHours()) + ':' + pad(d.getMinutes()); }
  function segSet(el, v) { el.querySelectorAll('button').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.v === String(v))); }); }
  function segGet(el) { var b = el.querySelector('button[aria-pressed="true"]'); return b ? b.dataset.v : null; }
  function segBind(el, fn) {
    el.addEventListener('click', function (e) {
      var b = e.target.closest('button'); if (!b) return;
      segSet(el, b.dataset.v); if (fn) fn(b.dataset.v);
    });
  }

  /* ---------------- 授权列表 ---------------- */
  var STATE_WORD = { active: '生效中', expired: '已到期', used: '已用完', revoked: '已吊销' };

  function grantCard(g) {
    var total = (g.minutes || 60) * 60, rem = Math.max(0, g.expires - nowS());
    var active = g.state === 'active';
    var tPct = active ? Math.max(0, Math.min(100, 100 * rem / total)) : 0;
    var lim = g.limit < 0 ? '不限' : g.used + '/' + g.limit;
    var uPct = g.limit < 0 ? 0 : Math.min(100, 100 * g.used / Math.max(1, g.limit));
    var act;
    if (active) act = '<button class="pill pill--sm" type="button" data-log="' + g.id + '"><span class="lbl">查看记录</span></button>' +
      '<button class="btn btn--ghost ibtn btn--sm" type="button" aria-label="吊销" title="吊销" data-revoke="' + g.id + '"><svg class="ic"><use href="#i-trash"></use></svg></button>';
    else if (g.restorable) act = '<span class="mc-gstate">已吊销</span><button class="pill pill--sm" type="button" data-restore="' + g.id + '"><span class="lbl">恢复</span></button>';
    else act = '<span class="mc-gstate">' + (STATE_WORD[g.state] || g.state) + '</span><button class="pill pill--sm pill--muted" type="button" data-log="' + g.id + '"><span class="lbl">查看记录</span></button>';
    return '<div class="mc-grant' + (active ? '' : ' is-off') + '" data-theme="dark" data-id="' + g.id + '">' +
      '<div class="mc-gmain"><p class="mc-grant-name" title="' + esc(g.name) + '">' + esc(g.name) + '</p>' +
      '<p class="mc-m" title="' + esc(g.folders.join('\n')) + '">' + esc(g.folders.join('  ·  ')) + '</p>' +
      '<p class="mc-tags"><span>联网<b>' + (g.net ? '允许' : '不允许') + '</b></span><span>执行前确认<b>' + (g.confirm ? '需要' : '不需要') + '</b></span>' +
      '<span>到期<b>' + esc(g.expires_at) + '</b></span></p></div>' +
      '<div class="prog" role="progressbar" aria-valuenow="' + Math.round(tPct) + '" aria-valuemin="0" aria-valuemax="100" aria-label="剩余时间"><span class="prog-label">剩余时间</span>' +
      '<div class="prog-line"><div class="prog-track"><div class="prog-fill" style="--v:' + tPct + '%"></div></div><span class="v" data-left="' + g.id + '">' + (active ? left(rem) : '—') + '</span></div></div>' +
      '<div class="prog" role="progressbar" aria-valuenow="' + Math.round(uPct) + '" aria-valuemin="0" aria-valuemax="100" aria-label="已用次数"><span class="prog-label">已用次数</span>' +
      '<div class="prog-line"><div class="prog-track"><div class="prog-fill" style="--v:' + uPct + '%"></div></div><span class="v">' + lim + '</span></div></div>' +
      '<div class="mc-grant-act">' + act + '</div></div>';
  }

  function renderGrants() {
    var list = state.grants.filter(function (g) { return state.filter === 'all' || g.state === 'active' || g.restorable; });
    var box = $('grant-list');
    if (!list.length) {
      box.innerHTML = '<div class="mc-empty">' + (state.filter === 'active' ? '没有生效中的授权。点左边的“签发”，把一个文件夹临时交给对话 AI。' : '还没有签发过授权。') + '</div>';
    } else box.innerHTML = list.map(grantCard).join('');
    var n = state.grants.filter(function (g) { return g.state === 'active'; }).length;
    $('grant-n').textContent = n;
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
      if (!state.last && r.last_issue) state.last = r.last_issue;   // 上次签发的选择
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
        toast('info', '已吊销“' + r.grant.name + '”，地址立即失效', '恢复', function () { restore(r.grant.id); });
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

  /* 每秒刷新剩余时间；到期的那一刻重新拉一次 */
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
  var RES = { ok: ['已执行', ''], running: ['执行中', ' is-busy'], pending: ['待确认', ' is-busy'], blocked: ['已拦截', ' is-err'],
    denied: ['已拒绝', ' is-off'], error: ['出错', ' is-err'], timeout: ['超时', ' is-err'], cancelled: ['已中止', ' is-off'] };

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
    if (d === true) return '<p class="mc-k">读取中…</p>';
    var g = state.grants.find(function (x) { return x.id === l.grant_id; });
    return '<dl><dt>授权</dt><dd>' + esc(g ? g.name : l.grant || l.grant_id) + '</dd><dt>时间</dt><dd>' + esc(d.full_time) + '</dd>' +
      (d.cwd ? '<dt>工作目录</dt><dd>' + esc(d.cwd) + '</dd>' : '') + (d.shell ? '<dt>shell</dt><dd>' + esc(d.shell) + '</dd>' : '') +
      (d.exit !== null && d.exit !== undefined ? '<dt>退出码</dt><dd>' + d.exit + '</dd>' : '') + '</dl>' +
      '<div class="mc-lcmd"><code>' + esc(d.target) + '</code><button class="btn btn--ghost btn--sm" type="button" data-copy="' + d.id + '"><span class="lbl">复制命令</span></button></div>' +
      (d.output ? '<pre class="mc-out">' + esc(d.output) + '</pre>' : '');
  }

  function renderLogs() {
    var rows = state.logs.filter(function (l) { return !state.logGrant || l.grant_id === state.logGrant; });
    $('log-body').innerHTML = rows.length ? rows.map(logRow).join('') :
      '<div class="mc-empty">' + (state.logGrant ? '这条授权还没有调用记录。' : '还没有调用记录。对方的每次调用都会记在这里，包括被拦截和被拒绝的。') + '</div>';
  }

  function renderLogFilter() {
    var el = $('log-filter');
    if (!state.logGrant) { el.hidden = true; return; }
    var g = state.grants.find(function (x) { return x.id === state.logGrant; });
    el.hidden = false;
    el.innerHTML = '<span class="tag tag--sm">' + esc(g ? g.name : state.logGrant) +
      '<button class="rm" type="button" aria-label="显示全部记录"><svg class="ic"><use href="#i-close"></use></svg></button></span>';
  }

  function setLogGrant(id) {
    state.logGrant = id || '';
    renderLogFilter();
    loadLogs();
  }
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
      state.open[id] = r.ok ? r.log : { full_time: '', target: '', output: r.msg || '读不到' };
      renderLogs();
    });
  }

  $('log-body').addEventListener('click', function (e) {
    var c = e.target.closest('[data-copy]');
    if (c) {
      var d = state.open[c.dataset.copy];
      copy(d && d.target).then(function (ok) { toast(ok ? 'success' : 'error', ok ? '命令已复制' : '复制失败，请手动选中'); });
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

  /* ---------------- 待确认（P5） ---------------- */
  function renderPend() {
    var box = $('pend'), a = state.approvals;
    if (!a.length) { box.hidden = true; box.innerHTML = ''; return; }
    box.hidden = false;
    var items = state.pendAll ? a : [a[0]];
    box.innerHTML = '<div class="mc-pend-card">' +
      '<div class="alert-strip"><span class="alert-title">待确认</span><button class="meta mc-pend-more" type="button" aria-expanded="' + state.pendAll + '" title="' +
      (a.length > 1 ? (state.pendAll ? '只看第一条' : '展开全部') : '') + '">' + (state.pendAll ? a.length + ' 条' : '1/' + a.length) + '</button>' +
      '<button class="cbtn mc-pend-min" type="button" aria-label="' + (state.pendMin ? '展开' : '收起') + '" title="' + (state.pendMin ? '展开' : '收起') + '">' +
      '<svg class="ic"><use href="#' + (state.pendMin ? 'i-plus' : 'i-minus') + '"></use></svg></button></div>' +
      '<div class="mc-pend-list"' + (state.pendMin ? ' hidden' : '') + '>' + items.map(function (p) {
        return '<div class="mc-pend-body" data-ap="' + p.id + '"><p class="mc-cmd">' + esc(p.command) + '</p>' +
          '<dl><dt>授权</dt><dd>' + esc(p.grant) + '</dd><dt>工作目录</dt><dd title="' + esc(p.cwd) + '">' + esc(p.cwd) + '</dd>' +
          '<dt>shell</dt><dd>' + esc(p.shell) + '</dd><dt>请求时间</dt><dd>' + esc(p.time) + '</dd></dl>' +
          '<div class="mc-pend-act"><button class="pill" type="button" data-deny="' + p.id + '"><span class="lbl">拒绝</span></button>' +
          '<button class="pill" type="button" data-allow="' + p.id + '"><span class="lbl">允许</span></button></div></div>';
      }).join('') + '</div></div>';
  }

  $('pend').addEventListener('click', function (e) {
    if (e.target.closest('.mc-pend-min')) { state.pendMin = !state.pendMin; renderPend(); return; }
    if (e.target.closest('.mc-pend-more')) { state.pendMin = false; if (state.approvals.length > 1) { state.pendAll = !state.pendAll; renderPend(); } return; }
    var b = e.target.closest('[data-allow],[data-deny]'); if (!b) return;
    var id = b.dataset.allow || b.dataset.deny, allow = !!b.dataset.allow;
    b.setAttribute('aria-busy', 'true');
    api('POST', '/api/approvals/' + id, { allow: allow }).then(function (r) {
      if (!r.ok && r._status !== 409) { b.removeAttribute('aria-busy'); return MC.after(r); }
      removeApproval(id);
      toast(allow ? 'success' : 'info', allow ? '已允许，命令开始执行' : '已拒绝，不计次数');
    });
  });

  function removeApproval(id) {
    state.approvals = state.approvals.filter(function (x) { return x.id !== id; });
    if (state.approvals.length < 2) state.pendAll = false;
    renderPend();
  }

  function loadApprovals() {
    return api('GET', '/api/approvals').then(function (r) { if (r.ok) { state.approvals = r.approvals; renderPend(); } });
  }

  /* ---------------- 签发（P3 / P4） ---------------- */
  var dlg = $('dlg-issue');

  function folderChips() {
    $('issue-folders').innerHTML = state.folders.map(function (f, i) {
      return '<span class="tag" title="' + esc(f) + '">' + esc(f) + '<button class="rm" type="button" data-rm="' + i + '" aria-label="移除"><svg class="ic"><use href="#i-close"></use></svg></button></span>';
    }).join('') || '<span class="mc-k">还没选文件夹</span>';
    summary();
  }

  function addFolder(p) {
    p = (p || '').trim().replace(/^"+|"+$/g, '').replace(/^file:\/\/\//, '');
    if (/^[A-Za-z]:/.test(p)) p = p.replace(/\//g, '\\');
    try { p = decodeURIComponent(p); } catch (e) {}
    if (!p) return;
    var box = $('issue-path-box');
    box.classList.remove('is-error');
    api('POST', '/api/fs/check', { folder: p }).then(function (r) {
      if (!r.ok) { box.classList.add('is-error'); toast('error', r.msg || '这个文件夹不能授权'); return; }
      if (state.folders.some(function (f) { return f.toLowerCase() === r.real.toLowerCase(); })) return;
      state.folders.push(r.real);
      $('issue-path').value = '';
      folderChips();
    });
  }

  $('issue-folders').addEventListener('click', function (e) {
    var b = e.target.closest('[data-rm]'); if (!b) return;
    state.folders.splice(+b.dataset.rm, 1); folderChips();
  });
  $('issue-add').addEventListener('click', function () { addFolder($('issue-path').value); });
  $('issue-path').addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); addFolder(this.value); } });
  $('issue-path').addEventListener('input', function () { $('issue-path-box').classList.remove('is-error'); });
  // 从资源管理器拖进来：浏览器只给文件名、不给完整路径；拖的是文字（地址栏里的路径）就能用
  [$('issue-path-box'), $('issue-folders')].forEach(function (el) {
    el.addEventListener('dragover', function (e) { e.preventDefault(); });
    el.addEventListener('drop', function (e) {
      e.preventDefault();
      var t = e.dataTransfer.getData('text/uri-list') || e.dataTransfer.getData('text/plain');
      if (t) { t.split(/\r?\n/).filter(function (x) { return x && x[0] !== '#'; }).forEach(addFolder); return; }
      toast('info', '浏览器拿不到拖进来的文件夹的完整路径。请点“浏览…”选择，或者从资源管理器的地址栏复制路径粘贴进来');
    });
  });
  $('issue-pick').addEventListener('click', function () {
    var b = this; b.setAttribute('aria-busy', 'true');
    toast('info', '已在桌面上打开选择框，选好后点“确定”');
    api('POST', '/api/fs/pick', { start: state.folders[0] || '' }).then(function (r) {
      b.removeAttribute('aria-busy');
      if (!r.ok) return MC.after(r);
      if (r.path) addFolder(r.path);
    });
  });

  /* 页内浏览 */
  function browse(path) {
    var box = $('issue-fs');
    box.hidden = false;
    box.innerHTML = '<p class="mc-k">读取中…</p>';
    api('GET', '/api/fs?path=' + encodeURIComponent(path || '')).then(function (r) {
      if (!r.ok) { box.innerHTML = '<p class="mc-k">' + esc(r.msg || '打不开') + '</p>'; return; }
      var h = '<div class="mc-fs-bar">' + (r.path ? '<button class="btn btn--ghost btn--sm" type="button" data-cd="' + esc(r.parent || '') + '"><span class="lbl">上一级</span></button>' : '') +
        '<span class="mc-m">' + esc(r.path || '此电脑') + '</span></div><ul class="mc-fs-list">';
      h += r.dirs.map(function (d) {
        return '<li><button class="mc-fs-name" type="button" ' + (d.enter !== false ? 'data-cd="' + esc(d.path) + '"' : 'disabled') + '>' + esc(d.name) + '</button>' +
          (d.ok ? '<button class="pill pill--sm" type="button" data-choose="' + esc(d.path) + '"><span class="lbl">选这个</span></button>' :
            '<span class="mc-k">' + esc(d.reason) + '</span>') + '</li>';
      }).join('') || '<li class="mc-k">没有子文件夹</li>';
      box.innerHTML = h + '</ul>';
    });
  }
  $('issue-browse').addEventListener('click', function () {
    var box = $('issue-fs');
    if (!box.hidden) { box.hidden = true; return; }
    browse(state.folders[0] ? state.folders[0].replace(/\\[^\\]+$/, '') : 'D:\\Projects');
  });
  $('issue-fs').addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    if (b.dataset.choose) { addFolder(b.dataset.choose); return; }
    if (b.hasAttribute('data-cd')) browse(b.dataset.cd);
  });

  function limitValue() {
    var v = segGet($('issue-limit'));
    if (v === 'custom') { var n = parseInt($('issue-custom').value, 10); return n > 0 ? Math.min(n, 100000) : 0; }
    return parseInt(v, 10);
  }

  function summary() {
    var m = parseInt(segGet($('issue-minutes')) || '60', 10), lim = limitValue();
    var end = new Date(Date.now() + m * 60000), today = new Date().getDate() === end.getDate();
    var ok = state.folders.length > 0 && lim !== 0;
    $('issue-sum').innerHTML = !state.folders.length ? '先选一个文件夹' : lim === 0 ? '次数要大于 0' :
      '到期 <b>' + (today ? '' : '明天 ') + pad(end.getHours()) + ':' + pad(end.getMinutes()) + '</b>' + (lim > 0 ? '，或用完 <b>' + lim + ' 次</b>' : '，次数不限');
    $('issue-go').disabled = !ok;
  }
  ['issue-minutes', 'issue-net', 'issue-confirm'].forEach(function (id) { segBind($(id), summary); });
  segBind($('issue-limit'), function (v) { $('issue-custom-box').hidden = v !== 'custom'; summary(); });
  $('issue-custom').addEventListener('input', function () { this.value = this.value.replace(/\D/g, ''); summary(); });

  function openIssue() {
    var last = state.last || {};
    state.folders = (last.folders || []).slice(0, 1);
    $('issue-name').value = '';
    $('issue-path').value = '';
    $('issue-path-box').classList.remove('is-error');
    $('issue-fs').hidden = true;
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
    dlg.showModal();
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
    b.disabled = true; b.querySelector('.lbl').textContent = '签发中';
    var body = { folders: state.folders, name: $('issue-name').value.trim(), minutes: parseInt(segGet($('issue-minutes')), 10),
      limit: limitValue(), net: segGet($('issue-net')) === '1', confirm: segGet($('issue-confirm')) === '1' };
    api('POST', '/api/grants', body).then(function (r) {
      b.disabled = false; b.querySelector('.lbl').textContent = '签发';
      if (!r.ok) return MC.after(r);
      state.last = { folders: r.grant.folders, minutes: body.minutes, limit: body.limit, net: body.net, confirm: body.confirm };
      state.issued = r;
      upsertGrant(r.grant);
      copy(r.prompt).then(function (ok) { showIssued(r, ok); });
    });
  });

  function showIssued(r, copied) {
    var g = r.grant, s = state.status;
    var reachable = s && s.tunnel.state === 'on' && s.routes.some(function (x) { return x.id === 'grant' && x.service.state === 'running'; });
    $('dlg-issue-h').textContent = '已签发';
    $('issue-form').hidden = true; $('issue-foot').hidden = true;
    $('issue-done').hidden = false; $('issue-foot2').hidden = false;
    $('issue-done').innerHTML =
      (copied ? '<p class="mc-ok">提示词已复制到剪贴板，粘贴到对话里即可。里面有连接地址和这次授权的边界。</p>' :
        '<p class="mc-bad">没能自动复制。请点下面的“再次复制提示词”。</p>') +
      (reachable ? '' : '<p class="mc-bad">外网访问现在是关闭的（或临时授权服务没运行），对方暂时连不上；到“连接状态”页开启后就能用。</p>') +
      '<dl class="mc-dl"><dt>用途</dt><dd>' + esc(g.name) + '</dd><dt>文件夹</dt><dd>' + esc(g.folders.join('、')) + '</dd>' +
      '<dt>到期</dt><dd>' + esc(g.expires_at) + '</dd><dt>次数</dt><dd>' + (g.limit < 0 ? '不限' : g.limit + ' 次') + '</dd>' +
      '<dt>联网</dt><dd>' + (g.net ? '允许' : '不允许') + '</dd><dt>执行前确认</dt><dd>' + (g.confirm ? '需要' : '不需要') + '</dd></dl>' +
      '<p class="mc-k">连接地址只在这一次给出；关掉这个窗口后无法再取。忘了就吊销，重新签发一条。</p>';
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
    out.hidden = false; out.innerHTML = '<p class="mc-k">以 aitemp 的身份逐项试一遍，约半分钟……</p>';
    api('POST', '/api/sandbox/verify').then(function (r) {
      b.removeAttribute('aria-busy'); b.querySelector('.lbl').textContent = '检查沙盒权限';
      if (!r.ok) { out.innerHTML = '<p class="mc-bad">' + esc(r.msg || '检查失败') + '</p>'; return; }
      var bad = r.checks.filter(function (c) { return !c[1]; });
      out.innerHTML = (r.passed ? '<p class="mc-ok">通过：沙盒账号访问不到受保护位置，' + r.checks.length + ' 项都被拒绝。</p>' :
        '<p class="mc-bad">有 ' + bad.length + ' 项没通过：</p>') +
        (r.fixed && r.fixed.length ? '<p class="mc-k">顺手补上：' + esc(r.fixed.join('；')) + '</p>' : '') +
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
    if (!g.deployed) msg = '临时授权还没有安装。';
    else if (!route || route.service.state !== 'running' || !g.online) msg = '临时授权服务没有运行，所有授权地址暂时不可用。';
    else if (!g.helper || !g.helper.ok) msg = '授权助手（Windows 服务 AITempHelper）没有就绪：' + ((g.helper && g.helper.msg) || '') + '。命令暂时执行不了。';
    else if (s.tunnel.state !== 'on') msg = '外网访问已关闭，所有授权地址暂时不可用。仍可以签发，开启后就能连。';
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
    state.pendMin = false;   // 新请求到达时展开
    renderPend();
  });
  MC.on('approval.resolved', function (d) { removeApproval(d.id); });
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
    loadGrants(); loadLogs(); loadApprovals();
  }
})();
