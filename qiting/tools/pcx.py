#!/usr/bin/env python3
"""Talk to the Blender PC through the exec MCP server only (no Blender MCP endpoint needed).

Used since 2026-11-01, when the cloud endpoint for Blender went down after an 11 MB reply. Two helper scripts
live on the PC in <PC_ROOT>\\tools (sources in ../tools/pc/):
  brelay.py  runs a code file inside the live Blender through the add-on's local socket 127.0.0.1:9876;
  pack.py    wraps any file into lossless greyscale PNG pieces, which exec's file reader returns unchanged.

  pcx.py blender <file.py> ["prepended code"]   run a local file in Blender (prints its output)
  pcx.py code "<python>"                         run inline code in Blender
  pcx.py bash "<command>"                        Git Bash on the PC
  pcx.py fetch <remote path> <local path>        copy a file from the PC (any size, any type)
  pcx.py put <local path> <remote path>          copy a file to the PC
"""
import base64, io, json, os, struct, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import execc, xyp

PY = r'D:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe'
PCT = xyp.PC_ROOT + r'\tools'
TMP = xyp.PC_ROOT + r'\tmp'


def _unix(p):
    """C:\\a\\b -> /c/a/b for Git Bash."""
    p = p.replace('\\', '/')
    if len(p) > 1 and p[1] == ':':
        p = '/' + p[0].lower() + p[2:]
    return p


def _text(r):
    res = r.get('result', {})
    out = []
    for c in res.get('content', []):
        t = c.get('text', '')
        try:
            j = json.loads(t)
            if isinstance(j, dict) and 'stdout' in j:
                t = j.get('stdout', '') + (('\n[stderr] ' + j['stderr']) if j.get('stderr', '').strip() else '')
        except Exception:
            pass
        out.append(t)
    out = [o.replace('\nShell cwd was reset to C:\\Users\\blender\\ExecMCP', '').replace('\n[stderr] \n', '\n').rstrip() for o in out]
    if res.get('isError'):
        out.insert(0, 'EXEC TOOL ERROR:')
    if 'error' in r:
        out.insert(0, 'JSONRPC ERROR: ' + json.dumps(r['error']))
    return '\n'.join(out)


def bash(cmd, timeout_ms=85000):
    for attempt in range(3):
        try:
            return _text(execc.call('Bash', {'command': cmd, 'description': 'run command', 'timeout': timeout_ms}))
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(3)


def wait_file(remote, timeout_s=1800, round_s=75):
    """Wait until a file exists on the PC (e.g. the .done marker of a deferred render); returns its text."""
    t0 = time.time()
    u = _unix(remote)
    while time.time() - t0 < timeout_s:
        out = bash('for i in $(seq 1 %d); do if [ -f "%s" ]; then echo FOUND; cat "%s"; exit 0; fi; sleep 1; done; echo WAIT'
                   % (round_s, u, u), timeout_ms=(round_s + 10) * 1000)
        if 'FOUND' in out:
            return out.split('FOUND', 1)[1].strip()
    raise TimeoutError('no %s after %d s' % (remote, timeout_s))


def write_text(remote, text):
    """Write a NEW file on the PC (exec's Write refuses to overwrite files it has not read)."""
    r = execc.call('Write', {'file_path': remote, 'content': text})
    t = _text(r)
    if 'EXEC TOOL ERROR' in t or 'JSONRPC ERROR' in t:
        raise RuntimeError(t[:500])
    return remote


def put_text(remote, text):
    """Write or replace a text file on the PC."""
    tmp = TMP + '\\put_%s.tmp' % uuid.uuid4().hex[:10]
    write_text(tmp, text)
    out = bash('mkdir -p "$(dirname "%s")" && mv -f "%s" "%s" && echo ok' % (_unix(remote), _unix(tmp), _unix(remote)))
    if 'ok' not in out:
        raise RuntimeError(out)


