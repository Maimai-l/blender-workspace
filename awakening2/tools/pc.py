#!/usr/bin/env python3
"""pc.py - render Awakening II on the Windows PC (28 threads) through the exec MCP.

  python3 tools/pc.py sync                      upload code (engine, robot, shots, tools, cues) and unpack
  python3 tools/pc.py bg S01 S02 ...            regenerate background paintings on the PC (detached)
  python3 tools/pc.py render NAME [shots] [--workers 6] [--chunk 24] [--skip]   start detached workers
  python3 tools/pc.py status NAME               frames per shot + worker progress
  python3 tools/pc.py encode VERSION            encode frames on the PC, fetch, mux audio, deliver
  python3 tools/pc.py fetch SID F [F ...]       fetch frames as JPEG into /home/user/aw2_pcframes
  python3 tools/pc.py sh "cmd"                  run a Git Bash command on the PC

PC layout: C:\\Users\\blender\\Documents\\awakening2\\{code, pylib, cache, frames, bg (in code/bg)}.
"""
import os, sys, json, time, subprocess, tarfile, io
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, '/home/user/blender-workspace/qiting/tools')
import pcx

PCROOT = 'C:\\Users\\blender\\Documents\\awakening2'
U = '/c/Users/blender/Documents/awakening2'
PY = '/d/Program Files/Blender Foundation/Blender 5.2/5.2/python/bin/python.exe'
ENV = (f'export PYTHONPATH="C:/Users/blender/Documents/awakening2/pylib" '
       f'AW2_MESH_CACHE="C:/Users/blender/Documents/awakening2/cache/meshes" '
       f'AW2_FRAMES="C:/Users/blender/Documents/awakening2/frames"; PY="{PY}"; ')
SCRATCH = '/tmp/claude-0/-home-user-blender-workspace/025617e1-c491-52ad-8f4f-905a73681e63/scratchpad'


def sh(cmd, timeout_ms=85000):
    return pcx.bash(ENV + cmd, timeout_ms=timeout_ms)


def kill_workers():
    """Stop every render worker and background painter on the PC (by command line)."""
    print(sh('powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:/Users/blender/Documents/awakening2/killw.ps1'))


def sync():
    tgz = os.path.join(SCRATCH, 'aw2code.tgz')
    def filt(ti):
        n = ti.name
        if '__pycache__' in n or n.endswith(('.png', '.jpg', '.mp4', '.wav', '.npz', '.pyc')):
            return None
        return ti
    # ship frozen copies of engine/fx and engine/gouache while helpers edit the live ones
    snaps = {'engine/fx': os.environ.get('AW2_FX_SNAPSHOT'), 'engine/gouache': os.environ.get('AW2_GOUACHE_SNAPSHOT')}
    snaps = {k: v for k, v in snaps.items() if v}
    def filt2(ti):
        for k in snaps:
            if ti.name == k or ti.name.startswith(k + '/'):
                return None
        return filt(ti)
    with tarfile.open(tgz, 'w:gz') as tf:
        for d in ('engine', 'robot', 'shots', 'tools'):
            tf.add(os.path.join(ROOT, d), arcname=d, filter=filt2)
        for k, v in snaps.items():
            tf.add(v, arcname=k, filter=filt)
            print(k, 'from snapshot', v)
        tf.add(os.path.join(ROOT, 'audio', 'cues.json'), arcname='audio/cues.json')
    pcx.put(tgz, PCROOT + '\\aw2code.tgz')
    print(sh(f'cd {U} && mkdir -p code && tar xzf aw2code.tgz -C code && echo synced'))


def bg(shots):
    for s in shots:
        print(sh(f'cd {U}/code/engine && (nohup "$PY" -m gouache.render {s} > {U}/bg_{s}.log 2>&1 &); echo started {s}'))


