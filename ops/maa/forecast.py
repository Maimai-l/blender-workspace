"""抽卡资源预测与倒推（参考实现）。

按天推演库存：理智 → 1-7 固源岩 → 碎片 → 合成玉；龙门币收支；固定抽卡收入。
输入是一个 JSON（见 forecast_inputs.json），输出：
  1. 到各个检查日累计多出的抽数（固定收入、搓玉稳态、库存土各占多少）
  2. 龙门币最低点，判断它是不是约束
  3. 倒推：库存土要在截止日前搓完，碎片站和开采协力每天至少要多少枚

用法：python3 -I forecast.py forecast_inputs.json
"""
# 规划会话写的参考实现，原文在《MAA 智能刷图调度器设计》的「预测脚本」标签页
# （https://claude.ai/artifact/6c5EDFa1fy8J2jAwc3mP1c#b3d56956-adf1），以那里为准，这里不改动；
# 那边更新后整份替换。每天由 forecast_update.py 刷新输入后运行。
import json
import sys
from datetime import date, timedelta


def simulate(p, days, shard_cap_per_day):
    today = date.fromisoformat(p["today"])
    st = dict(p["stock"])           # lmd, gold, rock, shards
    acc = {"fixed": 0.0, "steady": 0.0, "backlog": 0.0}
    lmd_min = (st["lmd"], today)
    rock_reserve = p["rock_reserved_for_orders"]
    for d in range(days):
        day = today + timedelta(days=d)
        # ---- 固定抽卡收入（玉；源石按 180 玉、凭证按 600 玉计）----
        fx = p["daily_orundum"]
        if day.weekday() == 0:
            fx += p["weekly_annihilation"] + p["weekly_tasks"]
        if day.day == 1:
            m = p["monthly"]
            fx += m["green_shop_orundum"] + 600 * (m["green_shop_vouchers"] + m["signin_vouchers"])
            fx += 180 * m["maintenance_originite"]
        if day.day == 15:
            e = p["monthly"]
            fx += 180 * e["event_originite"] + 600 * e["event_vouchers"]
        acc["fixed"] += fx
        # ---- 理智 → 固源岩 ----
        san = p["sanity_per_day"] - p["annihilation_sanity_per_week"] / 7 - p["order_sanity_per_day"]
        farmed = max(san, 0) / p["sanity_per_rock"]
        # ---- 碎片站：先用当天刷到的土，余量消化库存 ----
        free_rock = max(st["rock"] - rock_reserve, 0)
        steady_sh = min(farmed / 2, shard_cap_per_day)
        backlog_sh = min(free_rock / 2, shard_cap_per_day - steady_sh)
        # 龙门币不够就放慢消化库存
        lmd_in = p["lmd_income_per_day"]
        spend_room = st["lmd"] + lmd_in - p["lmd_floor"] - p["order_lmd_per_day"] - steady_sh * 1600
        backlog_sh = max(min(backlog_sh, spend_room / 1600), 0)
        st["rock"] += farmed - 2 * (steady_sh + backlog_sh)
        st["lmd"] += lmd_in - p["order_lmd_per_day"] - 1600 * (steady_sh + backlog_sh)
        acc["steady"] += 10 * steady_sh
        acc["backlog"] += 10 * backlog_sh
        if st["lmd"] < lmd_min[0]:
            lmd_min = (st["lmd"], day)
    return acc, st, lmd_min


def main():
    p = json.load(open(sys.argv[1], encoding="utf-8"))
    cap = p["shard_cap_per_day"]
    print(f"假设：碎片站产能 {cap} 枚/天，龙门币净收入 {p['lmd_income_per_day']:,}/天，"
          f"订单占理智 {p['order_sanity_per_day']}/天\n")
    print("| 天数 | 固定收入 | 搓玉·稳态 | 搓玉·库存土 | 合计 | 龙门币最低点 | 剩余库存土 |")
    print("|---|---|---|---|---|---|---|")
    for days in p["checkpoints"]:
        acc, st, lmin = simulate(p, days, cap)
        pulls = {k: v / 600 for k, v in acc.items()}
        print(f"| {days} | {pulls['fixed']:.0f} 抽 | {pulls['steady']:.0f} 抽 | {pulls['backlog']:.0f} 抽 | "
              f"{sum(pulls.values()):.0f} 抽 | {lmin[0]/1e4:.0f} 万（{lmin[1]:%m-%d}） | {st['rock']:.0f} |")

    # ---- 倒推：库存土要在 D 天内搓完，碎片站每天至少多少枚 ----
    san = p["sanity_per_day"] - p["annihilation_sanity_per_week"] / 7 - p["order_sanity_per_day"]
    steady = san / p["sanity_per_rock"] / 2
    free_rock = p["stock"]["rock"] - p["rock_reserved_for_orders"]
    print("\n| 截止（天后） | 碎片站至少 枚/天 | 约合倍率（24 枚/天 = 1.0） |")
    print("|---|---|---|")
    for D in p["deadlines"]:
        need = steady + free_rock / 2 / D
        print(f"| {D} | {need:.0f} | {need/24:.2f} |")


if __name__ == "__main__":
    main()
