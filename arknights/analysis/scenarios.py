"""scenarios.py - compare base layouts on the account's real operators (phase 1, section 4.3).

    python3 -I scenarios.py <analysis_input.json> <RIIC-knowledge dir> [--promote 绮良=2,图耶=2] [--json out.json]

Scenarios: the base exactly as stationed now (Skland), then 243 / 333 / 342 with teams picked by the model
(documented combos first, then single operators by skill), and 342 with hypothetical promotions."""
import argparse
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import infra_model as M  # noqa: E402


def trade_output(acc, members, team_skill, anchor, aura, level=3):
    """(LMD/day, gold consumed/day, efficiency %) for one trade room at peak."""
    occ = min(len(members), level)
    eff = 100 + occ + team_skill + aura
    lmd_per, implicit_gold = M.ANCHOR[anchor] if anchor else (M.TRADE_BASE[level], 0)
    lmd = eff / 100 * lmd_per
    gold = max(0.0, (lmd - eff / 100 * implicit_gold) / M.LMD_PER_GOLD)
    return lmd, gold, eff


def best_trade_rooms(acc, levels, used, aura, hongxue=None):
    """One team per trade room, rooms taken from the highest level down. A room of level L seats L operators;
    a combo fits only if it has at most L members (龙舌兰组 needs a level-3 room). Combos are tried in order of
    the LMD they would make in that room and padded with the best single trade operators."""
    cands = M.trade_combos(acc) + ([hongxue] if hongxue else [])
    singles = sorted(((M.trade_skill(acc, name, 3, [name])[0], name) for name in acc.ops if name not in used), reverse=True)
    rooms = []
    for level in sorted(levels, reverse=True):
        fitting = [c for c in cands if len(c[1]) <= level and not any(m in used for m in c[1])]
        fitting.sort(key=lambda c: -trade_output(acc, c[1], c[2], c[3], aura, level)[0])
        if fitting:
            label, members, skill, anchor, _ = fitting[0]
            team, extra = list(members), 0
        else:
            label, team, skill, anchor, extra = '散件', [], 0, None, 0
        for v, name in singles:
            if len(team) == level:
                break
            if name not in used and name not in team and v > 0:
                team.append(name)
                extra += v
        if label == '散件':
            skill, extra = sum(M.trade_skill(acc, t, len(team), team)[0] for t in team), 0
        used.update(team)
        lmd, gold, eff = trade_output(acc, team, skill + extra, anchor, aura, level)
        rooms.append({'label': label, 'level': level, 'team': team, 'eff': eff, 'lmd': lmd, 'gold': gold, 'anchor': anchor})
    return rooms


def best_factory_rooms(acc, specs, used, ctx):
    """specs: [(product, level)], rooms taken from the highest level down; a level-L room seats L operators.
    Per room: the strongest available combo that fits, padded with the best single operators. Combo bonus is
    the combo's documented value; padded members add their own simple skills. Automation teams are never
    padded and are re-evaluated when trimmed to fit a smaller room."""
    rooms = []
    for product, level in sorted(specs, key=lambda s: -s[1]):
        combos = []
        for c in M.factory_combos(acc, product, ctx):
            if any(m in used for m in c[1]):
                continue
            if len(c[1]) > level:
                if c[0] != '自动化组':
                    continue
                c = (c[0], c[1][:level], M.factory_team(acc, c[1][:level], product, ctx), c[3], c[4])
            combos.append(c)
        combo = max(combos, key=lambda c: c[2], default=None)
        singles = sorted(((M.factory_skill(acc, n, product)[0], n) for n in acc.ops if n not in used), reverse=True)
        if combo:
            label, team, bonus = combo[0], list(combo[1]), combo[2]
            if label != '自动化组':
                for v, n in singles:
                    if len(team) == level:
                        break
                    if n not in team:
                        team.append(n)
                        bonus += v
        else:
            label, team = '散件', [n for _, n in singles[:level]]
            bonus = M.factory_team(acc, team, product, ctx)
        used.update(team)
        rooms.append({'label': label, 'product': product, 'level': level, 'team': team, 'eff': 100 + len(team) + bonus})
    return rooms


