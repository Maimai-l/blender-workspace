#!/usr/bin/env python3
"""ui.py - look at and tap the LDPlayer screen (instance 0, 1600x900) through exec, for game UI work MAA cannot do.

    python3 -I ui.py shot [name]        screenshot -> scratchpad/<name>.jpg (960x540; prints the path)
    python3 -I ui.py ocr [min_score]    text + coordinates on screen (agent-ocr), one "x,y  text" line each
    python3 -I ui.py tap X Y            tap at screenshot coordinates (960x540 space, scaled to 1600x900)
    python3 -I ui.py swipe X1 Y1 X2 Y2 [ms]
    python3 -I ui.py back               Android back key
Coordinates given here are in the 960x540 screenshot; the device is 1600x900 (x 5/3)."""
import base64
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tools'))  # shared <repo>/tools
import execc  # noqa: E402
import pcx  # noqa: E402

ADB = '/d/leidian/LDPlayer9/adb.exe -s emulator-5554'
PY = '"/d/Program Files/Blender Foundation/Blender 5.2/5.2/python/bin/python.exe"'
PYLIB = 'PYTHONPATH="D:/Blender/Projects/awakening2/pylib"'
OUT = os.environ.get('UI_OUT', '/tmp/claude-0/-home-user-blender-workspace/91c2cead-ddd1-513a-a35d-d0dd6d67ae15/scratchpad/ui')
K = 1600 / 960


def shot(name='screen'):
    pcx.bash(f'{ADB} exec-out screencap -p > /d/Projects/maa-cli/state/ui.png && {PYLIB} {PY} -c "import cv2; '
             f"im=cv2.imread(r'D:\\Projects\\maa-cli\\state\\ui.png'); "
             f"cv2.imwrite(r'D:\\Projects\\maa-cli\\state\\ui.jpg', cv2.resize(im,(960,540),interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 85])\"")
    r = execc.call('Read', {'file_path': 'D:\\Projects\\maa-cli\\state\\ui.jpg'})
    j = json.loads(r['result']['content'][0]['text'])
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name + '.jpg')
    open(p, 'wb').write(base64.b64decode(j['file']['base64']))
    return p


def ocr(min_score=0.5):
    """Text + coordinates of the current screen (agent-ocr on the PC, port 8767), in 960x540 screenshot space.
    A pseudo accessibility tree: one line per text item, `x,y  text`. Starts the OCR server if needed."""
    out = pcx.bash(f'{ADB} exec-out screencap -p > /d/Projects/maa-cli/state/ui.png && AGENT_OCR_PORT=8767 '
                   f'PYTHONIOENCODING=utf-8 /d/Projects/agent-ocr/.venv/Scripts/python.exe /d/Projects/agent-ocr/ocr.py '
                   f'--image D:/Projects/maa-cli/state/ui.png --min-score {min_score} --format text')
    lines = []
    for ln in out.splitlines():
        p = ln.split('\t')
        if len(p) >= 3 and p[1].startswith('['):
            x, y = (int(v) for v in p[1].strip('[]').split(','))
            lines.append(f'{round(x / K):4d},{round(y / K):4d}  {p[2]}')
    return '\n'.join(lines)


def tap(x, y):
    return pcx.bash(f'{ADB} shell input tap {round(float(x) * K)} {round(float(y) * K)} && echo ok')


def swipe(x1, y1, x2, y2, ms=400):
    return pcx.bash(f'{ADB} shell input swipe {round(float(x1) * K)} {round(float(y1) * K)} {round(float(x2) * K)} {round(float(y2) * K)} {int(ms)} && echo ok')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'shot':
        print(shot(a[1] if len(a) > 1 else 'screen'))
    elif a[0] == 'ocr':
        print(ocr(*(float(v) for v in a[1:2])))
    elif a[0] == 'tap':
        print(tap(a[1], a[2]))
    elif a[0] == 'swipe':
        print(swipe(*a[1:5], *(a[5:6] or [400])))
    elif a[0] == 'back':
        print(pcx.bash(f'{ADB} shell input keyevent 4 && echo ok'))
