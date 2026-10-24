# Blender 工作区说明

## 环境
- Claude 运行在云端沙箱里，Blender 运行在用户自己的 Windows 电脑上（Blender 5.2），两者通过 `.mcp.json` 里的 `blender` MCP 服务器连接。
- 两边的文件系统互不相通。Blender 里的路径都是用户电脑上的 Windows 路径，沙箱里的文件 Blender 看不到，反过来也一样。
- MCP 连接偶尔会断开再重连。重连后先用 `get_scene_info` 确认场景还在，再继续操作。

## 文件保存
- 工作文件默认存到 `C:\Users\blender\Documents\`，文件名用英文小写加下划线，例如 `donut.blend`。
- 渲染图存到同一个文件夹，和对应的 `.blend` 同名，例如 `donut.png`。
- 不覆盖已有文件：遇到同名文件时加序号（`donut_1.blend`），除非用户明确说要覆盖。
- 保存时使用 `bpy.ops.wm.save_as_mainfile(filepath=..., compress=True)`，保存后把完整路径告诉用户。
- 任务完成后主动保存一次，避免 Blender 关掉后丢失工作。

## 截图与传输额度
MCP 传输通道有流量额度，图片和大段输出都会占用额度，所以尽量少传、传小图。
- `look` 的 `max_size` 默认用 **512**。快速确认用 384，需要看清细节时用 768，只有给用户看的最终图才用 960。
- 只想知道位置、尺寸、数量时，用 `get_scene_info` 或打印文字，不要截图。
- 多角度检查放在一次 `look` 里（`mode="angles"`），不要分多次截图。
- 正式渲染先把 `resolution_percentage` 调低（例如 50%）再看 `Render Result`，看完改回原值。
- `execute_blender_code` 只打印需要的信息，不要通过它输出整个文件或大段数据（例如把 `.blend` 转成 base64 传回沙箱）。

## 操作习惯
- 多步骤任务每做完一步就截一张小图检查，有问题先修好再继续。
- 用户没有要求时，不使用外部素材（`search_assets`、`import_asset`、`generate_3d`）。
- 改过的场景或渲染设置（分辨率、采样数等），如果只是为了临时检查，用完要改回去。

## 写 bpy 代码的注意事项
- 着色器节点按类型查找，不要按名称查找（节点名称会随界面语言变化）：
  `next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")`。
- 刚改过 `location`、`rotation` 等属性后，`matrix_world` 还是旧值。要基于它继续计算，先调用 `bpy.context.view_layer.update()`。
- 物体底部要贴地或贴住其他物体时，用求值后的网格（带修改器）来计算高度，细分曲面会让物体略微缩小。
