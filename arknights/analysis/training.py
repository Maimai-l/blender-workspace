"""training.py - base training list ranked by payback (phase 1, section 4.4).

For each candidate: promote it (or a pair) to the target, re-run the recommended layout with the model in
scenarios.py, and take the change in daily LMD as the gain. Cost = level-up and promotion LMD/EXP (RIIC tables)
plus the promotion materials (RIIC-Web training-planner-data.json, from ArknightsGameData), checked against the
Skland inventory. Payback days = (LMD + EXP) / daily LMD gain, valuing 1 EXP = 1 LMD (36 sanity buys 10k of
either at CE-6 / LS-6, RIIC-knowledge 产出常数表); materials are listed with what is missing, not priced."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import infra_model as M  # noqa: E402
import scenarios as S  # noqa: E402
from training_costs import training_cost  # noqa: E402

PLANNER = '/home/user/riic/RIIC-Web/apps/arknights/src/generated/training-planner-data.json'

# candidates: (label, [(operator, target elite)]) - section 4.4 of the plan plus the prototype's queue
CANDIDATES = [
    ('孑 → 精一', [('孑', 1)]),
    ('但书 → 精二', [('但书', 2)]),
    ('八幡海铃 → 精二', [('八幡海铃', 2)]),
    ('红云 → 精一', [('红云', 1)]),
    ('泡泡 → 精一', [('泡泡', 1)]),
    ('断罪者 → 精一', [('断罪者', 1)]),
    ('绮良 + 图耶 → 精二', [('绮良', 2), ('图耶', 2)]),
    ('苍苔 → 精二', [('苍苔', 2)]),
    ('泡泡精一 + 火神精二', [('泡泡', 1), ('火神', 2)]),
    ('摩根 + 戴菲恩 → 精二', [('摩根', 2), ('戴菲恩', 2)]),
    ('雷狼龙S空爆 → 精二', [('雷狼龙S空爆', 2)]),
    ('焰尾 → 精二', [('焰尾', 2)]),
    ('若叶睦 → 精二', [('若叶睦', 2)]),
    ('乌有 → 精二', [('乌有', 2)]),
    ('森西 → 精二', [('森西', 2)]),
]


def promote(acc, changes):
    a = copy.deepcopy(acc)
    for name, elite in changes:
        if name in a.ops and a.ops[name]['elite'] < elite:
            a.ops[name]['elite'], a.ops[name]['level'] = elite, 1
    return a


def cost(acc, changes, planner, items):
    lmd = exp = 0
    mats = {}
    for name, target in changes:
        o = acc.ops.get(name)
        if not o or o['elite'] >= target:
            continue
        a = training_cost(o['rarity'], target, 1)
        b = training_cost(o['rarity'], o['elite'], o['level'])
        lmd += a[0] - b[0]
        exp += a[1] - b[1]
        phases = planner['operators'].get(o['id'], {}).get('phases', [])
        for ph in range(o['elite'] + 1, target + 1):
            for it in (phases[ph] if ph < len(phases) else []):
                mats[it['id']] = mats.get(it['id'], 0) + it['count']
    names = planner['items']
    missing = {names.get(k, {}).get('name', k): n - items.get(k, 0) for k, n in mats.items() if items.get(k, 0) < n}
    need = {names.get(k, {}).get('name', k): n for k, n in mats.items()}
    return lmd, exp, need, missing


def run(acc, reserved, ctrl, plan):
    label, tl, fs, npw, dorms = plan
    return S.layout(acc, label, tl, fs, npw, dorms, reserved, ctrl)


def main(inp, kb):
    M.load_kb(kb)
    acc = M.Account(inp)
    cur, ctrl = S.current(acc)
    b = acc.raw['building']
    nameof = lambda cid: acc.raw['charInfoMap'][cid]['name']  # noqa: E731
    reserved = set(ctrl) | {nameof(c['charId']) for c in b['meeting']['chars'] + b['hire']['chars']}
    planner = json.loads(Path(PLANNER).read_text(encoding='utf-8'))
    items = {i['id']: int(i['count']) for i in acc.raw['cultivate_items']}
    plans = {
        '333': ('333 · 2 赤金 1 经验', [3, 3, 3], [('gold', 3), ('gold', 3), ('exp', 3)], 3, acc.dorm_levels),
        '243': ('243 · 2 赤金 2 经验', [3, 3], [('gold', 3), ('gold', 3), ('exp', 3), ('exp', 3)], 3, acc.dorm_levels),
    }
    base = {k: run(acc, reserved, ctrl, p) for k, p in plans.items()}
    rows = []
    for label, changes in CANDIDATES:
        status = '、'.join(f"{n} 精{acc.ops[n]['elite']} {acc.ops[n]['level']}级" if n in acc.ops else f'{n} 未拥有' for n, _ in changes)
        if any(n not in acc.ops for n, _ in changes):
            rows.append({'label': label, 'status': status, 'skip': '未拥有'})
            continue
        lmd, exp, need, missing = cost(acc, changes, planner, items)
        if lmd == 0 and exp == 0 and not need:
            rows.append({'label': label, 'status': status, 'skip': '已达标'})
            continue
        p = promote(acc, changes)
        gain = {}
        for k, plan in plans.items():
            r = run(p, reserved, ctrl, plan)
            gain[k] = {'lmd': r['lmd'] - base[k]['lmd'], 'capacity': r['capacity'] - base[k]['capacity'],
                       'gold_net': r['gold_net'] - base[k]['gold_net'], 'exp': r['exp'] - base[k]['exp']}
        g = gain['333']['lmd']
        rows.append({'label': label, 'status': status, 'lmd': lmd, 'exp': exp, 'materials': need, 'missing': missing,
                     'gain': gain, 'payback_days': (lmd + exp) / g if g > 1 else None})
    rows.sort(key=lambda r: (r.get('skip') is not None, r.get('payback_days') is None, r.get('payback_days') or 0))
    return rows, base


if __name__ == '__main__':
    rows, base = main(sys.argv[1], sys.argv[2])
    for r in rows:
        if r.get('skip'):
            print(f"{r['label']}: {r['skip']}（{r['status']}）")
            continue
        g = r['gain']['333']
        pb = f"{r['payback_days']:.0f} 天" if r['payback_days'] else '无龙门币增量'
        print(f"{r['label']}（{r['status']}）: 龙门币 {r['lmd']:,} 经验 {r['exp']:,} | 333 日增龙门币 {g['lmd']:+,.0f} 产能指数 {g['capacity']:+,.0f} | 回本 {pb} | 缺 {r['missing']}")
    if len(sys.argv) > 3:
        Path(sys.argv[3]).write_text(json.dumps({'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
