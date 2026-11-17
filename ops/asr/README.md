# 本地转写台（FireRedASR2S）的改动

转写台在 `D:\asr\FireRedASR2S\asr_gui.py`，用户主账号开机后台运行（`pythonw asr_gui.py --no-browser`，端口 17860），Python 是 `D:\ProgramData\envs\firered`。这里只存我们做的改动，转写台本身不进本仓库。

## 2026-11-17：音乐判断接口 `POST /api/v1/detect`（`detect_endpoint.patch`）
- 用 FireRedVAD 的 AED（`pretrained_models\FireRedVAD\AED`），判断说话、唱歌、音乐各占的比例。
  - 只用 CPU，参数是官方默认值：说话 0.4，唱歌和音乐 0.5，`smooth_window_size=5`。
  - 跑在单独的检测进程里（`asr_gui.py --detector`），第一次调用时启动，空闲时间和识别进程相同（默认 10 分钟）就退出；日志在 `logs\aed_engine.log`。
  - 不启动识别进程，和转写互不影响。
- 三种传法：
  - JSON `{"path": ...}`，只允许本机请求，否则返回 403；
  - 表单字段 `file`；
  - 请求正文就是文件，文件名放在 `X-Filename` 头里。
  - 加 `timestamps=1` 时额外返回 `segments`。
- 返回 `{"dur", "ratio", ["segments"], "elapsed"}`；出错时返回 `{"error"}`。状态码：400（没传文件或格式不支持）、403、404、422（ffmpeg 转换失败）、401（与现有规则相同）、500（检测进程本身出错）。
- `/api/health` 增加 `"aed": true`（AED 模型文件在时）。
- 同步返回，不进任务列表，不写 `gui_outputs`；转格式产生的临时 WAV 和上传的文件在请求结束时删除。
- 实测（2026-11-17，测试实例在 17861 端口）：
  - 1 小时练琴录音 `250621_1900.mp3`：音乐 0.957、说话 0、唱歌 0；首次调用 14.3 秒，之后 12.1 秒，主要花在 ffmpeg 转格式上。
  - 和转写同时跑互不影响；空闲后检测进程会按时退出。
- 原文件备份为 `asr_gui.py.bak-20261117-121234`。改动要在用户重启转写台后才生效。

## 文档
- 给用户看的说明在两份 Claude Docs 里：《Windows 主机维护手册》的「语音识别」页（维护），《FireRedASR2S 本地语音识别使用手册》（https://claude.ai/artifact/HUd8DsbmtfV9Bt48Yw1ErN，用法、接口字段，以及「脚本原文」附录）。
- 附录里 `asr_gui.py` 的原文分 4 个代码块，开头注明版本日期、行数和 SHA256。改了脚本后不要整份重抄：先核对附录的 SHA256 等于改前的文件，再用 `doc_diff_ops.py` 生成只含改动的查找替换，一次 `update` 发出去，最后改附录开头的日期、行数、SHA256。2026-11-17 这样同步了 /api/v1/detect 的改动：11 处替换，约 13k 字符，全文约 2,973 行。
