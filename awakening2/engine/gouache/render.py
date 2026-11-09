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
SHOTS = {'S01': 's01', 'S11': 's11', 'S16': 's16'}


def run(shot):
    t = time.time()
    mod = importlib.import_module(f'gouache.shots.{SHOTS[shot]}')
    mod.build(os.path.join(BG, shot))
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