def blender(code, poll=80, quiet=False):
    """Run code in the live Blender; returns everything it printed. Long jobs keep running on the PC while
    this polls in rounds of `poll` seconds (exec calls must finish within about 90 s)."""
    job = 'job_%s_%s' % (time.strftime('%H%M%S'), uuid.uuid4().hex[:6])
    src = TMP + '\\' + job + '.py'
    out = _unix(TMP + '\\' + job + '.out')
    write_text(src, code)
    wait = ('for i in $(seq 1 %d); do [ -f "%s.done" ] && break; sleep 0.25; done; '
            'if [ -f "%s.done" ]; then echo __DONE__ $(wc -c < "%s"); '
            '[ $(wc -c < "%s") -le 29000 ] && cat "%s" && rm -f "%s" "%s" "%s.done"; fi'
            % (poll * 4, out, out, out, out, out, _unix(src), out, out))
    r = bash('cd "%s" && (nohup "%s" tools/brelay.py "tmp/%s.py" "tmp/%s.out" > /dev/null 2>&1 &) ; %s'
             % (_unix(xyp.PC_ROOT), _unix(PY), job, job, wait), timeout_ms=(poll + 15) * 1000)
    t0 = time.time()
    while '__DONE__' not in r:
        if not quiet:
            print('  ... still running (%.0fs)' % (time.time() - t0), file=sys.stderr)
        r = bash(wait, timeout_ms=(poll + 15) * 1000)
    head, _, rest = r.partition('__DONE__')
    size = int(rest.split()[0])
    if size <= 29000:
        return rest.split('\n', 1)[1] if '\n' in rest else ''
    parts = []
    for off in range(0, size, 29000):
        parts.append(bash('tail -c +%d "%s" | head -c 29000' % (off + 1, out)))
    bash('rm -f "%s" "%s" "%s.done"' % (_unix(src), out, out))
    return ''.join(parts)


def fetch(remote, local, piece_mb=2.5):
    """Copy any file from the PC: pack.py turns it into PNG pieces, exec's Read returns them unchanged."""
    from PIL import Image
    d = TMP + '\\pk_' + uuid.uuid4().hex[:8]
    lst = bash('"%s" "%s/pack.py" "%s" "%s" %s' % (_unix(PY), _unix(PCT), remote, d, piece_mb), timeout_ms=85000)
    paths = [l.split()[0] for l in lst.splitlines() if l.strip().endswith(tuple('0123456789')) and '.png' in l]
    if not paths:
        raise RuntimeError('pack failed: ' + lst[:500])
    from concurrent.futures import ThreadPoolExecutor

    def get(p):
        for attempt in range(3):
            try:
                r = execc.call('Read', {'file_path': p})
                j = json.loads(r['result']['content'][0]['text'])
                im = Image.open(io.BytesIO(base64.b64decode(j['file']['base64'])))
                a = im.tobytes()
                if a[:4] != b'QTPK':
                    raise RuntimeError('piece %s came back altered (%s)' % (p, j['file'].get('dimensions')))
                i, n, ln = struct.unpack('>III', a[4:16])
                return a[im.size[0]:im.size[0] + ln]
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2)
    with ThreadPoolExecutor(6) as ex:
        data = b''.join(ex.map(get, paths))
    bash('rm -rf "%s"' % _unix(d))
    os.makedirs(os.path.dirname(os.path.abspath(local)) or '.', exist_ok=True)
    open(local, 'wb').write(data)
    return len(data)


def put(local, remote):
    """Copy a local file to the PC (base64 text through exec's Write, decoded there)."""
    b64 = base64.b64encode(open(local, 'rb').read()).decode('ascii')
    tmp = TMP + '\\up_%s.b64' % uuid.uuid4().hex[:8]
    write_text(tmp, '\n'.join(b64[i:i + 76] for i in range(0, len(b64), 76)))
    out = bash('mkdir -p "$(dirname "%s")" && base64 -d "%s" > "%s" && rm -f "%s" && wc -c < "%s"'
               % (_unix(remote), _unix(tmp), _unix(remote), _unix(tmp), _unix(remote)))
    return out.strip()


if __name__ == '__main__':
    a = sys.argv[1:]
    t0 = time.time()
    if a[0] == 'blender':
        code = open(a[1], encoding='utf-8').read()
        if len(a) > 2:
            code = a[2] + '\n' + code
        print(blender(code))
    elif a[0] == 'code':
        print(blender(a[1]))
    elif a[0] == 'bash':
        print(bash(a[1]))
    elif a[0] == 'fetch':
        print('fetched', fetch(a[1], a[2]), 'bytes ->', a[2])
    elif a[0] == 'put':
        print('put', put(a[1], a[2]), 'bytes ->', a[2])
    print('[%.1fs]' % (time.time() - t0), file=sys.stderr)