def best_power(acc, n, used):
    singles = sorted(((M.power_skill(acc, name), name) for name in acc.ops if name not in used), reverse=True)[:n]
    used.update(name for _, name in singles)
    return [{'team': [name], 'skill': v} for v, name in singles]


def summarize(name, trade, factories, powers, best_anchor_lmd):
    E = 1 + sum(0.05 * len(p['team']) + p['skill'] / 100 for p in powers)
    drones = 240 * E
    drone_lmd = drones / 480 * best_anchor_lmd
    lmd = sum(r['lmd'] for r in trade) + drone_lmd
    gold_used = sum(r['gold'] for r in trade) + drone_lmd / M.LMD_PER_GOLD
    gold_made = sum(r['eff'] / 100 * M.GOLD_PER_EFF for r in factories if r['product'] == 'gold')
    exp = sum(r['eff'] / 100 * M.EXP_PER_EFF for r in factories if r['product'] == 'exp')
    gold_value = gold_made * M.LMD_PER_GOLD
    capacity = lmd * 0.5 + gold_value * 0.8 + exp + 4000
    return {'scenario': name, 'lmd': lmd, 'drone_lmd': drone_lmd, 'drones': drones, 'gold_made': gold_made,
            'gold_used': gold_used, 'gold_net': gold_made + 10 - gold_used, 'exp': exp, 'capacity': capacity,
            'trade': trade, 'factories': factories, 'powers': powers}


def current(acc):
    """The base as Skland reports it now."""
    b, nameof = acc.raw['building'], (lambda cid: acc.raw['charInfoMap'][cid]['name'])
    ctrl = [nameof(c['charId']) for c in b['control']['chars']]
    aura = M.control_trade_aura(acc, ctrl)
    trade = []
    for t in b['tradings']:
        team = [nameof(c['charId']) for c in t['chars']]
        combo = next((c for c in M.trade_combos(acc) if set(c[1]) <= set(team)), None)
        if combo:
            extra = sum(M.trade_skill(acc, n, len(team), team)[0] for n in team if n not in combo[1])
            lmd, gold, eff = trade_output(acc, team, combo[2] + extra, combo[3], aura, t['level'])
            label, anchor = combo[0], combo[3]
        else:
            skill = sum(M.trade_skill(acc, n, len(team), team)[0] for n in team)
            lmd, gold, eff = trade_output(acc, team, skill, None, aura, t['level'])
            label, anchor = '散件', None
        trade.append({'label': label, 'level': t['level'], 'team': team, 'eff': eff, 'lmd': lmd, 'gold': gold, 'anchor': anchor})
    factories = []
    for m in b['manufactures']:
        product = {'3': 'exp', '4': 'gold'}.get(m['formulaId'], 'exp')
        team = [nameof(c['charId']) for c in m['chars']]
        ctx = {'powers': len(b['powers']), 'trades': len(b['tradings'])}
        combo = next((c for c in M.factory_combos(acc, product, ctx) if set(c[1]) <= set(team) and not c[0].startswith('自动化')), None)
        skill = (combo[2] + sum(M.factory_skill(acc, n, product)[0] for n in team if n not in combo[1])) if combo \
            else M.factory_team(acc, team, product, ctx)
        factories.append({'label': combo[0] if combo else '散件', 'product': product, 'team': team, 'eff': 100 + len(team) + skill})
    powers = [{'team': [nameof(c['charId']) for c in p['chars']],
               'skill': sum(M.power_skill(acc, nameof(c['charId'])) for c in p['chars'])} for p in b['powers']]
    best = max([r for r in trade], key=lambda r: r['eff'])
    anchor_lmd = M.ANCHOR[best['anchor']][0] if best['anchor'] else M.TRADE_BASE[3]
    return summarize('当前（森空岛实际排班）', trade, factories, powers, anchor_lmd), ctrl


