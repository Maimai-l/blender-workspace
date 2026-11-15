"""infra_model.py - base production model built only from public rules (RIIC-knowledge, CC BY 4.0).

Daily output = base output per 1.0 efficiency x room efficiency (产出常数表):
  trade Lv3 10265 LMD per 1.0 (1 gold per 500 LMD), gold factory 20 bars per 1.0 (10000 LMD value),
  exp factory 8000 exp per 1.0 (中级作战记录), drones 240*E per day, 480 drones = 1.0 efficiency.
Room efficiency = 100% + 1% per working operator + operator skills + control-center aura.
Operator skills come from the generated skill pages (docs/2-干员技能); simple and common conditional forms are
parsed, the rest count 0 and are listed. Combos whose effect cannot be read off single skills use the team
efficiencies and special-order anchors that RIIC-knowledge documents (组合注册表, 产出常数表).
Peak basis: one team per room for the whole day (a rotation with rested backups keeps most of it)."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import skills  # noqa: E402

TRADE_BASE = {1: 10000, 2: 10141, 3: 10265}
GOLD_PER_EFF, EXP_PER_EFF, LMD_PER_GOLD = 20, 8000, 500
# special-order anchors per 1.0 efficiency (产出常数表 · 特殊组合自有锚点): (LMD, implicit gold)
ANCHOR = {
    'tequila_full': (12739.73, 2328.77),   # 龙舌兰精二 + 巫恋精二 + 裁缝·β
    'closure': (12000, 2000),              # 可露希尔特别订单
    'proviso_e2_lv3': (15929.2, 0),        # 但书精二 · 三级站
    'proviso_e0_lv3': (13097.345, 0),      # 但书精零 · 三级站
}


class Account:
    def __init__(self, path):
        d = json.loads(Path(path).read_text(encoding='utf-8'))
        self.raw = d
        info = d['charInfoMap']
        self.ops = {}
        for c in d['chars']:
            i = info[c['charId']]
            self.ops[i['name']] = {'id': c['charId'], 'name': i['name'], 'elite': c['evolvePhase'], 'level': c['level'],
                                   'rarity': i['rarity'] + 1, 'profession': i['profession']}
        b = d['building']
        self.meeting_lv = b['meeting']['level']
        self.dorm_levels = [x['level'] for x in b['dormitories']]

    def e(self, name):
        o = self.ops.get(name)
        return -1 if o is None else o['elite']

    def has(self, name, elite=0):
        return self.e(name) >= elite


KB = None


def load_kb(kb_dir):
    global KB
    base = Path(kb_dir) / 'docs/2-干员技能'
    KB = {f: skills.parse(base / f'技能-{f}.md') for f in ('贸易站', '制造站', '发电站', '控制中枢')}


def _ops_skills(acc, fac, name):
    o = acc.ops.get(name)
    if not o:
        return []
    return skills.active_skills([r for r in KB[fac] if r['op'] == name], o)


def order_cap_bonus(acc, team):
    """Order-cap increase the team provides ('订单上限+N')."""
    total = 0
    for n in team:
        for r in _ops_skills(acc, '贸易站', n):
            m = re.search(r'订单上限\+(\d+)', r['text'])
            if m and '每级' not in r['text']:
                total += int(m.group(1))
    return total


def trade_skill(acc, name, team_size, team=()):
    """Trade efficiency of one operator (percent) in a team, and the skills not modelled."""
    total, skipped = 0, []
    for r in _ops_skills(acc, '贸易站', name):
        t = r['text']
        m = re.search(r'每间宿舍每级\+(\d+)%获取效率', t)
        if m:
            total += int(m.group(1)) * sum(acc.dorm_levels)
            continue
        m = re.search(r'当前贸易站内干员提升的每个订单上限，提供(\d+)%订单获取效率', t)
        if m:
            total += int(m.group(1)) * order_cap_bonus(acc, [x for x in team if x != name])
            continue
        m = re.search(r'当前订单数与订单上限每差1笔订单，则订单获取效率\+(\d+)%', t)
        if m:   # the gap stays near the cap increase the team adds (orders are delivered as they come)
            total += int(m.group(1)) * order_cap_bonus(acc, [x for x in team if x != name])
            continue
        if re.search(r'订单上限\+\d+$', t) and '效率' not in t:
            continue
        m = re.search(r'订单获取效率\+(\d+)%，会客室每级额外提供(\d+)%获取效率，最多提供(\d+)%', t)
        if m:
            total += min(int(m.group(1)) + int(m.group(2)) * acc.meeting_lv, int(m.group(3)))
            continue
        m = re.search(r'除自身以外每名处于工作状态的干员\+(\d+)%订单获取效率', t)
        if m:
            total += int(m.group(1)) * (team_size - 1)
            continue
        m = re.fullmatch(r'进驻贸易站时，订单获取效率\+(\d+)%(?:，心情每小时消耗[+-][\d.]+)?', t)
        if m:
            total += int(m.group(1))
            continue
        skipped.append(f"{name}「{r['name']}」")
    return total, skipped


AUTOMATION = re.compile(r'其他干员提供的生产力全部归零（不包含根据设施数量提供加成的生产力），每个发电站为当前制造站\+(\d+)%的生产力')


def factory_team(acc, team, product, ctx):
    """Team productivity bonus (percent) for a factory room. ctx: {'powers': n, 'trades': n}.
    Automation operators (温蒂/森蚺/异客...) zero the others' bonuses except facility-count based ones."""
    auto = 0
    per_facility = 0
    normal = 0
    rhine = sum(1 for n in team for r in _ops_skills(acc, '制造站', n) if '莱茵科技' in r['name'])
    for n in team:
        for r in _ops_skills(acc, '制造站', n):
            t = r['text']
            m = AUTOMATION.search(t)
            if m:
                auto += int(m.group(1)) * ctx['powers']
                continue
            m = re.search(r'每个贸易站为当前制造站贵金属类配方的生产力\+(\d+)%', t)
            if m:
                per_facility += int(m.group(1)) * ctx['trades'] if product == 'gold' else 0
                continue
            m = re.search(r'当前制造站内每个莱茵科技类技能为自身\+(\d+)%的生产力', t)
            if m:
                normal += int(m.group(1)) * rhine
                continue
        normal += factory_skill(acc, n, product)[0]
    return (auto + per_facility) if auto else (normal + per_facility)


