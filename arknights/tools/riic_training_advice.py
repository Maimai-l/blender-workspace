#!/usr/bin/env python3
"""本地练卡建议原型：MAA 干员导出 + RIIC-knowledge 知识库 -> 基建练卡建议。

规则来源（只读，不内置数值）：
  - RIIC-knowledge/docs/3-组合库/{单站组合,跨设施体系}/*.md 的 front matter：组合成员、层级、目标练度
  - RIIC-knowledge/docs/6-专家经验/新手培养.md：入门最低目标
  - RIIC-knowledge/docs/6-专家经验/练卡取向.md：五档取向（必练 / 超级推荐 / 40% 档 / 酌情 / 不推荐）
  - 升级经验与龙门币表移植自 RIIC-Web apps/arknights/src/inventory-estimates.ts（PolyForm Noncommercial 1.0.0），
    原始数据为 gamedata_const.json；只算等级与精英化龙门币，不含精英化材料与技能。
知识库原创内容为 CC BY 4.0，来源：可露希尔基建终端 / RIIC-knowledge（公孙长乐等）。

用法：python3 -I riic_training_advice.py <RIIC-knowledge 目录> <Arknights_OperBox_Export.json> [输出.md]
"""
import json
import re
import sys
from pathlib import Path

# ---- 升级成本（移植自 RIIC-Web inventory-estimates.ts） ----
EXPERIENCE = [[100,117,134,151,168,185,202,219,236,253,270,287,304,321,338,355,372,389,406,423,440,457,474,491,508,525,542,559,574,589,605,621,637,653,669,685,701,716,724,739,749,759,770,783,804,820,836,852,888],[120,172,224,276,328,380,432,484,536,588,640,692,744,796,848,900,952,1004,1056,1108,1160,1212,1264,1316,1368,1420,1472,1524,1576,1628,1706,1784,1862,1940,2018,2096,2174,2252,2330,2408,2584,2760,2936,3112,3288,3464,3640,3816,3992,4168,4344,4520,4696,4890,5326,6019,6312,6505,6838,7391,7657,7823,8089,8355,8621,8887,9153,9419,9605,9951,10448,10945,11442,11939,12436,12933,13430,13927,14549],[191,303,415,527,639,751,863,975,1087,1199,1311,1423,1535,1647,1759,1871,1983,2095,2207,2319,2431,2543,2655,2767,2879,2991,3103,3215,3327,3439,3602,3765,3928,4091,4254,4417,4580,4743,4906,5069,5232,5395,5558,5721,5884,6047,6210,6373,6536,6699,6902,7105,7308,7511,7714,7917,8120,8323,8526,8729,9163,9597,10031,10465,10899,11333,11767,12201,12729,13069,13747,14425,15103,15781,16459,17137,17815,18493,19171,19849,21105,22361,23617,24873,26129,27385,28641,29897,31143]]
LMD = [[30,36,43,50,57,65,73,81,90,99,108,118,128,138,149,160,182,206,231,258,286,315,346,378,411,446,482,520,557,595,635,677,720,764,809,856,904,952,992,1042,1086,1131,1178,1229,1294,1353,1413,1474,1572],[48,71,95,120,146,173,201,231,262,293,326,361,396,432,470,508,548,589,631,675,719,765,811,859,908,958,1010,1062,1116,1171,1245,1322,1400,1480,1562,1645,1731,1817,1906,1996,2171,2349,2531,2717,2907,3100,3298,3499,3705,3914,4127,4344,4565,4807,5294,6049,6413,6681,7098,7753,8116,8378,8752,9132,9518,9909,10306,10709,11027,11533,12224,12926,13639,14363,15097,15843,16599,17367,18303],[76,124,173,225,279,334,392,451,513,577,642,710,780,851,925,1001,1079,1159,1240,1324,1410,1498,1588,1680,1773,1869,1967,2067,2169,2273,2413,2556,2702,2851,3003,3158,3316,3477,3640,3807,3976,4149,4324,4502,4684,4868,5055,5245,5438,5634,5867,6103,6343,6587,6835,7086,7340,7599,7861,8127,8613,9108,9610,10120,10637,11163,11696,12238,12882,13343,14159,14988,15828,16681,17545,18422,19311,20213,21126,22092,23722,25380,27065,28778,30519,32287,34083,35906,37745]]
PROMOTION = [[-1,-1],[-1,-1],[10000,-1],[15000,60000],[20000,120000],[30000,180000]]
MAX_LEVEL = {1: [30], 2: [30], 3: [40, 55], 4: [45, 60, 70], 5: [50, 70, 80], 6: [50, 80, 90]}


