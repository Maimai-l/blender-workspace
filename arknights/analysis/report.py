"""report.py - phase-1 report (Markdown) from the analysis outputs.

    python3 -I report.py <analysis_input.json> <optimize.json> <train_eval.json> <maa depot json> <infrast json> <out.md>"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import health as H  # noqa: E402

inp, opt_p, tr_p, depot_p, infra_p, out_p = sys.argv[1:7]
d = json.loads(Path(inp).read_text(encoding='utf-8'))
opt = json.loads(Path(opt_p).read_text(encoding='utf-8'))
tr = json.loads(Path(tr_p).read_text(encoding='utf-8'))
depot = json.loads(Path(depot_p).read_text(encoding='utf-8'))['data']
infra = json.loads(Path(infra_p).read_text(encoding='utf-8'))
st = H.stock(d['cultivate_items'])
trn = H.training(d['chars'], d['charInfoMap'])
ratio = trn['ratio']
orundum, originium = depot.get('4003', 0), depot.get('4002', 0)
pulls = (orundum + originium * 180) / 600
short = st['exp'] * ratio - st['lmd']
w = lambda x: f'{x / 10000:,.2f} 万'  # noqa: E731


def flow(lmd, exp):
    return (lmd + H.OFFLINE_LMD) - (exp + H.OFFLINE_EXP) * ratio


cur = opt['current']['peak']
lays = {x['label']: x for x in opt['layouts']}
base243 = lays['243 · 1 赤金 3 经验（现配方）']['avg']
rec = lays['333 · 2 赤金 1 经验']
L = []
add = L.append
add('# 明日方舟 基建优化 第一阶段报告')
add('')
add(f"数据：森空岛（{d['syncTime'][:16].replace('T', ' ')} UTC）+ MAA 仓库识别。产出由 RIIC 评估器计算（RIIC-Web 公开仓库 "
    "`apps/arknights/public/wasm`，本地运行）；团队先按 RIIC-knowledge 的组合与技能规则选出，再由评估器逐个位置换人打分择优。")
add('')
add('## 结论')
add('')
r = rec['avg']
add(f"1. **把基建从 243 改成 333**（拆 1 个制造站、建第 3 个贸易站）：两班平均龙门币 {w(base243['lmd'])} → **{w(r['lmd'])}/天**，"
    f"多 {w(r['lmd'] - base243['lmd'])}（+{(r['lmd'] / base243['lmd'] - 1) * 100:.0f}%）。342 受电力限制只有 {w(lays['342 · 3 赤金 1 经验']['avg']['lmd'])}，不如 333。")
add(f"2. 现在的基建让缺口**每天扩大** {w(-flow(base243['lmd'], base243['exp']))}（经验产得太多、龙门币太少）；改成 333 后变成**每天回补** {w(flow(r['lmd'], r['exp']))}。")
add(f"3. 练卡先做 **孑 → 精一**（6 天回本，只缺 1 个特种芯片），再做 **但书 → 精二**（每天 +{tr['rows'][1]['gain_lmd']:,.0f} 龙门币，14 天回本，缺 3 个辅助双芯片）。其余候选回本都在 200 天以上，暂不练。")
kt = next(x for x in tr['rows'] if x['label'].startswith('绮良'))
add(f"4. 绮良、图耶练到精二：333 下每天只多 {kt['gain_lmd']:,.0f} 龙门币（{kt['payback_days']:.0f} 天回本），342 下没有收益（鸿雪杜林组会挤掉带特殊订单的龙舌兰组）。**不建议**现在为它花 74 万龙门币和精二材料。")
g243 = lays['243 · 2 赤金 2 经验']['avg']
add(f"5. 改建之前可以先做的一步：把 1 个经验站改产赤金。龙门币不变，赤金从每天净耗 {-base243['gold_net']:.0f} 根降到 {-g243['gold_net']:.0f} 根，给改建后的第 3 个贸易站留住库存。只是换产物，不拆建；需要在游戏里手动切换（MAA 不改制造站产物）。")
add('')
add('## 1. 账号体检')
add('')
add('| 项目 | 数值 | 说明 |')
add('|---|---|---|')
add(f"| 龙门币库存 | {st['lmd']:,} | |")
add(f"| 经验库存 | {st['exp']:,} | 作战记录折算（森空岛库存） |")
add(f"| 赤金库存 | {st['gold']:,} | |")
add(f"| 抽卡储备 | 合成玉 {orundum:,} + 源石 {originium} ≈ {pulls:.1f} 抽 | MAA 仓库识别（森空岛库存不含这两项） |")
r6 = trn['by_rarity'][6]; r5 = trn['by_rarity'][5]; r4 = trn['by_rarity'][4]
add(f"| 精二干员 | {trn['e2']} 名（六星 {r6['e2']}/{r6['owned']}、五星 {r5['e2']}/{r5['owned']}、四星 {r4['e2']}/{r4['owned']}） | |")
add(f"| **个人龙门币 : 经验需求比** | **{ratio:.2f} : 1**（只算等级 {trn['level_ratio']:.2f}） | RIIC 口径：精二干员的（升级龙门币＋模组龙门币）÷ 升级经验；模组已开 {r6['modules_open'] + r5['modules_open'] + r4['modules_open']} 个 |")
add(f"| **龙门币缺口** | **{w(short)}** | 经验库存 × 需求比 − 龙门币库存 |")
add(f"| 当前产出（单班峰值） | 龙门币 {w(cur['lmd'])}（其中无人机 {w(cur['drone_lmd'])}）、赤金 {cur['gold_made']:.0f} 根、经验 {w(cur['exp'])} | 森空岛上的实际驻扎，评估器 24h 口径 |")
add(f"| 当前产出（两班平均） | 龙门币 {w(base243['lmd'])}、经验 {w(base243['exp'])} | 同布局按两组 12h 轮换 |")
add(f"| 产能指数 | 峰值 {cur['capacity']:,.0f}（{H.grade(cur['capacity'])}），两班 {base243['capacity']:,.0f}（{H.grade(base243['capacity'])}） | 龙门币×0.5＋赤金价值×0.8＋经验＋合成玉×66.67＋4000 |")
add(f"| 赤金日净额 | {cur['gold_net']:+.0f} 根/天 | 日产 {cur['gold_made']:.0f} ＋ 10 − 消耗 {cur['gold_used']:.0f}；库存可撑约 {st['gold'] / -cur['gold_net']:.0f} 天 |")
add(f"| 日净龙门币流 | {w(flow(base243['lmd'], base243['exp']))} | （基建龙门币＋3 万）−（基建经验＋3 万）× 需求比；为负表示缺口在扩大 |")
add('')
add('说明：RIIC 把每名干员默认自带、不花钱的初始模组（`uniequip_001`）也按一级模组计费，这里没有计入。')
add('')
add('## 2. 布局对比（RIIC 评估器）')
add('')
add('| 方案 | 龙门币/天（两班） | 峰值 | 赤金 产/耗/净 | 经验/天 | 产能指数 | 日净龙门币流 | 补平缺口 |')
add('|---|---:|---:|---|---:|---:|---:|---:|')
for x in opt['layouts']:
    a = x['avg']
    f = flow(a['lmd'], a['exp'])
    days = f'{short / f:,.0f} 天' if f > 0 else '不会'
    add(f"| {x['label']} | {a['lmd']:,.0f} | {x['peak']['lmd']:,.0f} | {a['gold_made']:.0f} / {a['gold_used']:.0f} / {a['gold_net']:+.0f} | {a['exp']:,.0f} | {a['capacity']:,.0f} | {f:+,.0f} | {days} |")
add('')
add('- 两班：两组不重叠的团队各上 12 小时；控制中枢、会客室、办公室保持现在的人。峰值：只看最强的一组。')
add('- 333 的产能指数比 243 低，是因为指数按 0.8 计赤金、按 1 计经验，而 333 少一个制造站；你的瓶颈是龙门币，所以这里以龙门币和日净龙门币流为准。')
add('- 342 只有 2 个发电站，供电不足以让设施满级（RIIC 模板：贸易站 3/2/2 级，制造站 3/3/2/2 级，宿舍 2/1/1/1 级），宿舍降级后轮换也更难。')
add(f"- 333 用 2 赤金 1 经验时赤金每天净耗 {-rec['avg']['gold_net']:.0f} 根，4,399 根大约够 {st['gold'] / -rec['avg']['gold_net']:.0f} 天；降到几百根时把经验站改产赤金（3 赤金时每天净耗 {-lays['333 · 3 赤金']['avg']['gold_net']:.0f} 根，届时再用部分无人机补赤金线配平）。")
add('- 日净龙门币流按 RIIC 的口径把基建经验也乘需求比扣掉，所以少产经验也会让它变好看：同一布局下「3 赤金」比「2 赤金 1 经验」回补得快，是因为少了经验，龙门币并没有多。比较布局请先看龙门币一列。补平天数只算基建，第二阶段的刷图（CE 龙门币本）会把它大幅缩短。')
add('')
add('## 3. 基建练卡清单（在推荐的 333 布局下，评估器计算日增量）')
add('')
add('| 优先 | 干员 | 现状 | 成本（龙门币 / 经验） | 日增龙门币 | 回本 | 还缺的材料 |')
add('|---:|---|---|---|---:|---:|---|')
for i, row in enumerate(tr['rows'], 1):
    pb = f"{row['payback_days']:.0f} 天" if row['payback_days'] else '—'
    miss = '、'.join(f'{k}×{v}' for k, v in row['missing'].items()) or '无'
    add(f"| {i} | {row['label']} | {row['status']} | {row['lmd_cost']:,} / {row['exp_cost']:,} | {row['gain_lmd']:+,.0f} | {pb} | {miss} |")
add('')
add('- 回本天数 =（龙门币＋经验）÷ 日增龙门币（1 经验按 1 龙门币计：CE-6 与 LS-6 都是 36 理智换 1 万）。精英化材料没有折成理智，单列在最后一列。')
add('- 但书精二：3 个辅助双芯片＝6 个辅助芯片组＋3 个芯片助剂，现有芯片组 1、芯片助剂 1；还缺 5 个辅助芯片组（芯片本 PR-C）和 2 个芯片助剂（采购凭证兑换，现有 647）。')
add('- 红云、泡泡、断罪者精一，苍苔、火神精二只提升经验线或赤金线；这两条线现在都富余，龙门币不增加，第一阶段不练。')
add('')
add('## 4. 推荐方案的排班（MAA 自定义基建，两班）')
add('')
for p in infra['plans']:
    rr = p['rooms']
    add(f"**{p['name']}（{p['period'][0][0]}–{p['period'][0][1]}）**：{p['description'].split('；')[1]}")
    add('')
    add('| 设施 | 干员 |')
    add('|---|---|')
    for t in rr['trading']:
        add(f"| 贸易站 | {'、'.join(t['operators'])} |")
    for m in rr['manufacture']:
        add(f"| 制造站（{'赤金' if m['product'] == 'Pure Gold' else '经验'}） | {'、'.join(m['operators'])} |")
    add(f"| 发电站 | {'、'.join(x['operators'][0] for x in rr['power'])} |")
    add(f"| 控制中枢 | {'、'.join(rr['control'][0]['operators'])} |")
    add('')
add('- 无人机全部投给班次里每效率产龙门币最多的贸易站（龙舌兰组或可露希尔所在站）。')
add('- 换班时刻：每天 0:00 换 A 班、12:00 换 B 班，正好对上现在的定时运行；8:00 那次重复套用 A 班，不会打乱。')
add('- 改建完成后，我会按森空岛里制造站的实际顺序重排这份文件，再切换到自定义排班；在那之前继续用 MAA 的自动排班（现有 243 下它已接近最优，评估器算出的重排收益只有约 1,700 龙门币/天）。')
add('')
add('## 需要你确认的事项')
add('')
add('1. **改建 243 → 333**：拆 1 个制造站，在原位建贸易站并升到 3 级。需要 190 架无人机和 1 个基础、3 个进阶、5 个高级加固建材，建材库存为 0，但碳、碳素、碳素组的库存足够在加工站合成（高级加固建材 5 个要 10 个碳素组，现有 6 个，另外 4 个用 12 个碳素合成）。')
add('2. （可选，改建前）**1 个经验站改产赤金**：游戏里手动切换产物，龙门币不变，赤金消耗放缓。')
add('3. **孑 → 精一**：1.5 万龙门币，还缺 1 个特种芯片。')
add('4. **但书 → 精二**：12 万龙门币，先补齐辅助双芯片、异铁块、轻锰矿。')
Path(out_p).write_text('\n'.join(L) + '\n', encoding='utf-8')
print(out_p)