def render(name, shots=None, workers=7, chunk=48, ss=2, skip=False):
    sys.path.insert(0, os.path.join(ROOT, 'shots'))
    cues = json.load(open(os.path.join(ROOT, 'audio', 'cues.json')))
    chunks = []
    for s in cues['shots']:
        if shots and s['id'] not in shots:
            continue
        n = int(round((s['out'] - s['in']) * 24))
        for a in range(0, n, chunk):
            chunks.append([s['id'], a, min(n, a + chunk)])
    jobs = dict(chunks=chunks, ss=ss, out='C:/Users/blender/Documents/awakening2/frames', skip_existing=skip)
    path = os.path.join(SCRATCH, f'{name}.json')
    json.dump(jobs, open(path, 'w'))
    pcx.put(path, PCROOT + f'\\jobs\\{name}.json')
    cmd = f'cd {U}/code/tools && mkdir -p {U}/frames/_done && rm -f {U}/frames/_done/{name}_*; '
    for w in range(workers):
        cmd += f'(nohup "$PY" pc_worker.py {U}/jobs/{name}.json {w} {workers} > {U}/frames/_done/{name}_{w}.out 2>&1 &); '
    cmd += 'echo launched'
    print(len(chunks), 'chunks over', workers, 'workers')
    print(sh(cmd))


def pipeline(name, bg_shots, workers=5, chunk=48, shots=None, fdir=None):
    """Upload the job file, then (detached on the PC) regenerate backgrounds and start the workers."""
    cues = json.load(open(os.path.join(ROOT, 'audio', 'cues.json')))
    chunks = []
    for s in cues['shots']:
        if shots and s['id'] not in shots:
            continue
        n = int(round((s['out'] - s['in']) * 24))
        for a in range(0, n, chunk):
            chunks.append([s['id'], a, min(n, a + chunk)])
    fdir = fdir or f'frames_{name}'
    jobs = dict(chunks=chunks, ss=2, out=f'C:/Users/blender/Documents/awakening2/{fdir}', contiguous=True)
    path = os.path.join(SCRATCH, f'{name}.json')
    json.dump(jobs, open(path, 'w'))
    pcx.put(path, PCROOT + f'\\jobs\\{name}.json')
    print(sh(f'(nohup bash {U}/code/tools/pc_pipeline.sh {name} {workers} {" ".join(bg_shots)} > {U}/pipeline_{name}.out 2>&1 &); echo started'))


def steal(name, fdir, shots, workers=4, chunk=12):
    """Help a running job: extra workers render the given shots from their END backwards,
    skipping frames that already exist (into the same frames folder)."""
    cues = json.load(open(os.path.join(ROOT, 'audio', 'cues.json')))
    chunks = []
    for s in cues['shots']:
        if s['id'] not in shots:
            continue
        n = int(round((s['out'] - s['in']) * 24))
        cs = [[s['id'], a, min(n, a + chunk)] for a in range(0, n, chunk)]
        chunks += cs[::-1]
    jobs = dict(chunks=chunks, ss=2, out=f'C:/Users/blender/Documents/awakening2/{fdir}', contiguous=False,
                skip_existing=True)
    path = os.path.join(SCRATCH, f'{name}.json')
    json.dump(jobs, open(path, 'w'))
    pcx.put(path, PCROOT + f'\\jobs\\{name}.json')
    print(sh(f'(nohup bash {U}/code/tools/pc_pipeline.sh {name} {workers} > {U}/pipeline_{name}.out 2>&1 &); echo started'))


def status(name):
    print(sh(f'cd {U}/frames && for d in S*; do echo -n "$d:$(ls $d | grep -c png) "; done; echo; '
             f'ls _done | grep -c "{name}_.*done"; tail -q -n 1 _done/{name}_*.log 2>/dev/null; '
             f'grep -l FAILED _done/{name}_*.log 2>/dev/null; tail -n 3 _done/{name}_*.out 2>/dev/null | tail -20'))