def layout(acc, label, trade_levels, factory_specs, n_power, dorm_levels, reserved, ctrl):
    """trade_levels: [3, 2, 2]; factory_specs: [(product, level)]; dorm_levels: the layout's dormitory levels."""
    acc = copy.copy(acc)
    acc.dorm_levels = list(dorm_levels)
    used = set(reserved)
    aura = M.control_trade_aura(acc, ctrl)
    hong = M.hongxue_combo(acc, sum(1 for p, _ in factory_specs if p == 'gold'))
    trade = best_trade_rooms(acc, trade_levels, used, aura, hong)
    factories = best_factory_rooms(acc, factory_specs, used, {'powers': n_power, 'trades': len(trade_levels)})
    powers = best_power(acc, n_power, used)
    top = max(trade, key=lambda r: r['eff'])
    anchor_lmd = M.ANCHOR[top['anchor']][0] if top['anchor'] else M.TRADE_BASE[top['level']]
    r = summarize(label, trade, factories, powers, anchor_lmd)
    r['dorm_levels'] = list(dorm_levels)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input'); ap.add_argument('kb')
    ap.add_argument('--json')
    a = ap.parse_args()
    M.load_kb(a.kb)
    acc = M.Account(a.input)
    cur, ctrl = current(acc)
    b = acc.raw['building']
    nameof = lambda cid: acc.raw['charInfoMap'][cid]['name']  # noqa: E731
    reserved = set(ctrl) | {nameof(c['charId']) for c in b['meeting']['chars'] + b['hire']['chars']}
    results = [cur]
    # room levels follow RIIC's layout templates (packages/arknights-domain/src/layouts/*.json): 243/333 are
    # fully upgraded on 3 power plants (810 power); 342 has 540 power, so two trade posts and two factories stay
    # at level 2 and the dormitories at 2/1/1/1.
    cur_dorms = acc.dorm_levels
    full, d342 = [3, 3, 3], [2, 1, 1, 1]
    for label, tl, fs, npw, dorms in [
        ('243 · 1 赤金 3 经验（现配方，重排团队）', [3, 3], [('gold', 3), ('exp', 3), ('exp', 3), ('exp', 3)], 3, cur_dorms),
        ('243 · 2 赤金 2 经验', [3, 3], [('gold', 3), ('gold', 3), ('exp', 3), ('exp', 3)], 3, cur_dorms),
        ('333 · 2 赤金 1 经验', full, [('gold', 3), ('gold', 3), ('exp', 3)], 3, cur_dorms),
        ('333 · 3 赤金', full, [('gold', 3), ('gold', 3), ('gold', 3)], 3, cur_dorms),
        ('342 · 3 赤金 1 经验', [3, 2, 2], [('gold', 3), ('gold', 3), ('gold', 2), ('exp', 2)], 2, d342),
        ('342 · 4 赤金', [3, 2, 2], [('gold', 3), ('gold', 3), ('gold', 2), ('gold', 2)], 2, d342),
    ]:
        results.append(layout(acc, label, tl, fs, npw, dorms, reserved, ctrl))
    promo = copy.deepcopy(acc)
    for n in ('绮良', '图耶'):
        if n in promo.ops:
            promo.ops[n]['elite'], promo.ops[n]['level'] = 2, 1
    results.append(layout(promo, '342 · 4 赤金 · 假设绮良、图耶精二（鸿雪杜林组）', [3, 2, 2],
                          [('gold', 3), ('gold', 3), ('gold', 2), ('gold', 2)], 2, d342, reserved, ctrl))
    for r in results:
        print(f"{r['scenario']}: 龙门币 {r['lmd']:,.0f}（无人机 {r['drone_lmd']:,.0f}） 赤金产 {r['gold_made']:.0f} 耗 {r['gold_used']:.0f} "
              f"净 {r['gold_net']:+.0f} 经验 {r['exp']:,.0f} 产能指数 {r['capacity']:,.0f}")
        for t in r['trade']:
            print(f"   贸易 {t['label']} {t['eff']:.0f}% {'、'.join(t['team'])}")
        for f in r['factories']:
            print(f"   制造[{f['product']}] {f['label']} {f['eff']:.0f}% {'、'.join(f['team'])}")
    if a.json:
        Path(a.json).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