def factory_skill(acc, name, product):
    """Simple factory productivity of one operator for a product ('gold' / 'exp' / 'shard')."""
    want = {'gold': '贵金属', 'exp': '作战记录', 'shard': '源石'}[product]
    total, skipped = 0, []
    for r in _ops_skills(acc, '制造站', name):
        t = r['text']
        if AUTOMATION.search(t) or '每个贸易站为当前制造站' in t or '莱茵科技类技能为自身' in t:
            continue
        m = re.search(r'最终达到\+(\d+)%', t)
        if m and '生产力' in t:
            total += int(m.group(1))
            continue
        m = re.search(r'每间宿舍每级为贵金属类配方的生产力\+(\d+)%', t)
        if m:
            total += int(m.group(1)) * sum(acc.dorm_levels) if product == 'gold' else 0
            continue
        hits = re.findall(r'(?:(贵金属|作战记录|源石)类配方的)?生产力(?:额外)?\+(\d+)%', t)
        if hits and not re.search(r'每(?:个|名|有)|当前制造站内|若|时，如果', t):
            total += sum(int(v) for k, v in hits if not k or k == want)
            continue
        if re.search(r'仓库容量上限|心情每小时消耗', t) and '生产力' not in t:
            continue
        skipped.append(f"{name}「{r['name']}」")
    return total, skipped


def power_skill(acc, name):
    total = 0
    for r in _ops_skills(acc, '发电站', name):
        m = re.search(r'无人机充能速度\+(\d+)%', r['text'])
        if m:
            total += int(m.group(1))
    return total


def control_trade_aura(acc, names):
    """'所有贸易站订单效率+7%（同种效果取最高）' and similar: the highest one applies."""
    best = 0
    for n in names:
        for r in _ops_skills(acc, '控制中枢', n):
            m = re.search(r'所有贸易站订单效率\+(\d+)%', r['text'])
            if m and '若' not in r['text'] and '当与' not in r['text']:
                best = max(best, int(m.group(1)))
    return best


