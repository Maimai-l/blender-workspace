# Blender 工作区说明

## 约定
- 工作文件存到 `C:\Users\blender\Documents\`，保存时写绝对路径。
- MCP 传输通道有额度：`look` 默认 `max_size=512`，看细节用 768，最终图用 960。

## 环境（2026-10 实测）
- 用户电脑：Windows，CPU 为 i7-14700KF，显卡为 RTX 5070 Ti，有 C:、D: 两个盘。
- Blender 5.2.3 LTS（Python 3.13），装在 `D:\Program Files\Blender Foundation\Blender 5.2`，这也是脚本里 `os.getcwd()` 的结果，所以相对路径会落到安装目录。
- 用户目录是 `C:\Users\blender`，下面有 `Documents`、`Desktop`、`Downloads`、`OneDrive`。`Documents` 没有被 OneDrive 接管。临时目录是 `C:\Users\blender\AppData\Local\Temp`。
- 渲染引擎的标识符是 `BLENDER_EEVEE`、`BLENDER_WORKBENCH`、`CYCLES`，默认用 EEVEE。EEVEE 渲染 1080p 的 50% 不到 1 秒。
- Cycles 能用 OPTIX 或 CUDA 调用显卡，但偏好设置里计算设备是"无"（`NONE`），场景也设成 CPU。要用 GPU 渲染必须改偏好设置，改之前先问用户。
- MCP 插件 1.8：资源库（Poly Haven、Sketchfab、Poly Pizza）和 3D 生成全部关闭，数据收集也关闭。
- Blender 和 Claude 的沙箱不共享文件系统。MCP 地址来自 `.mcp.json` 里的 `BLENDER_MCP_URL`，断线重连不会清掉场景。

## 经验
- 改完 `location`、`rotation` 等属性后要先 `view_layer.update()`，`matrix_world` 才会更新。
- 对齐或贴合物体时，用求值后的网格（含修改器）来量尺寸，不要用原始网格。
- 判断颜色看渲染结果，`material` 模式的预览光会把颜色冲淡。
- 最终展示图用 `render.render()` 加 `look(image="Render Result")`，视口里的 `rendered` 截图有噪点。
- 不要靠赋值来试探偏好设置（`bpy.context.preferences`）：赋值会真的改掉设置，而且 Blender 退出时会自动保存偏好。只读取不改；非要改，先记下原值，用完改回去。
