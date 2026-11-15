"""optimize.py - layout comparison scored by RIIC's evaluator (phase 1, sections 4.2-4.3).

Teams start from the rule-based picks of scenarios.py (combos first), then a local search swaps members with
the best candidates for that facility and keeps a swap only if RIIC's evaluator scores the room higher
(trade: LMD incl. order multiplier; factory: its product; power: charge speed). Two disjoint 12-hour shifts are built
in turn (the second excludes the first's operators), so the average reflects teams that rest half the day.
Control center, meeting room and office keep the operators stationed now.

    python3 -I optimize.py <analysis_input.json> <RIIC-knowledge dir> <out.json>"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import infra_model as M  # noqa: E402
import scenarios as S  # noqa: E402

POOL = 30


def account(path):
    acc = M.Account(path)
    for c in acc.raw['chars']:
        acc.ops[acc.raw['charInfoMap'][c['charId']]['name']]['potential'] = c['potentialRank'] + 1
    return acc


def pools(acc, exclude, trades):
    """Candidate operators per facility, ranked by the rule model (combo members always included)."""
    ex = set(exclude)
    trade = sorted((n for n in acc.ops if n not in ex), key=lambda n: -M.trade_skill(acc, n, 3, [n])[0])[:POOL]
    for c in M.trade_combos(acc) + [x for x in [M.hongxue_combo(acc, 4)] if x]:
        trade += [m for m in c[1] if m not in ex and m not in trade]
    fac = {}
    for p in ('gold', 'exp'):
        lst = sorted((n for n in acc.ops if n not in ex), key=lambda n: -M.factory_skill(acc, n, p)[0])[:POOL]
        for c in M.factory_combos(acc, p, {'powers': 3, 'trades': trades}):
            lst += [m for m in c[1] if m not in ex and m not in lst]
        fac[p] = lst
    power = sorted((n for n in acc.ops if n not in ex), key=lambda n: -M.power_skill(acc, n))[:POOL]
    return {'trade': trade, 'gold': fac['gold'], 'exp': fac['exp'], 'power': power}


def room_score(daily, rid):
    r = daily['rooms'][rid]
    if r['facility'] == 'trade_post':
        return r.get('lmd', 0)
    return r['final']


def local_search(acc, bp, asg, fixed, pool_for, passes=2):
    """Improve each production room in turn by single-member swaps, batch-scored with the evaluator."""
    def evaluate_all(cands):
        return [M.daily_from_eval(r, bp) for r in M.riic_evaluate([M.eval_request(acc, bp, a) for a in cands])]

    cur = evaluate_all([asg])[0]
    for _ in range(passes):
        improved = False
        for rid in [r for r in asg if r not in fixed and not r.startswith('dorm')]:
            used = {n for k, team in asg.items() for n in team}
            trials = []
            for i in range(len(asg[rid])):
                for cand in pool_for(rid):
                    if cand in used:
                        continue
                    a = copy.deepcopy(asg)
                    a[rid][i] = cand
                    trials.append(a)
            if not trials:
                continue
            best_val, best = room_score(cur, rid), None
            for a, d in zip(trials, evaluate_all(trials)):
                v = room_score(d, rid)
                if v > best_val * 1.0005:
                    best_val, best = v, (a, d)
            if best:
                asg, cur = best
                improved = True
        if not improved:
            break
    return asg, cur


def plan_shift(acc, kb_layout, fixed_asg, exclude):
    """One shift: rule-based start, then evaluator local search."""
    label, tl, fs, npw, dorms = kb_layout
    reserved = set(exclude) | {n for t in fixed_asg.values() for n in t}
    ctrl = fixed_asg['control']
    r = S.layout(acc, label, tl, fs, npw, dorms, reserved, ctrl)
    bp = M.blueprint(tl, fs, npw, dorms)
    asg = dict(copy.deepcopy(fixed_asg))
    for i, t in enumerate(sorted(r['trade'], key=lambda x: -x['level'])):
        asg[f'trade_{i + 1}'] = list(t['team'])
    order = sorted(range(len(fs)), key=lambda i: -fs[i][1])
    for room, i in zip(r['factories'], order):
        asg[f'manu_{i + 1}'] = list(room['team'])
    for i, p in enumerate(r['powers']):
        asg[f'power_{i + 1}'] = list(p['team'])
    pl = pools(acc, reserved, len(tl))
    products = {f'manu_{i + 1}': p for i, (p, _) in enumerate(fs)}

    def pool_for(rid):
        if rid.startswith('trade'):
            return pl['trade']
        if rid.startswith('manu'):
            return pl[products[rid]]
        return pl['power']
    asg, daily = local_search(acc, bp, asg, set(fixed_asg), pool_for)
    return asg, daily, bp


def run_layout(acc, kb_layout, fixed_asg, shifts=2):
    exclude, out = set(), []
    for _ in range(shifts):
        asg, daily, bp = plan_shift(acc, kb_layout, fixed_asg, exclude)
        out.append({'assignment': asg, 'daily': {k: v for k, v in daily.items() if k != 'rooms'}, 'rooms': daily['rooms']})
        exclude |= {n for k, t in asg.items() if k not in fixed_asg for n in t}
    keys = ('lmd', 'drone_lmd', 'gold_made', 'gold_used', 'gold_net', 'exp', 'capacity')
    avg = {k: sum(s['daily'][k] for s in out) / len(out) for k in keys}
    return {'label': kb_layout[0], 'peak': out[0]['daily'], 'avg': avg, 'shifts': out, 'blueprint': bp}


def current_eval(acc):
    b, nm = acc.raw['building'], (lambda cid: acc.raw['charInfoMap'][cid]['name'])
    mf = {'3': 'exp', '4': 'gold'}
    tl = [t['level'] for t in b['tradings']]
    fs = [(mf[m['formulaId']], m['level']) for m in b['manufactures']]
    dorms = [d['level'] for d in b['dormitories']]
    bp = M.blueprint(tl, fs, len(b['powers']), dorms, b['control']['level'], b['meeting']['level'], b['hire']['level'])
    asg = {'control': [nm(c['charId']) for c in b['control']['chars']],
           'meeting': [nm(c['charId']) for c in b['meeting']['chars']],
           'office': [nm(c['charId']) for c in b['hire']['chars']]}
    for i, t in enumerate(b['tradings']):
        asg[f'trade_{i + 1}'] = [nm(c['charId']) for c in t['chars']]
    for i, m in enumerate(b['manufactures']):
        asg[f'manu_{i + 1}'] = [nm(c['charId']) for c in m['chars']]
    for i, p in enumerate(b['powers']):
        asg[f'power_{i + 1}'] = [nm(c['charId']) for c in p['chars']]
    d = M.daily_from_eval(M.riic_evaluate([M.eval_request(acc, bp, asg)])[0], bp)
    fixed = {k: asg[k] for k in ('control', 'meeting', 'office')}
    return {'label': '当前（森空岛实际排班）', 'peak': {k: v for k, v in d.items() if k != 'rooms'}, 'rooms': d['rooms'],
            'assignment': asg}, fixed, dorms


def main(inp, kb, out_path):
    M.load_kb(kb)
    acc = account(inp)
    cur, fixed, cur_dorms = current_eval(acc)
    d342 = [2, 1, 1, 1]
    layouts = [
        ('243 · 1 赤金 3 经验（现配方）', [3, 3], [('gold', 3), ('exp', 3), ('exp', 3), ('exp', 3)], 3, cur_dorms),
        ('243 · 2 赤金 2 经验', [3, 3], [('gold', 3), ('gold', 3), ('exp', 3), ('exp', 3)], 3, cur_dorms),
        ('333 · 2 赤金 1 经验', [3, 3, 3], [('gold', 3), ('gold', 3), ('exp', 3)], 3, cur_dorms),
        ('333 · 3 赤金', [3, 3, 3], [('gold', 3), ('gold', 3), ('gold', 3)], 3, cur_dorms),
        ('342 · 3 赤金 1 经验', [3, 2, 2], [('gold', 3), ('gold', 3), ('gold', 2), ('exp', 2)], 2, d342),
        ('342 · 4 赤金', [3, 2, 2], [('gold', 3), ('gold', 3), ('gold', 2), ('gold', 2)], 2, d342),
    ]
    results = {'current': cur, 'layouts': []}
    for lay in layouts:
        res = run_layout(acc, lay, fixed)
        results['layouts'].append(res)
        print(f"{lay[0]}: 峰值 龙门币 {res['peak']['lmd']:,.0f} | 两班平均 龙门币 {res['avg']['lmd']:,.0f} 赤金净 {res['avg']['gold_net']:+.0f} "
              f"经验 {res['avg']['exp']:,.0f} 产能指数 {res['avg']['capacity']:,.0f}", flush=True)
    promo = copy.deepcopy(acc)
    for n in ('绮良', '图耶'):
        promo.ops[n]['elite'], promo.ops[n]['level'] = 2, 1
    res = run_layout(promo, ('342 · 4 赤金 · 假设绮良、图耶精二', [3, 2, 2], [('gold', 3), ('gold', 3), ('gold', 2), ('gold', 2)], 2, d342), fixed)
    results['layouts'].append(res)
    print(f"{res['label']}: 峰值 {res['peak']['lmd']:,.0f} | 两班平均 {res['avg']['lmd']:,.0f} 产能指数 {res['avg']['capacity']:,.0f}")
    c = cur['peak']
    print(f"当前: 龙门币 {c['lmd']:,.0f}（无人机 {c['drone_lmd']:,.0f}） 赤金产 {c['gold_made']:.0f} 净 {c['gold_net']:+.0f} 经验 {c['exp']:,.0f} 产能指数 {c['capacity']:,.0f}")
    Path(out_path).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main(*sys.argv[1:4])