def cost_from_zero(rarity, elite, level):
    lmd = exp = 0
    for stage in range(elite + 1):
        levels = (MAX_LEVEL[rarity][stage] if stage < elite else level) - 1
        exp += sum(EXPERIENCE[stage][:levels])
        lmd += sum(LMD[stage][:levels])
        if stage < elite:
            lmd += PROMOTION[rarity - 1][stage]
    return lmd, exp


def upgrade_cost(rarity, cur_elite, cur_level, target_elite):
    """从当前练度到「目标精英阶段 1 级」的龙门币与经验（不含精英化材料）。"""
    if target_elite <= cur_elite:
        return 0, 0
    a = cost_from_zero(rarity, target_elite, 1)
    b = cost_from_zero(rarity, cur_elite, cur_level)
    return a[0] - b[0], a[1] - b[1]


# ---- 读知识库 ----
def parse_target(text):
    text = text.strip()
    if text in ("无要求", "", "—"):
        return None  # 持有即可
    m = re.search(r"精\s*([012零一二])", text)
    if m:
        return {"0": 0, "1": 1, "2": 2, "零": 0, "一": 1, "二": 2}[m.group(1)]
    if re.search(r"\d+\s*级", text):
        return 0
    return None


def load_combos(kb):
    combos = []
    for f in sorted((kb / "docs/3-组合库").glob("*/*.md")):
        if f.parent.name not in ("单站组合", "跨设施体系"):
            continue
        s = f.read_text(encoding="utf-8")
        m = re.match(r"---\n(.*?)\n---", s, re.S)
        if not m:
            continue
        fm = m.group(1)
        prod = re.search(r"^product: \[(.*?)\]", fm, re.M)
        members = []
        for block in re.split(r"\n  - name: ", "\n" + fm.split("members:", 1)[-1])[1:]:
            name = block.split("\n", 1)[0].strip()
            tier = re.search(r"tier: (\S+)", block)
            prom = re.search(r"promotion: (\S+)", block)
            members.append({"name": name, "tier": tier.group(1) if tier else "次级",
                            "target": parse_target(prom.group(1)) if prom else None})
        combos.append({"name": f.stem, "layer": f.parent.name,
                       "product": [p.strip() for p in prod.group(1).split(",")] if prod else [],
                       "members": members})
    return combos


def load_newbie(kb):
    s = (kb / "docs/6-专家经验/新手培养.md").read_text(encoding="utf-8")
    out, section = [], None
    for line in s.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        m = re.match(r"\|\s*([^|]+?)\s*\|\s*(\S+)\s*\|\s*([^|]+?)\s*\|", line)
        if m and section and m.group(1) not in ("干员", "---") and not m.group(1).startswith("-"):
            out.append({"name": m.group(1), "section": section, "target": parse_target(m.group(3)) or 0})
    return out


def load_tiers(kb, known_names, combo_keys=frozenset()):
    """练卡取向：按小节收集出现的干员名，得到 名字 -> 档位。"""
    s = (kb / "docs/6-专家经验/练卡取向.md").read_text(encoding="utf-8")
    order = ["必练必拿", "超级推荐", "练了可以一直用", "酌情考虑", "不推荐"]
    tiers, current = {}, None
    names_sorted = sorted(known_names, key=len, reverse=True)
    for line in s.splitlines():
        if line.startswith("### "):
            current = next((t for t in order if t in line), None)
            continue
        if line.startswith("## "):
            current = None
        if not current:
            continue
        for n in names_sorted:
            if n in line and n not in tiers:
                if n in combo_keys and re.search(r"兼\s*" + re.escape(n), line):
                    continue  # 「兼 X 组成员」只说明该干员的身份，不给整个组合定档
                tiers[n] = current
    return tiers, order


