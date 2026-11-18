"""Runs ON THE PC (any Python 3). Fetch prts.plus copilots for a side story's EX/S stages and match them against the account box (Skland export). Output: state\\copilot_match.json; rank with copilot_rank.py. Edit STAGES for a new event."""
import json, sys, time, urllib.request, urllib.parse
E = "D:\\Projects\\maa-cli\\export\\"
OUT = "D:\\Projects\\maa-cli\\state\\copilot_match.json"
STAGES = [f"act55side_ex{i:02d}" for i in range(1, 9)] + [f"act55side_s{i:02d}" for i in range(1, 5)]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=30))

info = json.load(open(E + "skland_info_latest.json", encoding="utf-8"))["data"]
names = {k: v["name"] for k, v in info["charInfoMap"].items()}
eqmap = info.get("equipmentInfoMap", {})
box = {}
for c in info["chars"]:
    box[names.get(c["charId"], c["charId"])] = c
LETTER = {1: "X", 2: "Y", 3: "A", 4: "D"}

def check(op):
    """None if the account meets the requirement, else a short reason."""
    n = op["name"]
    c = box.get(n)
    if c is None:
        return "未拥有"
    r = op.get("requirements") or {}
    why = []
    el, lv = r.get("elite", 0), r.get("level", 0)
    if (c["evolvePhase"], c["level"]) < (el, lv):
        why.append(f"需精{el} {lv}级(有精{c['evolvePhase']} {c['level']})")
    sl = r.get("skill_level", 0)
    sk = op.get("skill", 1)
    if sl:
        have = c["mainSkillLvl"]
        if have == 7 and len(c["skills"]) >= sk:
            have += c["skills"][sk - 1].get("specializeLevel", 0)
        if have < sl:
            why.append(f"需{sk}技能{sl}级(有{have})")
    if len(c["skills"]) < sk and c["skills"]:   # 没有技能的干员（Lancet-2 等）作业里写的技能编号无所谓
        why.append(f"没有{sk}技能")
    m = r.get("module", -1)
    if m and m > 0:
        ok = False
        for e in c.get("equip", []):
            t = eqmap.get(e["id"], {})
            if t.get("typeIcon", "").upper().endswith("-" + LETTER.get(m, "?")) and e.get("level", 0) >= 1 and not e["id"].startswith("uniequip_001"):
                ok = True
        if not ok:
            why.append(f"需{LETTER.get(m, m)}模组")
    pot = r.get("potentiality", 0)
    if pot and c["potentialRank"] + 1 < pot:
        why.append(f"需潜能{pot}")
    return "；".join(why) or None

res = {}
for st in STAGES:
    items, page = [], 1
    while True:
        q = urllib.parse.urlencode({"level_keyword": st, "page": page, "limit": 50, "order_by": "hot"})
        d = get("https://prts.maa.plus/copilot/query?" + q)["data"]
        items += d["data"]
        if not d["has_next"] or page > 6:
            break
        page += 1
        time.sleep(0.5)
    out = []
    for it in items:
        try:
            ct = json.loads(it["content"])
        except Exception:
            continue
        if ct.get("stage_name") != st:
            continue
        miss = []
        for op in ct.get("opers", []):
            w = check(op)
            if w:
                miss.append({"name": op["name"], "skill": op.get("skill"), "why": w})
        for g in ct.get("groups", []):
            alts = [(op, check(op)) for op in g.get("opers", [])]
            if alts and all(w for _, w in alts):
                miss.append({"name": "组:" + g.get("name", ""), "why": "可选干员都不满足: " + "/".join(op["name"] for op, _ in alts)})
        out.append({
            "id": it["id"], "title": ct.get("doc", {}).get("title", ""), "difficulty": ct.get("difficulty"),
            "views": it["views"], "rating": it["rating_level"], "few_ratings": it["not_enough_rating"],
            "upload": it["upload_time"][:10], "uploader": it["uploader"],
            "opers": [f"{o['name']}{o.get('skill', '')}" for o in ct.get("opers", [])],
            "groups": [g.get("name", "") + ":" + "/".join(o["name"] for o in g.get("opers", [])) for g in ct.get("groups", [])],
            "missing": miss, "details": ct.get("doc", {}).get("details", "")[:300],
        })
    res[st] = out
    print(st, len(items), "fetched,", sum(1 for o in out if not o["missing"]), "fully usable,",
          sum(1 for o in out if len(o["missing"]) == 1), "missing one")
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("eqmap sample", list(eqmap.values())[:1])