# ---- documented combos (组合注册表): team skill efficiency, members, control requirement ----
def trade_combos(acc):
    """Candidate trade teams the account can field now: (label, members, team skill %, anchor key, control needs)."""
    c = []
    if acc.has('巫恋', 2) and acc.has('龙舌兰', 2):
        tailor = next((n for n in ('柏喙', '折光', '明椒', '卡夫卡') if acc.has(n, 2)), None)
        if tailor:
            c.append(('龙舌兰组', ['巫恋', '龙舌兰', tailor], 90, 'tequila_full', []))
    if acc.has('能天使', 2) and acc.has('蕾缪安', 2):
        c.append(('能天使组', ['能天使', '蕾缪安'], 80, None, []))
    if acc.has('新约能天使', 2) and acc.has('蕾缪安', 2):
        c.append(('拉特兰', ['新约能天使', '蕾缪安'] + (['空弦'] if acc.has('空弦', 2) else []), 60 + (25 if acc.has('空弦', 2) else 0), None, []))
    if acc.has('焰狐龙梓兰', 2) and acc.has('雷狼龙S空爆', 2):
        c.append(('泡影国狩猎小队', ['焰狐龙梓兰', '雷狼龙S空爆'], 75, None, []))
    if acc.has('摩根', 2) and acc.has('推进之王', 0):
        c.append(('格拉斯哥帮组', ['摩根', '推进之王'], 95 if acc.has('戴菲恩', 2) else 75, None, ['戴菲恩'] if acc.has('戴菲恩', 2) else []))
    if acc.has('灵知', 2) and acc.has('银灰', 2) and acc.has('孑', 1):
        c.append(('喀兰贸易组', ['孑', '银灰'], 85, None, ['灵知']))
    if acc.has('可露希尔', 2):
        c.append(('可露希尔特别订单', ['可露希尔'], 10, 'closure', []))
    if acc.has('但书', 2):
        c.append(('但书', ['但书'], 0, 'proviso_e2_lv3', []))
    if acc.has('伺夜', 2):
        c.append(('叙拉古（伺夜单站）', ['伺夜'], 40 + (5 if acc.has('八幡海铃', 2) else 0), None, ['八幡海铃'] if acc.has('八幡海铃', 2) else []))
    return c


def hongxue_combo(acc, gold_factories):
    """鸿雪杜林组: 4 gold factories -> 160% (three), 2/3 -> 80%/85% (two)."""
    if not (acc.has('鸿雪', 2) and acc.has('绮良', 2) and acc.has('图耶', 2)):
        return None
    if gold_factories >= 4:
        return ('鸿雪杜林组', ['绮良', '鸿雪', '图耶'], 160, None, [])
    if gold_factories >= 2:
        return ('鸿雪杜林组', ['鸿雪', '图耶'], 80 if gold_factories == 2 else 85, None, [])
    return None


def factory_combos(acc, product, ctx=None):
    ctx = ctx or {'powers': 3, 'trades': 2}
    c = []
    auto = [n for n in ('温蒂', '森蚺', '承曦格雷伊', '异客', '掠风') if acc.has(n, 2)]
    if len(auto) >= 2:
        team = auto[:3]
        c.append(('自动化组', team, factory_team(acc, team, product, ctx), None, []))
    if product == 'gold' and acc.has('苍苔', 2):
        mates = [n for n in ('引星棘刺', '砾', '斑点', '夜烟', '温米') if acc.has(n, 0)][:2]
        c.append(('赤金工艺组', ['苍苔'] + mates, 113 if len(mates) == 2 else 45, None, []))
    if acc.has('泡泡', 1) and acc.has('火神', 2):
        c.append(('泡泡火神组', ['泡泡', '火神'], 97, None, []))
    if acc.has('歌蕾蒂娅', 2) and all(acc.has(n) for n in ('乌尔比安', '斯卡蒂', '幽灵鲨', '安哲拉')):
        c.append(('深海猎人组（站一）', ['乌尔比安', '斯卡蒂'], 80, None, ['歌蕾蒂娅']))
        c.append(('深海猎人组（站二）', ['幽灵鲨', '安哲拉'], 80, None, ['歌蕾蒂娅']))
    return c


# ---- RIIC's evaluator (public RIIC-Web repo, apps/arknights/public/wasm) via riic_eval.mjs ----
import subprocess  # noqa: E402

RIIC_WEB = '/home/user/riic/RIIC-Web'