# ---- 评估 ----
def main():
    kb, box_path = Path(sys.argv[1]), Path(sys.argv[2])
    out_path = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    box = {o["name"]: o for o in json.loads(box_path.read_text(encoding="utf-8")) if o.get("own", True)}
    combos, newbie = load_combos(kb), load_newbie(kb)
    combo_keys = {c["name"] for c in combos} | {c["name"].removesuffix("组") for c in combos if len(c["name"]) > 2}
    all_names = {m["name"] for c in combos for m in c["members"]} | {n["name"] for n in newbie} | set(box) | combo_keys
    tiers, tier_order = load_tiers(kb, all_names, combo_keys)

    def status(name, target):
        o = box.get(name)
        if not o:
            return "未拥有", None
        if target is None or o["elite"] >= target:
            return "已达标", o
        return "需练", o

    lines = [f"# 基建练卡建议（本地原型）", "",
             f"干员文件：{box_path.name}，已拥有 {len(box)} 名。规则来自 RIIC-knowledge（公孙长乐等，CC BY 4.0）。", ""]

    # 1. 新手目标
    todo_newbie = []
    for n in newbie:
        st, o = status(n["name"], n["target"])
        if st != "已达标":
            todo_newbie.append((n, st, o))
    lines += ["## 1. 新手最低目标", ""]
    if not todo_newbie:
        lines += ["全部完成。", ""]
    else:
        lines += ["| 干员 | 产线 | 目标 | 现状 | 龙门币 | 经验 |", "|---|---|---|---|---:|---:|"]
        for n, st, o in todo_newbie:
            if o:
                lmd, exp = upgrade_cost(o["rarity"], o["elite"], o["level"], n["target"])
                cur = f"精{o['elite']} {o['level']}级"
            else:
                lmd = exp = 0
                cur = "未拥有（需获取）"
            lines.append(f"| {n['name']} | {n['section']} | 精{n['target']} | {cur} | {lmd:,} | {exp:,} |")
        lines.append("")

    # 2. 组合状态
    rows, recs = [], []
    for c in combos:
        cores = [m for m in c["members"] if m["tier"] == "核心"]
        imps = [m for m in c["members"] if m["tier"] == "重要"]
        core_missing = [m["name"] for m in cores if status(m["name"], m["target"])[0] == "未拥有"]
        core_train = [m for m in cores if status(m["name"], m["target"])[0] == "需练"]
        imp_train = [m for m in imps if status(m["name"], m["target"])[0] == "需练"]
        imp_ready = [m for m in imps if status(m["name"], m["target"])[0] == "已达标"]
        if core_missing:
            state = "缺核心"
        elif core_train:
            state = "持有可启动、练度不足"
        elif imps and not imp_ready and imp_train:
            state = "核心就绪、重要成员未成型"
        elif imps and not imp_ready:
            state = "核心就绪、缺重要成员"
        else:
            state = "已成型"
        rows.append((c, state, core_missing, core_train, imp_train))
        if state in ("持有可启动、练度不足", "核心就绪、重要成员未成型"):
            for m in core_train + (imp_train if not imp_ready else []):
                o = box[m["name"]]
                lmd, exp = upgrade_cost(o["rarity"], o["elite"], o["level"], m["target"])
                recs.append({"name": m["name"], "role": m["tier"], "combo": c["name"], "target": m["target"],
                             "cur": f"精{o['elite']} {o['level']}级", "lmd": lmd, "exp": exp,
                             "gaps": len(core_train) + (0 if imp_ready else len(imp_train)),
                             "tier": tiers.get(m["name"]) or tiers.get(c["name"]) or tiers.get(c["name"].removesuffix("组")) or "未分档"})

    lines += ["## 2. 组合状态", "", "| 组合 | 产物 | 状态 | 缺核心 | 核心待练 | 重要待练 |", "|---|---|---|---|---|---|"]
    rank = {"持有可启动、练度不足": 0, "核心就绪、重要成员未成型": 1, "核心就绪、缺重要成员": 2, "已成型": 3, "缺核心": 4}
    for c, state, miss, ctrain, itrain in sorted(rows, key=lambda r: rank[r[1]]):
        fmt = lambda ms: "、".join(f"{m['name']}→精{m['target']}" for m in ms) or "—"
        lines.append(f"| {c['name']} | {'/'.join(c['product'])} | {state} | {'、'.join(miss) or '—'} | {fmt(ctrain)} | {fmt(itrain)} |")
    lines.append("")

    # 3. 优先级队列：档位 > 离成型还差几人 > 成本
    tier_rank = {t: i for i, t in enumerate(tier_order + ["未分档"])}
    seen, queue = set(), []
    for r in sorted(recs, key=lambda r: (tier_rank[r["tier"]], r["role"] != "核心", r["gaps"], r["lmd"] + r["exp"])):
        if r["name"] in seen or r["tier"] == "不推荐":
            continue
        seen.add(r["name"])
        queue.append(r)
    lines += ["## 3. 练卡优先级队列", "",
              "排序：练卡取向档位 → 核心先于重要 → 离成型差的人数少的先 → 成本低的先。成本只含升级与精英化龙门币、经验，不含精英化材料。", "",
              "| # | 干员 | 档位 | 组合（身份） | 现状 → 目标 | 龙门币 | 经验 |", "|---:|---|---|---|---|---:|---:|"]
    for i, r in enumerate(queue[:15], 1):
        lines.append(f"| {i} | {r['name']} | {r['tier']} | {r['combo']}（{r['role']}） | {r['cur']} → 精{r['target']} | {r['lmd']:,} | {r['exp']:,} |")
    lines.append("")
    text = "\n".join(lines)
    if out_path:
        out_path.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
