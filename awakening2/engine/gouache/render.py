"""Render shot backgrounds:  python3 -m gouache.render S01 S11 S16 [-j 2]

Writes awakening2/bg/<shot>/ (layer PNGs, flat.png, preview.jpg, layers.json).
"""
import argparse
import importlib
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BG = os.path.join(ROOT, 'bg')
SHOTS = {'S01': 's01', 'S11': 's11', 'S16': 's16', 'S08': 's08', 'S03': 's03', 'S02': 's02', 'S12': 's12',
         'S13': 's13', 'S09': 's09', 'S05': 's05', 'S17': 's17', 'S06': 's06', 'S10': 's10', 'S04': 's04'}


def run(shot):
    """Render into bg/.tmp_<shot>/ and then move the files into bg/<shot>/ one by one
    (os.replace is atomic per file; layers.json goes last), so a consumer never reads
    a half-written layer."""
    import shutil
    t = time.time()
    mod = importlib.import_module(f'gouache.shots.{SHOTS[shot]}')
    tmp = os.path.join(BG, f'.tmp_{shot}')
    dst = os.path.join(BG, shot)
    shutil.rmtree(tmp, ignore_errors=True)
    mod.build(tmp)
    os.makedirs(dst, exist_ok=True)
    names = sorted(os.listdir(tmp), key=lambda n: n == 'layers.json')
    for n in names:
        os.replace(os.path.join(tmp, n), os.path.join(dst, n))
    shutil.rmtree(tmp, ignore_errors=True)
    return shot, round(time.time() - t, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('shots', nargs='*', default=list(SHOTS))
    ap.add_argument('-j', type=int, default=1)
    a = ap.parse_args()
    if a.j > 1 and len(a.shots) > 1:
        with ProcessPoolExecutor(min(a.j, 2)) as ex:
            for shot, dt in ex.map(run, a.shots):
                print(f'{shot}: {dt}s')
    else:
        for s in a.shots:
            shot, dt = run(s)
            print(f'{shot}: {dt}s')


if __name__ == '__main__':
    main()