def encode(version, crf=19, fdir='frames', overrides=None):
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    cues = json.load(open(os.path.join(ROOT, 'audio', 'cues.json')))
    lines = []
    for s in cues['shots']:
        n = int(round((s['out'] - s['in']) * 24))
        for f in range(n):
            fd = (overrides or {}).get(s['id'], fdir)
            lines.append(f"file 'C:/Users/blender/Documents/awakening2/{fd}/{s['id']}/{s['id']}_{f:04d}.png'\nduration 0.041667\n")
    lst = os.path.join(SCRATCH, f'list_{version}.txt')
    open(lst, 'w').write(''.join(lines))
    pcx.put(lst, PCROOT + f'\\list_{version}.txt')
    ff = '$("$PY" -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")'
    out_pc = f'{U}/deliver/aw2_{version}_video.mp4'
    print(sh(f'mkdir -p {U}/deliver && cd {U} && (nohup {ff} -y -v error -f concat -safe 0 -i list_{version}.txt '
             f'-c:v libx264 -preset slow -crf {crf} -pix_fmt yuv420p -r 24 -vf fps=24 {out_pc} > enc_{version}.log 2>&1 && echo ok > enc_{version}.done &); echo encoding',
             timeout_ms=60000))
    pcx.wait_file(PCROOT + f'\\enc_{version}.done', timeout_s=1800)
    local_v = os.path.join(SCRATCH, f'aw2_{version}_video.mp4')
    pcx.fetch(PCROOT + f'\\deliver\\aw2_{version}_video.mp4', local_v)
    if os.path.getsize(local_v) > 88 * 2 ** 20 and crf < 26:
        # GitHub rejects files over 100 MB: re-encode a little lighter
        print('video', os.path.getsize(local_v) // 2 ** 20, 'MB; re-encoding at crf', crf + 2)
        sh(f'rm -f {U}/enc_{version}.done')
        return encode(version, crf + 2, fdir, overrides)
    mux(local_v, version)


def mux(video, version):
    out = os.path.join(ROOT, 'deliver', f'awakening2_{version}.mp4')
    audio = os.path.join(ROOT, 'audio', 'mix.wav')
    cmd = ['ffmpeg', '-y', '-v', 'error', '-i', video]
    if os.path.exists(audio):
        cmd += ['-i', audio, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '192k', '-shortest']
    cmd += ['-c:v', 'copy', '-movflags', '+faststart', out]
    subprocess.run(cmd, check=True)
    subprocess.run(['cp', out, os.path.join(ROOT, 'deliver', 'awakening2.mp4')], check=True)
    print('delivered', out, os.path.getsize(out) // 1024, 'kB')


def fetch(sid, frames, fdir='frames'):
    os.makedirs('/home/user/aw2_pcframes', exist_ok=True)
    for f in frames:
        f = int(f)
        W_ = 'C:/Users/blender/Documents/awakening2'
        src = f'{W_}/{fdir}/{sid}/{sid}_{f:04d}.png'
        jpg = f'{W_}/tmp/{sid}_{f:04d}.jpg'
        sh(f'mkdir -p {U}/tmp && "$PY" -c "import cv2; cv2.imwrite(r\'{jpg}\', cv2.imread(r\'{src}\'), [cv2.IMWRITE_JPEG_QUALITY, 92])"')
        pcx.fetch(PCROOT + f'\\tmp\\{sid}_{f:04d}.jpg', f'/home/user/aw2_pcframes/{sid}_{f:04d}.jpg')
        print('fetched', sid, f)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'sync':
        sync()
    elif a[0] == 'bg':
        bg(a[1:])
    elif a[0] == 'render':
        name = a[1]
        rest = [x for x in a[2:] if not x.startswith('--')]
        w = int(a[a.index('--workers') + 1]) if '--workers' in a else 7
        c = int(a[a.index('--chunk') + 1]) if '--chunk' in a else 48
        rest = [x for x in rest if not x.isdigit()]
        render(name, rest or None, workers=w, chunk=c, skip='--skip' in a)
    elif a[0] == 'pipeline':
        name = a[1]
        w = int(a[a.index('--workers') + 1]) if '--workers' in a else 5
        bgs = [x for x in a[2:] if x.startswith('S') and len(x) == 3]
        pipeline(name, bgs, workers=w)
    elif a[0] == 'status':
        status(a[1])
    elif a[0] == 'encode':
        # pc.py encode vN FRAMESDIR [S07=frames_x S14=frames_x ...]
        ov = dict(x.split('=') for x in a[3:] if '=' in x)
        encode(a[1], fdir=a[2] if len(a) > 2 else 'frames', overrides=ov)
    elif a[0] == 'pipeline_shots':
        # pc.py pipeline_shots NAME WORKERS S07 S14 ...   (no background regen)
        pipeline(a[1], [], workers=int(a[2]), chunk=48, shots=a[3:])
    elif a[0] == 'fetch':
        # pc.py fetch SID F [F ...] [--dir frames_v2]
        fd = a[a.index('--dir') + 1] if '--dir' in a else 'frames'
        fr = [x for x in a[2:] if x.isdigit()]
        fetch(a[1], fr, fd)
    elif a[0] == 'sh':
        print(sh(a[1]))
    elif a[0] == 'steal':
        # pc.py steal NAME FRAMESDIR WORKERS S09 S12 ...
        steal(a[1], a[2], a[4:], workers=int(a[3]))
    elif a[0] == 'kill':
        kill_workers()
