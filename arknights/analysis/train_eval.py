"""train_eval.py - daily gain of training candidates in the recommended layout, scored by RIIC's evaluator
(one optimized shift each, same procedure as optimize.py). Costs come from training.py."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import infra_model as M  # noqa: E402
import optimize as O  # noqa: E402
import training as T  # noqa: E402

LAYOUT = ('333 · 2 赤金 1 经验', [3, 3, 3], [('gold', 3), ('gold', 3), ('exp', 3)], 3, None)
TOP = ['但书 → 精二', '孑 → 精一', '八幡海铃 → 精二', '摩根 + 戴菲恩 → 精二', '绮良 + 图耶 → 精二', '泡泡精一 + 火神精二', '苍苔 → 精二']


def main(inp, kb, out):
    M.load_kb(kb)
    acc = O.account(inp)
    cur, fixed, dorms = O.current_eval(acc)
    lay = LAYOUT[:4] + (dorms,)
    base = O.plan_shift(acc, lay, fixed, set())[1]
    planner = json.loads(Path(T.PLANNER).read_text(encoding='utf-8'))
    items = {i['id']: int(i['count']) for i in acc.raw['cultivate_items']}
    rows = []
    for label, changes in T.CANDIDATES:
        if label not in TOP:
            continue
        lmd, exp, need, missing = T.cost(acc, changes, planner, items)
        p = copy.deepcopy(acc)
        for n, e in changes:
            if p.ops[n]['elite'] < e:
                p.ops[n]['elite'], p.ops[n]['level'] = e, 1
        d = O.plan_shift(p, lay, fixed, set())[1]
        gain = d['lmd'] - base['lmd']
        rows.append({'label': label, 'status': '、'.join(f"{n} 精{acc.ops[n]['elite']} {acc.ops[n]['level']}级" for n, _ in changes),
                     'lmd_cost': lmd, 'exp_cost': exp, 'materials': need, 'missing': missing,
                     'gain_lmd': gain, 'gain_gold_net': d['gold_net'] - base['gold_net'], 'gain_exp': d['exp'] - base['exp'],
                     'payback_days': (lmd + exp) / gain if gain > 50 else None})
        print(f"{label}: 日增龙门币 {gain:+,.0f}（成本 龙门币 {lmd:,} 经验 {exp:,}，回本 {rows[-1]['payback_days'] and round(rows[-1]['payback_days'])} 天） 缺 {missing}", flush=True)
    rows.sort(key=lambda r: (r['payback_days'] is None, r['payback_days'] or 0))
    Path(out).write_text(json.dumps({'base_lmd': base['lmd'], 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main(*sys.argv[1:4])
