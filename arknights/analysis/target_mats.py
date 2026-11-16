"""target_mats.py - materials still missing for one operator's training goal, after stock and crafting.

    python3 -I target_mats.py <analysis_input.json> <gamedata dir> <char_id> [mastery skills, e.g. 2,3]

Goal: skill level 7, the next elite promotion (from the current one) up to elite 2, and M3 on the listed skills.
Uses ArknightsGameData (character_table, item_table, building_data) and the de-identified Skland export.
Stock is used first; items of tier 3+ (and 技巧概要·卷3) are crafted from their workshop recipe, dual chips from
the factory recipe (芯片组 x2 + 芯片助剂). Lossy chip-pack conversions (3 other packs -> 1) are not used.
Prints the top-level need / stock and the base items still missing."""
import collections
import json
import sys
from pathlib import Path


def main(inp, gd, cid, mastery='2,3'):
    gd = Path(gd)
    ct = json.loads((gd / 'character_table.json').read_text(encoding='utf-8'))
    it = json.loads((gd / 'item_table.json').read_text(encoding='utf-8'))['items']
    bd = json.loads((gd / 'building_data.json').read_text(encoding='utf-8'))
    d = json.loads(Path(inp).read_text(encoding='utf-8'))
    inv = collections.Counter({x['id']: int(x['count']) for x in d['cultivate_items']})
    me = next(c for c in d['chars'] if c['charId'] == cid)
    name = lambda i: it.get(i, {}).get('name', i)
    c = ct[cid]
    need = collections.Counter()
    for i, s in enumerate(c['allSkillLvlup']):                 # index i: level i+1 -> i+2
        if i + 1 >= me['mainSkillLvl']:
            for x in s['lvlUpCost'] or []:
                need[x['id']] += x['count']
    for ph in range(me['evolvePhase'] + 1, 3):
        for x in c['phases'][ph]['evolveCost'] or []:
            need[x['id']] += x['count']
    for si in [int(v) - 1 for v in mastery.split(',') if v]:
        done = me['skills'][si]['specializeLevel']
        for lv in c['skills'][si]['levelUpCostCond'][done:]:
            for x in lv['levelUpCost'] or []:
                need[x['id']] += x['count']
    recipe = {}
    for f in bd['workshopFormulas'].values():
        if f['itemId'].startswith('32') and f['itemId'].endswith('2'):     # lossy chip-pack conversion
            continue
        recipe[f['itemId']] = {x['id']: x['count'] for x in f['costs']}
    for f in bd['manufactFormulas'].values():
        if f['itemId'].startswith('32') and f['itemId'].endswith('3'):     # dual chips (factory)
            recipe[f['itemId']] = {x['id']: x['count'] for x in f['costs']}

    def tier(i):
        return int(it.get(i, {}).get('rarity', 'TIER_1')[-1])

    stock, base = inv.copy(), collections.Counter()

    def expand(item, n):
        use = min(stock[item], n)
        stock[item] -= use
        n -= use
        if not n:
            return
        r = recipe.get(item)
        if r and (tier(item) >= 3 or item == '3303') and item not in ('3302', '3301'):
            for k, v in r.items():
                expand(k, v * n)
        else:
            base[item] += n

    for k, v in sorted(need.items(), key=lambda kv: -tier(kv[0])):
        expand(k, v)
    print(f"{c['name']}: elite {me['evolvePhase']} lv {me['level']}, skill {me['mainSkillLvl']}, "
          f"masteries {[s['specializeLevel'] for s in me['skills']]}")
    print('need / stock:')
    for k, v in sorted(need.items(), key=lambda kv: -tier(kv[0])):
        print(f'  {name(k)} {v} / {inv[k]}')
    print('still missing after stock and crafting:')
    for k, v in base.items():
        print(f'  {name(k)} ({k}) x{v}')


if __name__ == '__main__':
    main(*sys.argv[1:5])
