# Blender 工作区说明

## 约定
- 工作文件存到 `C:\Users\blender\Documents\`，保存时写绝对路径（Blender 的工作目录是安装目录）。
- MCP 传输通道有额度：`look` 默认 `max_size=512`，看细节用 768，最终图用 960。

## 环境
- Blender 跑在用户的 Windows 电脑上，和 Claude 的沙箱不共享文件系统。
- MCP 断线重连不会清掉场景，接着做即可。

## 经验
- 改完 `location`、`rotation` 等属性后要先 `view_layer.update()`，`matrix_world` 才会更新。
- 对齐或贴合物体时，用求值后的网格（含修改器）来量尺寸，不要用原始网格。
- 判断颜色看渲染结果，`material` 模式的预览光会把颜色冲淡。
- 最终展示图用 `render.render()` 加 `look(image="Render Result")`，视口里的 `rendered` 截图有噪点。
