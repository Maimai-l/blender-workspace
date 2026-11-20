#!/usr/bin/env python3
"""Paths shared by the session-side tools (this folder) and the project tools in <project>/tools.

Which project a run belongs to:
  1. XY_PROJECT: a project folder name in the repo (e.g. qiting) or a path;
  2. otherwise the folder of the script being run, when it is <repo>/<project>/... (a project tool);
  3. otherwise the current directory, when it is inside <repo>/<project>.
With no project (e.g. ops work run from the repo root), PROJ, PC_ROOT and LIB are None, and only the
project-free tools work (pcx bash/fetch/put, execc, fetch.py, upload.py, rdefer.py).

  PROJ      <repo>/<project>                    PC_ROOT   D:\\Blender\\Projects\\<project> (XY_PC_ROOT overrides)
  PTOOLS    <repo>/<project>/tools              LIB       <repo>/<project>/scripts/lib
  S         work folder in the session: XY_WORK, default ~/.cache/<project> (~/.cache/pc-tools without one)
  PC_TOOLS  D:\\Projects\\pc-tools on the PC: pc/brelay.py, pc/pack.py and the transfer scratch tmp\\ (pcx.py)

S holds crops/ renders/ deliver/ ref/, plus links refc -> <project>/refs/crops, cal -> <project>/tools/cal and
ref/<project>-images -> <project>/refs/pages where those exist.
`python3 xyp.py` prints S; `--pc-root` prints PC_ROOT; `--project` prints PROJ."""
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TOOLS)
PC_TOOLS = os.environ.get('XY_PC_TOOLS') or 'D:\\Projects\\pc-tools'


def _project_of(path):
    """<repo>/<project> if path lies inside a project folder of the repo, else None."""
    path = os.path.abspath(path)
    while True:
        parent = os.path.dirname(path)
        if parent == path:
            return None
        if parent == REPO:
            name = os.path.basename(path)
            ok = os.path.isdir(path) and path != TOOLS and not name.startswith('.') and name != 'ops'
            return path if ok else None
        path = parent


def _project():
    p = os.environ.get('XY_PROJECT')
    if p:
        p = p if os.path.isabs(p) or os.sep in p else os.path.join(REPO, p)
        if not os.path.isdir(p):
            raise SystemExit('XY_PROJECT: no such project folder: %s' % p)
        return os.path.abspath(p)
    main = sys.argv[0] if sys.argv and sys.argv[0] not in ('', '-c', '-') else None
    return (main and _project_of(os.path.dirname(os.path.abspath(main)))) or _project_of(os.getcwd())


PROJ = _project()
NAME = os.path.basename(PROJ) if PROJ else None
PTOOLS = os.path.join(PROJ, 'tools') if PROJ else None
SCRIPTS = os.path.join(PROJ, 'scripts') if PROJ else None
LIB = os.path.join(SCRIPTS, 'lib') if PROJ else None
REFS = os.path.join(PROJ, 'refs') if PROJ else None
# Projects live under D:\Blender\Projects (C: is the system drive). The older projects were moved there on
# 2026-11-11; their old C:\Users\blender\Documents\<project> paths are junctions to the new folders.
PC_ROOT = os.environ.get('XY_PC_ROOT') or ('D:\\Blender\\Projects\\' + NAME if NAME else None)
S = os.environ.get('XY_WORK') or os.path.join(os.path.expanduser('~'), '.cache', NAME or 'pc-tools')
_CA = '/root/.ccr/ca-bundle.crt'                    # cloud-session proxy CA; ignored where absent
CA = os.environ.get('XY_CA_BUNDLE') or (_CA if os.path.exists(_CA) else None)


def need_project(what='this tool'):
    """Stop with a clear message when a project is required but none was found."""
    if not PROJ:
        raise SystemExit('%s needs a project: run it from <repo>/<project>, or set XY_PROJECT=<project>' % what)
    return PROJ


def setup():
    for d in ('crops', 'renders', 'deliver', 'ref'):
        os.makedirs(os.path.join(S, d), exist_ok=True)
    if PROJ:
        for link, target in ((os.path.join(S, 'refc'), os.path.join(REFS, 'crops')),
                             (os.path.join(S, 'cal'), os.path.join(PTOOLS, 'cal')),
                             (os.path.join(S, 'ref', NAME + '-images'), os.path.join(REFS, 'pages'))):
            if os.path.isdir(target) and not os.path.lexists(link):
                os.symlink(target, link)
    return S


def font(path, size):
    """ImageFont.truetype with a fallback when the font file is missing on this machine."""
    from PIL import ImageFont
    for p in (path, '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if p and os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


setup()

if __name__ == '__main__':
    if '--pc-root' in sys.argv:
        print(PC_ROOT or need_project('--pc-root'))
    elif '--project' in sys.argv:
        print(PROJ or need_project('--project'))
    else:
        print(S)
