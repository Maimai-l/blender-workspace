(function () {
  'use strict';
  var R = window.React, h = R.createElement, useState = R.useState, useEffect = R.useEffect, useRef = R.useRef;
  var E = window.Endfield;

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function pad(n) { return String(n).padStart(2, '0'); }
  function hm(d) { return pad(d.getHours()) + ':' + pad(d.getMinutes()); }
  function hms(d) { return hm(d) + ':' + pad(d.getSeconds()); }
  function left(ms) {
    if (ms <= 0) return '已到期';
    var m = Math.floor(ms / 60000), s = Math.floor(ms / 1000) % 60;
    if (m >= 60) return Math.floor(m / 60) + ' 小时 ' + (m % 60) + ' 分';
    return m + ' 分 ' + pad(s) + ' 秒';
  }
  function val(e) { return e && e.target ? e.target.value : e; }

  // ================= 连接状态（现有页面，原样保留，演示数据） =================
  var lane = function (host, port, appPort, o) {
    return Object.assign({ host: host, port: port, app_port: appPort, proxy_listening: true, app_running: true, app_listening: true,
      reloading: false, project: '', secret_ok: true, check: { code: 401, msg: '正常', at: '14:06:40' } }, o || {});
  };
  var STATUS = { net: { mode: 'clash', port: 7897 }, tunnel: { running: true, connections: 4, exe_found: true }, agent: { online: true },
    blender: lane('bmcp.maimaiqiu.work', 8080, 9876),
    unity: lane('umcp.maimaiqiu.work', 8082, 6400, { app_running: false, app_listening: false }),
    exec: lane('xmcp.maimaiqiu.work', 8084, null) };

  function Cmd(p) {
    return h('button', { type: 'button', className: 'cmd' + (p.busy ? ' is-busy' : '') + (p.cls ? ' ' + p.cls : ''), disabled: p.disabled, onClick: p.onClick, 'aria-busy': p.busy || undefined },
      h('span', { className: 'cmd-cn' }, p.cn),
      p.busy ? h(E.Loading, { size: 16, ariaLabel: '处理中' }) : h('span', { className: 'cmd-en' }, p.en));
  }
  function Node(p) {
    return h('section', { className: 'node' + (p.cls ? ' ' + p.cls : ''), 'aria-label': p.name },
      h('div', { className: 'node-head' }, h('span', { className: 'node-idx' }, p.idx), h('span', { className: 'node-en' }, p.en)),
      h('p', { className: 'node-name' }, p.name),
      h('p', { className: 'node-state' + (p.tone ? ' is-' + p.tone : '') }, p.state),
      h('dl', { className: 'node-data' }, p.data.map(function (d) {
        return h(R.Fragment, { key: d[0] }, h('dt', null, d[0]), h('dd', { className: d[2] || '' }, d[1]));
      })),
      p.cmd);
  }
  function Link(p) { return h('div', { className: 'link' + (p.on ? ' is-on' : '') + (p.cls ? ' ' + p.cls : ''), 'aria-hidden': 'true' }); }

  function StatusView() {
    var s = STATUS, linked = true;
    function nodes(key, label, app, appEn) {
      var x = s[key];
      return {
        check: h(Node, { idx: '01', en: 'Check', name: label + ' 连通检测', state: '正常', data: [['响应', '401', 'num'], ['时间', x.check.at, 'num']], cmd: h(Cmd, { cn: '检测', en: 'Test' }) }),
        svc: h(Node, { idx: '03', en: 'Service', name: label + ' MCP 服务', state: '运行中', data: [['端口', String(x.port), 'num'], ['代理', '在线', 'cn']], cmd: h(Cmd, { cn: '停止', en: 'Stop' }) }),
        app: app ? h(Node, { idx: '04', en: appEn, name: app, state: x.app_listening ? '已连接' : '未启动', tone: x.app_listening ? '' : 'off',
          data: [['端口', String(x.app_port), 'num'], [key === 'unity' ? '工程' : '进程', x.app_running ? '运行' : (key === 'unity' ? '无' : '未运行'), 'cn']],
          cmd: h(Cmd, { cn: x.app_running ? '已打开' : '打开', en: 'Launch', disabled: x.app_running }) }) : null
      };
    }
    var b = nodes('blender', 'Blender', 'Blender 插件', 'Blender'), u = nodes('unity', 'Unity', 'Unity 编辑器', 'Unity'), x = nodes('exec', '命令执行');
    var tunnel = h(Node, { idx: '02', en: 'Tunnel', name: '外网访问', state: '已开启', cls: 'g rs c3',
      data: [['连接', '04', 'num'], ['Blender', s.blender.host], ['Unity', s.unity.host], ['命令执行', s.exec.host]], cmd: h(Cmd, { cn: '关闭', en: 'Close' }) });
    return h(R.Fragment, null,
      h('div', { className: 'sec' }, h('p', { className: 'over' }, 'Route'),
        h('div', { className: 'hub' },
          h('div', { className: 'g r1 c1 cell' }, b.check), h(Link, { cls: 'g r1 c2', on: linked }), tunnel, h(Link, { cls: 'g r1 c4', on: true }),
          h('div', { className: 'g r1 c5 cell' }, b.svc), h(Link, { cls: 'g r1 c6', on: true }), h('div', { className: 'g r1 c7 cell' }, b.app),
          h('div', { className: 'g r2 c1 lane2 cell' }, u.check), h(Link, { cls: 'g r2 c2 in2', on: true }), h(Link, { cls: 'g r2 c4 in2', on: true }),
          h('div', { className: 'g r2 c5 cell' }, u.svc), h(Link, { cls: 'g r2 c6', on: false }), h('div', { className: 'g r2 c7 cell' }, u.app),
          h('div', { className: 'g r3 c1 lane2 cell' }, x.check), h(Link, { cls: 'g r3 c2 in2', on: true }), h(Link, { cls: 'g r3 c4 in2', on: true }),
          h('div', { className: 'g r3 c5 cell' }, x.svc))),
      h('div', { className: 'sec' }, h('p', { className: 'over' }, 'Network'),
        h('section', { className: 'netbar', 'aria-label': 'blender 网络代理' },
          h('div', { className: 'net-main' }, h('p', { className: 'node-name' }, 'blender 网络代理'), h('p', { className: 'node-state' }, '已开启')),
          h('div', { className: 'net-cmd' }, h(Cmd, { cn: '关闭', en: 'Close' })))),
      h('p', { className: 'proto-note' }, '这一页是现有界面，原样保留；本次原型只新增“临时授权”。'));
  }

  // ================= 临时授权（新页面） =================
  var FOLDERS = [
    { value: 'D:\\Projects\\rss-digest', label: 'rss-digest', meta: 'D:\\Projects\\rss-digest' },
    { value: 'D:\\Projects\\wawa', label: 'wawa', meta: 'D:\\Projects\\wawa' },
    { value: 'D:\\Projects\\LDAdBlock', label: 'LDAdBlock', meta: 'D:\\Projects\\LDAdBlock' },
    { value: 'D:\\Projects\\cas-manager', label: 'cas-manager', meta: 'D:\\Projects\\cas-manager' },
    { value: 'D:\\Projects\\maa-cli', label: 'maa-cli（不可授权：托管配置和账号数据）', meta: '受保护', disabled: true },
    { value: 'D:\\Projects\\skland', label: 'skland（不可授权：登录脚本）', meta: '受保护', disabled: true }
  ];
  var DURATIONS = [{ value: 30, label: '30 分钟' }, { value: 60, label: '1 小时' }, { value: 240, label: '4 小时' }, { value: 1440, label: '1 天' }];
  var COUNTS = [{ value: '5', label: '5 次' }, { value: '20', label: '20 次' }, { value: '50', label: '50 次' }, { value: 'custom', label: '其他' }];
  var RULES = [
    ['路径范围', '命令和读写只能落在授权的文件夹里；出现其他盘符、上级目录（..）或用户目录就拦截'],
    ['受保护位置', 'C:\\Users\\blender、C:\\Users\\Administrator、C:\\ProgramData\\BlenderMCP、D:\\Projects\\maa-cli、D:\\Projects\\skland 一律不可访问'],
    ['计划任务与服务', 'schtasks、sc、New-Service、Register-ScheduledTask'],
    ['注册表', 'reg、regedit、Set-ItemProperty HKLM/HKCU'],
    ['账号与权限', 'net user、net localgroup、icacls、takeown、runas'],
    ['系统与防火墙', 'netsh、Set-NetFirewall*、bcdedit、shutdown'],
    ['编码与混淆', 'powershell -EncodedCommand、certutil -decode、Invoke-Expression 拼接字符串'],
    ['联网', '关闭“允许联网”时，pip、npm、git clone、curl 等一律拦截']
  ];
  var now0 = Date.now();
  var INITIAL = [
    { id: 'tk1', name: '部署 RSS 摘要小工具', folders: ['D:\\Projects\\rss-digest'], limit: 5, used: 3, issued: now0 - 26 * 60000, expires: now0 + 34 * 60000 + 12000, net: true, confirm: false, state: 'active' },
    { id: 'tk2', name: '修 wawa 打包脚本', folders: ['D:\\Projects\\wawa'], limit: 20, used: 1, issued: now0 - 40 * 60000, expires: now0 + 200 * 60000, net: false, confirm: true, state: 'active' },
    { id: 'tk0', name: '试跑 FastAPI 示例', folders: ['D:\\Projects\\cas-manager'], limit: 5, used: 5, issued: now0 - 5 * 3600000, expires: now0 - 4 * 3600000, net: true, confirm: false, state: 'used' }
  ];
  var t = function (minAgo) { return hms(new Date(now0 - minAgo * 60000)); };
  var LOGS = [
    { id: 'l1', at: t(25), tk: 'tk1', op: 'run', text: 'python -m venv .venv', res: 'ok', note: '退出码 0 · 4.1 秒' },
    { id: 'l2', at: t(23), tk: 'tk1', op: 'run', text: '.venv\\Scripts\\pip install -r requirements.txt', res: 'ok', note: '退出码 0 · 38.6 秒' },
    { id: 'l3', at: t(21), tk: 'tk1', op: 'read', text: 'C:\\Users\\blender\\.skland\\store', res: 'blocked', note: '受保护位置' },
    { id: 'l4', at: t(19), tk: 'tk1', op: 'run', text: 'schtasks /create /tn rss /tr run.bat /sc hourly', res: 'blocked', note: '计划任务与服务' },
    { id: 'l5', at: t(18), tk: 'tk1', op: 'run', text: '.venv\\Scripts\\python app.py --check', res: 'ok', note: '退出码 0 · 2.3 秒' },
    { id: 'l6', at: t(38), tk: 'tk2', op: 'run', text: 'python build.py --zip', res: 'ok', note: '退出码 0 · 6.8 秒' },
    { id: 'l7', at: t(36), tk: 'tk2', op: 'run', text: 'git clone https://github.com/example/patch-tool', res: 'blocked', note: '联网未允许' }
  ];

  function rel(ms) { return left(ms); }

  function TempAuth(props) {
    var toast = E.useToast();
    var tk = useState(INITIAL), tokens = tk[0], setTokens = tk[1];
    var lg = useState(LOGS), logs = lg[0], setLogs = lg[1];
    var pd = useState([{ id: 'p1', tk: 'tk2', text: 'python build.py --zip --sign', cwd: 'D:\\Projects\\wawa', at: hms(new Date(now0 - 45000)) }]), pending = pd[0], setPending = pd[1];
    var ck = useState(Date.now()), clock = ck[0], setClock = ck[1];
    var gw = useState(true), gwOn = gw[0], setGwOn = gw[1];
    var bz = useState(''), busy = bz[0], setBusy = bz[1];
    // form
    var fName = useState('部署天气提醒脚本'), name = fName[0], setName = fName[1];
    var fFolders = useState(['D:\\Projects\\rss-digest']), folders = fFolders[0], setFolders = fFolders[1];
    var fDur = useState(60), dur = fDur[0], setDur = fDur[1];
    var fCnt = useState('5'), cnt = fCnt[0], setCnt = fCnt[1];
    var fCustom = useState('10'), custom = fCustom[0], setCustom = fCustom[1];
    var fNet = useState(true), net = fNet[0], setNet = fNet[1];
    var fConfirm = useState(false), confirm = fConfirm[0], setConfirm = fConfirm[1];
    var issuedDlg = useState(null), issued = issuedDlg[0], setIssued = issuedDlg[1];
    var revDlg = useState(null), revoking = revDlg[0], setRevoking = revDlg[1];
    var rulesDlg = useState(false), showRules = rulesDlg[0], setShowRules = rulesDlg[1];
    var flt = useState('active'), filter = flt[0], setFilter = flt[1];
    var lf = useState('all'), logFilter = lf[0], setLogFilter = lf[1];
    var urlRef = useRef(null);

    useEffect(function () { var id = setInterval(function () { setClock(Date.now()); }, 1000); return function () { clearInterval(id); }; }, []);

    function stateOf(x) {
      if (x.state === 'revoked') return 'revoked';
      if (x.used >= x.limit) return 'used';
      if (x.expires <= clock) return 'expired';
      return 'active';
    }
    var STATE_TEXT = { active: '使用中', used: '次数用完', expired: '已到期', revoked: '已吊销' };
    var activeTokens = tokens.filter(function (x) { return stateOf(x) === 'active'; });
    var blockedToday = logs.filter(function (l) { return l.res === 'blocked'; }).length;

    var limit = cnt === 'custom' ? Math.max(1, Math.min(500, parseInt(custom, 10) || 0)) : parseInt(cnt, 10);
    var formOk = name.trim() && folders.length > 0 && limit > 0;
    var endAt = new Date(clock + dur * 60000);

    function issue() {
      setBusy('issue');
      sleep(700).then(function () {
        var id = 'tk' + Math.random().toString(36).slice(2, 7);
        var secret = 'tk_' + Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 10);
        var row = { id: id, name: name.trim(), folders: folders.slice(), limit: limit, used: 0, issued: Date.now(), expires: Date.now() + dur * 60000, net: net, confirm: confirm, state: 'active' };
        setTokens(function (a) { return [row].concat(a); });
        setIssued({ row: row, url: 'https://tmcp.maimaiqiu.work/t/' + secret + '/mcp' });
        setBusy('');
      });
    }
    function copyUrl() {
      var u = issued && issued.url;
      var done = function () { toast('success', '地址已复制'); };
      try {
        navigator.clipboard.writeText(u).then(done, function () { selectUrl(); });
      } catch (e) { selectUrl(); }
    }
    function selectUrl() {
      var el = urlRef.current; if (!el) return;
      var r = document.createRange(); r.selectNodeContents(el); var s = window.getSelection(); s.removeAllRanges(); s.addRange(r);
      toast('info', '已选中地址，按 Ctrl+C 复制');
    }
    function revoke(x) {
      setTokens(function (a) { return a.map(function (y) { return y.id === x.id ? Object.assign({}, y, { state: 'revoked' }) : y; }); });
      setPending(function (p) { return p.filter(function (q) { return q.tk !== x.id; }); });
      toast('success', '已吊销“' + x.name + '”，这个地址立即失效');
    }
    function decide(p, ok) {
      setPending(function (a) { return a.filter(function (q) { return q.id !== p.id; }); });
      setTokens(function (a) { return a.map(function (y) { return y.id === p.tk && ok ? Object.assign({}, y, { used: y.used + 1 }) : y; }); });
      setLogs(function (a) { return [{ id: 'l' + Date.now(), at: hms(new Date()), tk: p.tk, op: 'run', text: p.text, res: ok ? 'ok' : 'denied', note: ok ? '退出码 0 · 7.4 秒' : '你在面板上拒绝了' }].concat(a); });
      toast(ok ? 'success' : 'info', ok ? '已允许，命令开始执行' : '已拒绝，不计次数');
    }
    // 演示：模拟对方 AI 调用一次（一次正常、一次越界，轮流）
    var flip = useRef(0);
    function simulate() {
      var x = activeTokens[0];
      if (!x) { toast('error', '没有使用中的连接'); return; }
      var bad = flip.current++ % 2 === 1;
      var cmd = bad ? 'type ..\\..\\maa-cli\\export\\skland_info_latest.json' : 'python -m pytest -q';
      if (x.confirm && !bad) {
        setPending(function (p) { return p.concat([{ id: 'p' + Date.now(), tk: x.id, text: cmd, cwd: x.folders[0], at: hms(new Date()) }]); });
        toast('info', '“' + x.name + '”请求执行一条命令，等你确认');
        return;
      }
      setLogs(function (a) { return [{ id: 'l' + Date.now(), at: hms(new Date()), tk: x.id, op: 'run', text: cmd, res: bad ? 'blocked' : 'ok', note: bad ? '路径范围（上级目录）' : '退出码 0 · 3.0 秒' }].concat(a); });
      if (!bad) setTokens(function (a) { return a.map(function (y) { return y.id === x.id ? Object.assign({}, y, { used: y.used + 1 }) : y; }); });
      toast(bad ? 'error' : 'success', bad ? '已拦截一条越界命令，不计次数' : '“' + x.name + '”执行了一条命令');
    }

    var nameOf = {}; tokens.forEach(function (x) { nameOf[x.id] = x.name; });
    var rows = tokens.filter(function (x) { return filter === 'all' || stateOf(x) === 'active'; });
    var shownLogs = logs.filter(function (l) { return logFilter === 'all' || l.tk === logFilter; });

    // ---- 01–03：沙盒账号、网关、检查规则 ----
    var gate = h('div', { className: 'chain3' },
      h(Node, { idx: '01', en: 'Sandbox', name: '沙盒账号', state: '就绪', data: [['账号', 'aitemp'], ['登录界面', '隐藏', 'cn'], ['可访问', '仅授权文件夹', 'cn']],
        cmd: h(Cmd, { cn: '检查权限', en: 'Verify', busy: busy === 'verify', onClick: function () { setBusy('verify'); sleep(800).then(function () { setBusy(''); toast('success', '沙盒账号读不到受保护位置，检查通过'); }); } }) }),
      h(Link, { on: gwOn }),
      h(Node, { idx: '02', en: 'Gateway', name: '临时连接网关', state: gwOn ? '运行中' : '已停止', tone: gwOn ? '' : 'off',
        data: [['端口', '8086', 'num'], ['地址', 'tmcp.maimaiqiu.work'], ['使用中', String(activeTokens.length).padStart(2, '0'), 'num']],
        cmd: h(Cmd, { cn: gwOn ? '停止' : '启动', en: gwOn ? 'Stop' : 'Start', busy: busy === 'gw',
          onClick: function () { setBusy('gw'); sleep(700).then(function () { setGwOn(!gwOn); setBusy(''); toast('success', gwOn ? '网关已停止，所有临时地址暂时不可用' : '网关已启动'); }); } }) }),
      h(Link, { on: gwOn }),
      h(Node, { idx: '03', en: 'Rules', name: '执行前检查', state: '已启用', data: [['规则', String(RULES.length).padStart(2, '0'), 'num'], ['今天拦截', String(blockedToday).padStart(2, '0'), 'num'], ['越界处理', '拦截，不计次数', 'cn']],
        cmd: h(Cmd, { cn: '查看规则', en: 'Rules', onClick: function () { setShowRules(true); } }) }));

    // ---- 签发表单 ----
    var form = h('section', { className: 'issue', 'aria-label': '签发临时连接' },
      h('div', { className: 'issue-col' },
        h(E.TextField, { id: 'ta-name', label: '用途', help: '写给自己看的，日志和列表里都用这个名字', value: name, onChange: function (e) { setName(val(e)); }, clearable: true }),
        h('div', { className: 'field' },
          h('span', { className: 'flabel' }, '可访问的项目文件夹'),
          h(E.MultiSelect, { ariaLabel: '项目文件夹', options: FOLDERS, value: folders, onChange: setFolders, placeholder: '选择 D:\\Projects 下的文件夹', maxTags: 3 }),
          h('span', { className: 'fhelp' }, '只能读写这些文件夹。maa-cli、skland 含托管配置和账号数据，不能选。'))),
      h('div', { className: 'issue-col' },
        h('div', { className: 'field' }, h('span', { className: 'flabel' }, '有效期'),
          h(E.SegmentedControl, { ariaLabel: '有效期', options: DURATIONS, value: dur, onChange: setDur })),
        h('div', { className: 'field' }, h('span', { className: 'flabel' }, '可执行次数'),
          h('div', { className: 'cnt-row' },
            h(E.SegmentedControl, { ariaLabel: '可执行次数', options: COUNTS, value: cnt, onChange: setCnt }),
            cnt === 'custom' && h(E.TextField, { id: 'ta-custom', value: custom, onChange: function (e) { setCustom(val(e).replace(/\D/g, '')); }, unit: '次', size: 'sm', style: { width: 110 } })),
          h('span', { className: 'fhelp' }, '只有执行命令和写文件计次；读取、列目录和被拦截的调用不计。')),
        h('div', { className: 'checks' },
          h(E.Checkbox, { checked: net, onChange: function (e) { setNet(e.target.checked); } }, '允许联网（pip、npm 安装依赖，git 拉代码）'),
          h(E.Checkbox, { checked: confirm, onChange: function (e) { setConfirm(e.target.checked); } }, '每次执行前先在这里确认（你要在电脑或手机旁）')))
    );
    var issueBar = h('div', { className: 'issue-foot' },
      h('p', { className: 'issue-sum' },
        formOk ? h(R.Fragment, null, '到期：', h('b', null, '今天 ' + hm(endAt)), endAt.getDate() !== new Date(clock).getDate() ? '（明天）' : '', '，或用完 ', h('b', null, limit + ' 次'), '，以先到者为准')
          : '填写用途并至少选一个文件夹'),
      h('div', { className: 'issue-cmd' }, h(Cmd, { cn: '签发', en: 'Issue', busy: busy === 'issue', disabled: !formOk || !gwOn, onClick: issue })));

    // ---- 使用中 ----
    var cols = [
      { key: 'name', label: '用途', kind: 'name', render: function (x) {
        return h('div', { className: 'tk-name' }, h('span', null, x.name),
          h('span', { className: 'tk-tags' }, x.net ? h(E.Tag, { size: 'sm' }, '可联网') : h(E.Tag, { size: 'sm' }, '不联网'), x.confirm ? h(E.Tag, { size: 'sm', variant: 'accent' }, '逐次确认') : null));
      } },
      { key: 'folders', label: '文件夹', sortable: false, render: function (x) { return h('span', { className: 'mono' }, x.folders.map(function (f) { return f.replace('D:\\Projects\\', ''); }).join('、')); } },
      { key: 'used', label: '已用次数', kind: 'progress', sortValue: function (x) { return x.used / x.limit; }, render: function (x) {
        var pct = Math.round(100 * x.used / x.limit);
        return h('div', { className: 'usage' }, h('div', { className: 'usage-bar' }, h('i', { style: { width: pct + '%' } })), h('span', { className: 'num' }, x.used + ' / ' + x.limit));
      } },
      { key: 'expires', label: '剩余时间', kind: 'time', render: function (x) { var st = stateOf(x); return h('span', { className: 'num' }, st === 'active' ? rel(x.expires - clock) : '—'); } },
      { key: 'state', label: '状态', render: function (x) { var st = stateOf(x); return h(E.Status, { tone: st === 'active' ? 'default' : 'off' }, STATE_TEXT[st]); } },
      { key: 'act', label: '', sortable: false, render: function (x) {
        return stateOf(x) === 'active' ? h(E.Button, { variant: 'ghost', size: 'sm', onClick: function () { setRevoking(x); } }, '吊销')
          : h(E.Button, { variant: 'ghost', size: 'sm', onClick: function () { setLogFilter(x.id); toast('info', '日志已筛选到“' + x.name + '”'); } }, '看记录');
      } }
    ];
    var active = h('div', { className: 'panel' },
      h('div', { className: 'panel-head' },
        h(E.SegmentedControl, { ariaLabel: '筛选', options: [{ value: 'active', label: '使用中 ' + activeTokens.length }, { value: 'all', label: '全部 ' + tokens.length }], value: filter, onChange: setFilter }),
        h(E.Button, { variant: 'ghost', size: 'sm', icon: 'i-arrow-r', onClick: simulate }, '演示：模拟对方调用一次')),
      rows.length ? h('div', { className: 'tbl-wrap' }, h(E.Table, { ariaLabel: '临时连接', columns: cols, rows: rows, rowKey: 'id', minWidth: 760 }))
        : h(E.EmptyState, { title: '没有使用中的临时连接' }, '在上面签发一个，复制地址到对话 AI 的连接器设置里就能用。'));

    // ---- 待确认 ----
    var approvals = pending.length ? h('div', { className: 'sec' }, h('p', { className: 'over' }, 'Approval'),
      h('div', { className: 'approvals' }, pending.map(function (p) {
        return h('section', { key: p.id, className: 'approval', 'aria-label': '待确认的命令' },
          h('div', { className: 'ap-main' },
            h('p', { className: 'ap-meta' }, h('span', null, nameOf[p.tk] || ''), h('span', { className: 'num' }, p.at)),
            h('p', { className: 'ap-cmd mono' }, p.text),
            h('p', { className: 'ap-sub' }, '在 ', h('span', { className: 'mono' }, p.cwd), ' 执行 · 执行前检查已通过')),
          h('div', { className: 'ap-btns' },
            h(E.Button, { variant: 'secondary', size: 'sm', onClick: function () { decide(p, false); } }, '拒绝'),
            h(Cmd, { cn: '允许', en: 'Allow', onClick: function () { decide(p, true); } })));
      }))) : null;

    // ---- 执行记录 ----
    var RES = { ok: ['已执行', 'default'], blocked: ['已拦截', 'err'], denied: ['已拒绝', 'off'] };
    var OP = { run: '执行命令', read: '读文件', write: '写文件', list: '列目录' };
    var logCols = [
      { key: 'at', label: '时间', kind: 'time', width: 96 },
      { key: 'tk', label: '连接', width: 150, sortable: false, render: function (l) { return nameOf[l.tk] || l.tk; } },
      { key: 'op', label: '操作', width: 96, sortable: false, render: function (l) { return h(E.Tag, { size: 'sm' }, OP[l.op]); } },
      { key: 'text', label: '内容', width: 300, sortable: false, render: function (l) { return h('span', { className: 'mono clip', title: l.text }, l.text); } },
      { key: 'res', label: '结果', width: 88, render: function (l) { return h(E.Status, { tone: RES[l.res][1] }, RES[l.res][0]); } },
      { key: 'note', label: '说明', sortable: false }
    ];
    var audit = h('div', { className: 'panel' },
      h('div', { className: 'panel-head' },
        h(E.Select, { ariaLabel: '按连接筛选', size: 'sm', options: [{ value: 'all', label: '全部连接' }].concat(tokens.map(function (x) { return { value: x.id, label: x.name }; })), value: logFilter, onChange: setLogFilter }),
        h('span', { className: 'panel-note' }, '被拦截的调用不计次数，也会记在这里')),
      h('div', { className: 'tbl-wrap' }, h(E.Table, { ariaLabel: '执行记录', columns: logCols, rows: shownLogs, rowKey: 'id', minWidth: 860, defaultSort: { key: 'at', dir: 'descending' } })));

    return h(R.Fragment, null,
      h(E.Banner, { type: 'info', title: '原型' }, '数据是模拟的，可以点着试：签发、复制地址、吊销、确认、查看规则；“演示：模拟对方调用一次”会轮流模拟一次正常调用和一次越界调用。'),
      h('div', { className: 'sec' }, h('p', { className: 'over' }, 'Sandbox'), gate),
      h('div', { className: 'sec' }, h('p', { className: 'over' }, 'Issue'), h('div', { className: 'panel' }, form, issueBar)),
      approvals,
      h('div', { className: 'sec' }, h('p', { className: 'over' }, 'Active'), active),
      h('div', { className: 'sec' }, h('p', { className: 'over' }, 'Audit'), audit),

      h(E.Dialog, { open: !!issued, onClose: function () { setIssued(null); }, title: '临时连接已签发', confirmLabel: '我已复制',
        onConfirm: function () {} },
        issued && h('div', { className: 'dlg-issued' },
          h('p', null, '把这个地址添加到对话 AI 的连接器（自定义 MCP 服务）里。地址只显示这一次，关掉后无法再查看；忘了就吊销重新签发。'),
          h('div', { className: 'url-box' }, h('code', { ref: urlRef, className: 'mono' }, issued.url), h(E.Button, { variant: 'secondary', size: 'sm', onClick: copyUrl }, '复制')),
          h('dl', { className: 'node-data dlg-data' },
            h('dt', null, '用途'), h('dd', { className: 'cn' }, issued.row.name),
            h('dt', null, '文件夹'), h('dd', null, issued.row.folders.join('、')),
            h('dt', null, '有效期至'), h('dd', { className: 'num' }, hm(new Date(issued.row.expires))),
            h('dt', null, '可执行次数'), h('dd', { className: 'num' }, String(issued.row.limit)),
            h('dt', null, '联网'), h('dd', { className: 'cn' }, issued.row.net ? '允许' : '不允许'),
            h('dt', null, '逐次确认'), h('dd', { className: 'cn' }, issued.row.confirm ? '开' : '关')))),

      h(E.Dialog, { open: !!revoking, onClose: function () { setRevoking(null); }, title: '吊销这个临时连接？', danger: true, confirmLabel: '吊销',
        onConfirm: function () { revoke(revoking); } },
        revoking && h('p', null, '“' + revoking.name + '”的地址会立即失效，对方 AI 正在执行的命令会被中止。已用 ' + revoking.used + ' / ' + revoking.limit + ' 次。')),

      h(E.Dialog, { open: showRules, onClose: function () { setShowRules(false); }, title: '执行前检查规则', confirmLabel: '知道了', onConfirm: function () {} },
        h('p', { className: 'rules-lead' }, '规则只是第一道关：真正的边界是沙盒账号本身的文件夹权限，规则漏掉的写法也访问不到受保护位置。'),
        h('dl', { className: 'rules' }, RULES.map(function (r) { return h(R.Fragment, { key: r[0] }, h('dt', null, r[0]), h('dd', null, r[1])); })))
    );
  }

  // ================= 外壳：顶栏 + 两个页面 =================
  function App() {
    var th = useState(document.documentElement.dataset.theme || 'dark'), theme = th[0], setTheme = th[1];
    var pg = useState('temp'), page = pg[0], setPage = pg[1];
    function toggleTheme() {
      var next = theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = next;
      try { localStorage.setItem('bmcp-theme', next); } catch (e) {}
      setTheme(next);
    }
    return h(R.Fragment, null,
      h(E.TopBar, { title: 'MCP 控制台', actions: h(R.Fragment, null,
        h(E.Button, { variant: 'ghost', size: 'sm', onClick: toggleTheme }, theme === 'dark' ? '浅色' : '深色'),
        h(E.Button, { variant: 'ghost', size: 'sm', icon: 'i-refresh' }, '刷新')) }),
      h('nav', { className: 'pages' }, h('div', { className: 'pages-in' },
        h(E.Tabs, { variant: 'line', ariaLabel: '页面', value: page, onChange: setPage, items: [{ value: 'status', label: '连接状态' }, { value: 'temp', label: '临时授权' }] }))),
      h('main', { className: 'wrap' }, page === 'status' ? h(StatusView) : h(TempAuth)));
  }

  ReactDOM.createRoot(document.getElementById('root')).render(h(E.ToastProvider, null, h(App)));
})();
