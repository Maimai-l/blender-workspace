"""make_maa_json.py - MAA custom base schedule (resource/custom_infrast format) from an optimize.py layout.

    python3 -I make_maa_json.py <optimize.json> "<layout label>" <out.json>

Two plans (12-hour shifts); maa-cli ignores "period", so run.ps1 / the task file pick plan_index by time.
Control center, meeting room and office keep their operators; dormitories use MAA's autofill. Drones go to
the trade post with the highest LMD per efficiency (the special-order team). Factory order must match the
in-game tab order: check against Skland after the base is rebuilt (manufacturesInGameOrder in RIIC-Web)."""
import json
import sys
from pathlib import Path

PRODUCT = {'gold': 'Pure Gold', 'battle_record': 'Battle Record', 'originium': 'Originium Shard'}
PERIODS = [[['00:00', '11:59']], [['12:00', '23:59']]]


def main(opt_path, label, out_path):
    d = json.loads(Path(opt_path).read_text(encoding='utf-8'))
    lay = next(x for x in d['layouts'] if x['label'] == label)
    bp = {r['id']: r for r in lay['blueprint']['rooms']}
    plans = []
    for i, s in enumerate(lay['shifts']):
        a = s['assignment']
        trades = sorted(k for k in a if k.startswith('trade_'))
        manus = sorted(k for k in a if k.startswith('manu_'))
        powers = sorted(k for k in a if k.startswith('power_'))
        best = max(trades, key=lambda k: s['rooms'][k].get('per_eff', 0))
        plans.append({
            'name': f'班次{"AB"[i]}',
            'description': f"{label}；评估器日产（本班 24h 口径）龙门币 {s['daily']['lmd']:,.0f}",
            'period': PERIODS[i],
            'drones': {'enable': True, 'room': 'trading', 'index': trades.index(best) + 1, 'order': 'pre'},
            'rooms': {
                'control': [{'operators': a['control']}],
                'meeting': [{'operators': a['meeting']}],
                'hire': [{'operators': a['office']}],
                'trading': [{'operators': a[k], 'sort': False} for k in trades],
                'manufacture': [{'operators': a[k], 'product': PRODUCT[bp[k]['product']['factory']['recipe']]} for k in manus],
                'power': [{'operators': a[k]} for k in powers],
                'dormitory': [{'autofill': True} for _ in range(4)],
            },
        })
    out = {'title': f'{label}（两班）', 'description': '由 arknights/analysis 生成：RIIC 评估器打分的本地搜索结果', 'plans': plans}
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(out_path)


if __name__ == '__main__':
    main(*sys.argv[1:4])
