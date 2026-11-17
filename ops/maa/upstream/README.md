# MAA 和 maa-cli 官方文档（本地副本）

改托管流程、用 MAA 或 maa-cli 的某个参数或功能之前，先在这里查，不要只看 `--help` 或凭印象。
2026-11-17 的教训：以为 `maa copilot --raid raid` 能让单个作业打突袭，结果 11 个突袭都按普通模式打了；
`maa/protocol/integration.md` 的 Copilot 一节写明 `is_raid` 只在多作业列表（`copilot_list`，带 `stage_name`）里才有。

| 目录 | 来源 | 版本 |
|---|---|---|
| `maa-cli/` | [maa-cli](https://github.com/MaaAssistantArknights/maa-cli) `crates/maa-cli/docs/zh-CN/`：安装、用法、配置、FAQ | 7fedc67 2026-11-08（电脑上装的是 0.7.8） |
| `maa/protocol/` | [MaaAssistantArknights](https://github.com/MaaAssistantArknights/MaaAssistantArknights) `docs/zh-cn/protocol/`：集成接口（各任务参数）、作业格式、任务流程（tasks.json）、回调、保全、肉鸽、基建排班 | d25f7a2 2026-11-16（电脑上的 MaaCore 是 v6.22） |
| `maa/manual/` | 同上 `docs/zh-cn/manual/`：各功能说明（introduction/，含自动战斗 copilot.md）、连接、FAQ | 同上 |

常用位置：
- 任务参数（Fight、Infrast、Copilot、Award 等）：`maa/protocol/integration.md`
- 作业 JSON 格式：`maa/protocol/copilot-schema.md`
- maa-cli 的任务配置写法（variants、condition 等）：`maa-cli/config.md`
- 自定义基建排班文件：`maa/protocol/base-scheduling-schema.md`

两个项目都是 AGPL-3.0 许可，这里原样保留文档供查阅，图片没有一起复制。
更新：`git clone --depth 1` maa-cli；MAA 主仓库用 `--filter=blob:none --sparse` 再 `git sparse-checkout set docs/zh-cn`，复制同样的目录，改上表的版本。
