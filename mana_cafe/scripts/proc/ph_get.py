"""Download Poly Haven assets (CC0) into <project>/assets/ph/<id>/ through the PC's local proxy.

    ph_get.py tex:<id>:<res>[:maps]  model:<id>:<res>  hdri:<id>:<res>  ...

tex maps default: Diffuse,nor_gl,Rough,Displacement  (jpg, Displacement as exr). model: the .blend and its textures.
"""
import json, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = r'D:\Blender\Projects\mana_cafe\assets\ph'
PROXY = urllib.request.ProxyHandler({'http': 'http://127.0.0.1:7897', 'https': 'http://127.0.0.1:7897'})
OP = urllib.request.build_opener(PROXY)
OP.addheaders = [('User-Agent', 'asset-fetch/1.0')]


def get(url, path, size=None):
    if os.path.exists(path) and (size is None or os.path.getsize(path) == size):
        return 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for attempt in range(4):
        try:
            with OP.open(url, timeout=120) as r, open(path + '.part', 'wb') as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            os.replace(path + '.part', path)
            return os.path.getsize(path)
        except Exception as e:
            err = e
            time.sleep(2 + attempt * 3)
    print('FAILED', url, err)
    return 0


def jobs(spec):
    kind, aid, res = spec.split(':')[:3]
    extra = spec.split(':')[3] if spec.count(':') > 2 else ''
    files = json.load(OP.open('https://api.polyhaven.com/files/' + aid, timeout=60))
    d = os.path.join(ROOT, aid)
    out = []
    if kind == 'tex':
        for m in (extra or 'Diffuse,nor_gl,Rough,Displacement').split(','):
            if m not in files:
                print('no map', m, 'for', aid)
                continue
            f = files[m][res]
            fmt = 'exr' if (m == 'Displacement' and 'exr' in f) else ('jpg' if 'jpg' in f else list(f)[0])
            out.append((f[fmt]['url'], os.path.join(d, os.path.basename(f[fmt]['url'])), f[fmt]['size']))
    elif kind == 'model':
        b = files['blend'][res]['blend']
        out.append((b['url'], os.path.join(d, os.path.basename(b['url'])), b['size']))
        for rel, inc in b.get('include', {}).items():
            out.append((inc['url'], os.path.join(d, rel.replace('/', os.sep)), inc['size']))
    elif kind == 'hdri':
        f = files['hdri'][res]['hdr']
        out.append((f['url'], os.path.join(os.path.dirname(ROOT), 'hdri', os.path.basename(f['url'])), f['size']))
    return out


if __name__ == '__main__':
    t0 = time.time()
    allj = []
    with ThreadPoolExecutor(6) as ex:
        for js in ex.map(jobs, sys.argv[1:]):
            allj += js
    print(len(allj), 'files, %.0f MB' % (sum(j[2] for j in allj) / 1e6))
    with ThreadPoolExecutor(6) as ex:
        got = list(ex.map(lambda j: get(*j), allj))
    print('downloaded %.0f MB in %.0fs' % (sum(got) / 1e6, time.time() - t0))
