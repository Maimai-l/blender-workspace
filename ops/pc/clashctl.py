"""clashctl.py - control the Clash Verge Rev core (mihomo) from the command line, through its controller pipe
\\\\.\\pipe\\verge-mihomo (reachable from the blender account; no secret). Runs ON THE PC with any Python 3
(e.g. Blender's bundled one). Standard library only.

    python clashctl.py status                  version, mode, mixed port, selected node of each selector group
    python clashctl.py groups                  selector groups and their nodes
    python clashctl.py test [GROUP]            delay of every node in GROUP (default: the first selector group)
    python clashctl.py best [GROUP]            test, then switch GROUP to the fastest node
    python clashctl.py use GROUP NODE          switch GROUP to NODE
    python clashctl.py mode rule|global|direct switch the core's mode ("direct" = proxy effectively off)
    python clashctl.py check                   can the PC reach GitHub directly and through 127.0.0.1:7897?

Changes apply to the whole PC: the main account's system proxy also points at this core (127.0.0.1:7897).
"""
import json
import sys
import time
import urllib.parse
import urllib.request

PIPE = r'\\.\pipe\verge-mihomo'
TEST_URL = 'https://www.gstatic.com/generate_204'


def api(method, path, body=None, timeout=15):
    data = json.dumps(body).encode() if body is not None else b''
    req = (f'{method} {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n'
           f'Content-Type: application/json\r\nContent-Length: {len(data)}\r\n\r\n').encode() + data
    t0 = time.time()
    while True:
        try:
            f = open(PIPE, 'r+b', buffering=0)
            break
        except OSError:                       # pipe busy: retry briefly
            if time.time() - t0 > timeout:
                raise
            time.sleep(0.2)
    with f:
        f.write(req)
        raw = b''
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            raw += chunk
    head, _, payload = raw.partition(b'\r\n\r\n')
    status = int(head.split(b' ', 2)[1])
    if b'chunked' in head.lower():           # de-chunk
        out, rest = b'', payload
        while rest:
            size_s, _, rest = rest.partition(b'\r\n')
            size = int(size_s.split(b';')[0] or b'0', 16)
            if size == 0:
                break
            out, rest = out + rest[:size], rest[size + 2:]
        payload = out
    if status >= 400:
        raise SystemExit(f'{method} {path}: HTTP {status} {payload[:200]!r}')
    return json.loads(payload) if payload.strip() else None


def selectors():
    px = api('GET', '/proxies')['proxies']
    return px, [(n, p) for n, p in px.items() if p.get('type') == 'Selector' and n != 'GLOBAL']


def q(s):
    return urllib.parse.quote(s, safe='')


def delays(group):
    px, _ = selectors()
    res = []
    for node in px[group]['all']:
        try:
            d = api('GET', f'/proxies/{q(node)}/delay?timeout=4000&url={q(TEST_URL)}', timeout=10)['delay']
        except SystemExit:
            d = None
        res.append((node, d))
    return res


def main(a):
    cmd = a[0] if a else 'status'
    if cmd == 'status':
        v = api('GET', '/version'); c = api('GET', '/configs')
        print(f"mihomo {v.get('version')}  mode={c.get('mode')}  mixed-port={c.get('mixed-port')}  tun={c.get('tun', {}).get('enable')}")
        _, sel = selectors()
        for n, p in sel:
            print(f'  {n}: {p.get("now")}')
    elif cmd == 'groups':
        _, sel = selectors()
        for n, p in sel:
            print(f'{n} (now {p.get("now")}): ' + ', '.join(p['all']))
    elif cmd in ('test', 'best'):
        _, sel = selectors()
        group = a[1] if len(a) > 1 else sel[0][0]
        res = delays(group)
        for node, d in sorted(res, key=lambda r: (r[1] is None, r[1] or 0)):
            print(f'  {d if d else "timeout":>8}  {node}')
        ok = [r for r in res if r[1]]
        if cmd == 'best' and ok:
            node = min(ok, key=lambda r: r[1])[0]
            api('PUT', f'/proxies/{q(group)}', {'name': node})
            print(f'{group} -> {node}')
    elif cmd == 'use':
        api('PUT', f'/proxies/{q(a[1])}', {'name': a[2]})
        print(f'{a[1]} -> {a[2]}')
    elif cmd == 'mode':
        api('PATCH', '/configs', {'mode': a[1]})
        print('mode ->', api('GET', '/configs').get('mode'))
    elif cmd == 'check':
        for label, proxy in (('direct', None), ('clash 7897', 'http://127.0.0.1:7897')):
            h = urllib.request.ProxyHandler({'https': proxy} if proxy else {})
            op = urllib.request.build_opener(h)
            t0 = time.time()
            try:
                op.open(urllib.request.Request('https://github.com', headers={'User-Agent': 'clashctl'}), timeout=10).read(1)
                print(f'{label}: github ok {time.time() - t0:.1f}s')
            except Exception as e:
                print(f'{label}: github FAILED ({e.__class__.__name__})')
    else:
        print(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
