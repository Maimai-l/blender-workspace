#!/usr/bin/env python3
"""Shared paths for the Xingyuan helper tools.

All tools work under one root folder S (env XY_WORK, default ~/.cache/xingyuan) with this layout:
  ref/xingyuan-images/  -> link to xingyuan/refs/pages   (original reference pages)
  refc/                 -> link to xingyuan/refs/crops   (photo crops used by the comparison views)
  cal/                  -> link to xingyuan/tools/cal    (camera fits)
  crops/ renders/ deliver/                                (outputs, created here)
Running `python3 xyp.py` sets the folder up and prints S (the shell tools use this)."""
import os

TOOLS = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(TOOLS)                       # .../xingyuan
SCRIPTS = os.path.join(PROJ, 'scripts')
LIB = os.path.join(SCRIPTS, 'lib')
REFS = os.path.join(PROJ, 'refs')
PC_ROOT = r'C:\Users\blender\Documents\xingyuan'   # the project folder on the Blender PC
S = os.environ.get('XY_WORK') or os.path.join(os.path.expanduser('~'), '.cache', 'xingyuan')
_CA = '/root/.ccr/ca-bundle.crt'                    # cloud-session proxy CA; ignored where absent
CA = os.environ.get('XY_CA_BUNDLE') or (_CA if os.path.exists(_CA) else None)

def setup():
    for d in ('crops', 'renders', 'deliver', 'ref'):
        os.makedirs(os.path.join(S, d), exist_ok=True)
    for link, target in ((os.path.join(S, 'ref', 'xingyuan-images'), os.path.join(REFS, 'pages')),
                         (os.path.join(S, 'refc'), os.path.join(REFS, 'crops')),
                         (os.path.join(S, 'cal'), os.path.join(TOOLS, 'cal'))):
        if not os.path.lexists(link):
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
    print(S)
