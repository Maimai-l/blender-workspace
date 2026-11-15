# 基建分析（第一阶段）

账号数据来自 `arknights/skland/sync.mjs` 导出的森空岛数据。电脑上先生成去掉身份信息的 `analysis_input.json`，只含干员、基建、库存，不含 UID 和昵称。这里只放代码，不放账号数据。报告和排班存在电脑的 `D:\Projects\maa-cli\reports\` 与 `config\infrast\`。

| 文件 | 作用 |
|---|---|
| `riic_eval.mjs` | 在本地运行 RIIC 的基建评估器。评估器来自 RIIC-Web 公开仓库的 `apps/arknights/public/wasm`，许可为 PolyForm Noncommercial 1.0.0，个人使用。输入输出格式见 `apps/arknights/src/lib/infra-eval/client.ts` |
| `skills.py` | 解析 RIIC-knowledge 的技能分片 `docs/2-干员技能/技能-*.md`（CC BY 4.0） |
| `infra_model.py` | 规则模型，用来挑候选团队：简单技能、常见条件技能、组合注册表里的组合效率和特殊订单锚点。另含调用评估器的接口和日产换算：评估器的 basis points 以 1000 为 100%，无人机 E = 1 + 发电合计，每天 240E 架 |
| `scenarios.py` | 布局模板：房间等级按 RIIC 的 `layouts/*.json`，其中 342 受电力限制。规则模型选人：组合优先、散件补位、每人只用一次 |
| `optimize.py` | 先用规则模型选出团队，再逐个位置换人，由评估器给房间打分择优；两组 12 小时班次互不重叠。输出各布局的峰值和两班平均 |
| `health.py`, `training_costs.py` | 体检，按 RIIC-Web `account-health-*.ts` 的口径：需求比、库存缺口、产能指数、日净龙门币流、赤金净额。默认初始模组 `uniequip_001` 不计费 |
| `training.py`, `train_eval.py` | 练卡候选。成本：升级和精英化的龙门币、经验，以及精英化材料，材料表来自 RIIC-Web 的 `training-planner-data.json`。日增量：在推荐布局下由评估器计算 |
| `make_maa_json.py` | 把优化结果写成 MAA 自定义基建 JSON（两班，0:00 和 12:00） |
| `report.py` | 生成第一阶段报告 |

运行：在 `/home/user/riic` 下放 RIIC-Web 和 RIIC-knowledge 的克隆，再依次运行 `optimize.py`、`train_eval.py`、`make_maa_json.py`、`report.py`，参数见各文件开头。

## 2026-11-15 结果摘要

- 当前布局是 243，两班平均龙门币 5.45 万/天，日净龙门币流 −2.95 万，也就是缺口在扩大。个人需求比 1.51:1，龙门币缺口 1,587 万。
- 推荐改成 333（2 赤金 1 经验）：7.43 万/天，提升 36%，日净龙门币流 +3.60 万。342 受电力限制只有 6.65 万/天。
- 练卡顺序：孑精一（6 天回本）→ 但书精二（每天 +8,582，缺 3 个辅助双芯片）。其他候选回本都超过 200 天。
- 现有 243 下 MAA 的自动排班已接近最优：评估器算出重排只多约 1,700/天。改建前继续用 MAA 的自动排班。
