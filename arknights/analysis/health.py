"""health.py - account health check in RIIC-Web's terms (phase 1, section 4.2), from Skland data.

Ported from RIIC-Web apps/arknights/src/account-health-input.ts / account-health-advice.ts (PolyForm
Noncommercial 1.0.0, personal use):
  demand ratio  = (level LMD + module LMD) / level EXP over all E2 operators of rarity >= 4 (needs >= 3 E2)
  LMD shortfall = EXP stock x ratio - LMD stock
  capacity      = LMD x 0.5 + gold value x 0.8 + EXP + orundum x 66.67 + 4000 (daily; < 90k fail, 90-100k pass,
                  100-110k good, >= 110k excellent)
  net LMD flow  = (base LMD + 30k) - (base EXP + 30k) x ratio  (30k/30k = daily income outside the base)
  gold net      = gold made + 10 - gold consumed
One deviation: the default "original" module (uniequip_001_*) is free in the game and is not charged here;
RIIC charges it as a level-1 module."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from training_costs import training_cost  # noqa: E402

MODULE_LMD = {4: [20000, 20000, 30000], 5: [40000, 50000, 60000], 6: [80000, 100000, 120000]}
EXP_PER_CARD = {'2001': 200, '2002': 400, '2003': 1000, '2004': 2000}
MAX_LEVEL = {1: [30], 2: [30], 3: [40, 55], 4: [45, 60, 70], 5: [50, 70, 80], 6: [50, 80, 90]}
OFFLINE_LMD = OFFLINE_EXP = 30000


def stock(items):
    c = {i['id']: int(i['count']) for i in items}
    exp = sum(c.get(k, 0) * v for k, v in EXP_PER_CARD.items())
    pulls = (c.get('4003', 0) + c.get('4002', 0) * 180) / 600 + c.get('7003', 0) + c.get('7004', 0) * 10
    return {'lmd': c.get('4001', 0), 'exp': exp, 'gold': c.get('3003', 0), 'orundum': c.get('4003', 0),
            'originium': c.get('4002', 0), 'single_tickets': c.get('7003', 0), 'ten_tickets': c.get('7004', 0),
            'pulls': pulls, 'counts': c}


def training(chars, char_info):
    rows = {}
    tot_lmd = tot_exp = tot_mod = 0
    for c in chars:
        r = char_info[c['charId']]['rarity'] + 1
        row = rows.setdefault(r, {'owned': 0, 'e2': 0, 'lmd': 0, 'exp': 0, 'mod_lmd': 0, 'modules_open': 0})
        row['owned'] += 1
        if r < 4 or c['evolvePhase'] != 2:
            continue
        row['e2'] += 1
        lmd, exp = training_cost(r, 2, c['level'])
        mod = sum(sum(MODULE_LMD[r][:min(3, e['level'])]) for e in c.get('equip') or []
                  if not e.get('locked') and e.get('level', 0) >= 1 and not e['id'].startswith('uniequip_001'))
        row['modules_open'] += sum(1 for e in c.get('equip') or [] if not e.get('locked') and not e['id'].startswith('uniequip_001'))
        row['lmd'] += lmd; row['exp'] += exp; row['mod_lmd'] += mod
        tot_lmd += lmd; tot_exp += exp; tot_mod += mod
    e2 = sum(r['e2'] for r in rows.values())
    return {'by_rarity': rows, 'level_ratio': tot_lmd / tot_exp if e2 >= 3 and tot_exp else None,
            'ratio': (tot_lmd + tot_mod) / tot_exp if e2 >= 3 and tot_exp else None,
            'e2': e2, 'lmd': tot_lmd, 'exp': tot_exp, 'mod_lmd': tot_mod}


def grade(score):
    return '不及格' if score < 90000 else '及格' if score < 100000 else '良好' if score < 110000 else '优秀'


def production_view(prod, ratio, st):
    lmd_in, exp_in = prod['lmd'] + OFFLINE_LMD, prod['exp'] + OFFLINE_EXP
    flow = lmd_in - exp_in * ratio
    short = max(0.0, st['exp'] * ratio - st['lmd'])
    return {'scenario': prod['scenario'], 'capacity': prod['capacity'], 'grade': grade(prod['capacity']),
            'lmd': prod['lmd'], 'exp': prod['exp'], 'gold_net': prod['gold_net'], 'lmd_flow': flow,
            'cover_days': short / flow if flow > 0 and short > 0 else None,
            'gold_runway_days': st['gold'] / -prod['gold_net'] if prod['gold_net'] < 0 else None}


if __name__ == '__main__':
    d = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    st = stock(d['cultivate_items'])
    tr = training(d['chars'], d['charInfoMap'])
    print(json.dumps({'stock': {k: v for k, v in st.items() if k != 'counts'}, 'training': tr}, ensure_ascii=False, indent=1))