def riic_evaluate(requests):
    out = subprocess.run(['node', str(Path(__file__).parent / 'riic_eval.mjs'), RIIC_WEB],
                         input=json.dumps(requests, ensure_ascii=False), capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def blueprint(trade_levels, factory_specs, n_power, dorm_levels, control_level=5, meeting_level=3, office_level=3):
    """BaseBlueprint in RIIC's format (packages/arknights-domain/src/layouts/*.json)."""
    rooms = [{'id': 'control', 'kind': 'control_center', 'level': control_level}]
    rooms += [{'id': f'trade_{i + 1}', 'kind': 'trade_post', 'level': lv, 'product': {'trade': {'order': 'gold'}}}
              for i, lv in enumerate(trade_levels)]
    rooms += [{'id': f'manu_{i + 1}', 'kind': 'factory', 'level': lv,
               'product': {'factory': {'recipe': {'gold': 'gold', 'exp': 'battle_record', 'shard': 'originium'}[p]}}}
              for i, (p, lv) in enumerate(factory_specs)]
    rooms += [{'id': f'power_{i + 1}', 'kind': 'power_plant', 'level': 3} for i in range(n_power)]
    rooms += [{'id': 'meeting', 'kind': 'meeting_room', 'level': meeting_level}]
    rooms += [{'id': f'dorm_{i + 1}', 'kind': 'dormitory', 'level': lv, 'dorm_beds': 5} for i, lv in enumerate(dorm_levels)]
    rooms += [{'id': 'workshop', 'kind': 'workshop', 'level': 3}, {'id': 'office', 'kind': 'office', 'level': office_level},
              {'id': 'training_room', 'kind': 'training_room', 'level': 3}]
    return {'template': 'custom', 'drone_cap': 250,
            'scenario': {'dorm_occupant_count': 5 * len(dorm_levels)}, 'rooms': rooms}


def eval_request(acc, layout_bp, assignment, hours=24):
    """assignment: {room_id: [operator names]}. Returns a NativeEvalRequestV1."""
    names = sorted({n for team in assignment.values() for n in team})
    ops = []
    for n in names:
        o = acc.ops[n]
        ops.append({'id': o['id'], 'name': n, 'elite': o['elite'], 'level': o['level'], 'own': True,
                    'potential': o.get('potential', 1), 'rarity': o['rarity']})
    return {'schema_version': 1, 'layout': layout_bp, 'scheduled_operators': ops,
            'shifts': [{'duration_hours': hours, 'rooms': [{'room_id': r, 'operators': [{'name': n} for n in team]}
                                                           for r, team in assignment.items()]}]}


def daily_from_eval(resp, layout_bp):
    """Daily output of one 24h evaluation. The evaluator's basis points are per mille (1000 = 100%);
    final efficiency already includes special-order multipliers, so LMD = final x trade base (this matches
    the evaluator's own lmd_per_day). Drones: E = 1 + power total, 240E per day, all into the best trade post."""
    if resp.get('status') != 'ok':
        raise RuntimeError(json.dumps(resp.get('errors'), ensure_ascii=False)[:600])
    levels = {r['id']: r for r in layout_bp['rooms']}
    s = resp['shifts'][0]
    out = {'lmd_rooms': 0.0, 'gold_made': 0.0, 'gold_used': 0.0, 'exp': 0.0, 'rooms': {}}
    best_trade = None
    for room in s['rooms']:
        rid, fac = room['room_id'], room['facility']
        final = room['final_basis_points'] / 1000
        rec = {'facility': fac, 'final': final, 'total': room['total_basis_points'] / 1000, 'status': room['settlement_status']}
        if fac == 'trade_post':
            base = TRADE_BASE[levels[rid]['level']]
            lmd = final * base
            gold_eq = room['gold_equivalent_basis_points'] / 1000 * GOLD_PER_EFF
            out['lmd_rooms'] += lmd
            out['gold_used'] += max(0.0, lmd / LMD_PER_GOLD - gold_eq)
            rec.update(lmd=lmd, per_eff=lmd / final if final else base,
                       gold_ratio=(max(0.0, lmd / LMD_PER_GOLD - gold_eq) / lmd) if lmd else 1 / LMD_PER_GOLD)
            if best_trade is None or rec['per_eff'] > best_trade['per_eff']:
                best_trade = rec
        elif fac == 'factory':
            recipe = levels[rid]['product']['factory']['recipe']
            if recipe == 'gold':
                out['gold_made'] += final * GOLD_PER_EFF
            elif recipe == 'battle_record':
                out['exp'] += final * EXP_PER_EFF
        out['rooms'][rid] = rec
    E = 1 + s['totals'].get('power_basis_points', 0) / 1000
    out['drones'] = 240 * E
    per_eff = best_trade['per_eff'] if best_trade else TRADE_BASE[3]
    out['drone_lmd'] = out['drones'] / 480 * per_eff
    out['gold_used'] += out['drone_lmd'] * (best_trade['gold_ratio'] if best_trade else 1 / LMD_PER_GOLD)
    out['lmd'] = out['lmd_rooms'] + out['drone_lmd']
    out['gold_net'] = out['gold_made'] + 10 - out['gold_used']
    out['capacity'] = out['lmd'] * 0.5 + out['gold_made'] * LMD_PER_GOLD * 0.8 + out['exp'] + 4000
    out['diagnostics'] = resp.get('diagnostics', [])
    return out
