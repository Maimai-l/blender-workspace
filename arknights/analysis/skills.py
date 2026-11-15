"""Parse RIIC-knowledge's generated per-facility skill pages (docs/2-干员技能/技能-*.md) into records.

Each record: operator, rarity, unlock (('elite', n) or ('level', n) or ('init', 0)), replaces (skill name or None),
skill name, effect text, tags. Source: RIIC-knowledge (CC BY 4.0), generated from clean game data."""
import re
from pathlib import Path

HEAD = re.compile(r'^### (\S+) ☆(\d) · ')
LINE = re.compile(r'^- \*\*(初始解锁|精英 (\d) (?:解锁|提升)(?:，替换「(.+?)」)?|Lv\.(\d+) (?:解锁|提升)(?:，替换「(.+?)」)?)\*\*「(.+?)」：(.*)$')


def parse(path):
    out, cur = [], None
    for raw in Path(path).read_text(encoding='utf-8').splitlines():
        m = HEAD.match(raw)
        if m:
            cur = (m.group(1), int(m.group(2)))
            continue
        m = LINE.match(raw)
        if not (m and cur):
            continue
        if m.group(1) == '初始解锁':
            unlock, repl = ('init', 0), None
        elif m.group(2):
            unlock, repl = ('elite', int(m.group(2))), m.group(3)
        else:
            unlock, repl = ('level', int(m.group(4))), m.group(5)
        text = m.group(7)
        tags = re.findall(r'〔标签：(.+?)〕', text)
        text = re.sub(r'\s*〔标签：.+?〕', '', text).strip()
        out.append({'op': cur[0], 'rarity': cur[1], 'unlock': unlock, 'replaces': repl, 'name': m.group(6),
                    'text': text, 'tags': tags[0].split('/') if tags else []})
    return out


def active_skills(records, op):
    """Skills an operator has at its current training (op: dict with elite, level). Replaced skills are dropped."""
    have = []
    for r in records:
        kind, n = r['unlock']
        ok = kind == 'init' or (kind == 'elite' and op['elite'] >= n) or (kind == 'level' and (op['elite'] > 0 or op['level'] >= n))
        if ok:
            have.append(r)
    replaced = {r['replaces'] for r in have if r['replaces']}
    return [r for r in have if r['name'] not in replaced]
