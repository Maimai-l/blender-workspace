# Blender 工作区说明

## 用户约定
- 工作文件存到 `C:\Users\blender\Documents\`。
- MCP 传输通道有额度。`look` 默认 `max_size=512`，看细节用 768，给用户看的最终图用 960。

## 环境情况
- Blender 5.2 跑在用户的 Windows 电脑上，用户目录是 `C:\Users\blender`。Blender 的当前工作目录是安装目录 `D:\Program Files\...`，所以保存时要写绝对路径。
- Claude 所在的云端沙箱和这台电脑的文件系统不相通。沙箱里的文件 Blender 看不到，Blender 存的文件也不会出现在仓库里。
- MCP 连接会中途断开再重连，场景不会因此丢失（之前遇到过一次，场景完好）。

## 经验
- **改完变换后要先刷新，再读 `matrix_world`**：刚改过 `location` 后，`matrix_world` 还是旧值。之前在这个状态下用 `obj.matrix_world = R @ obj.matrix_world` 转糖霜，结果高度偏移丢失，糖霜掉下去了。先调用 `bpy.context.view_layer.update()`。
- **细分曲面会让物体略微缩小**：底部按原始网格对齐到 z=0 后，加了细分的甜甜圈悬空约 1 毫米。贴地或贴住其他物体时，要用求值后的网格（`evaluated_get` + `to_mesh`）来量高度。
- **`material` 着色模式下颜色偏淡**：预览用的内置 HDRI 会把颜色冲淡。判断颜色要用相机视角的 `rendered` 模式，或者看正式渲染图。之前在 material 模式下把面包色调深了，其实不需要调那么多。
- **`rendered` 视口截图有噪点**：盘子这类大面积浅色区域会有明显颗粒。给用户看的最终图，先 `bpy.ops.render.render()`（EEVEE、50% 分辨率，耗时不到 1 秒），再用 `look(image="Render Result")` 查看。
- **相机距离估算**：50mm 镜头、16:9 画面、45 度俯视时，相机到目标的距离约为物体最大尺寸的 2.4 倍，画面才放得下整个物体（4.8 米宽的盘子用了 11.5 米）。
- **用"删面"做覆盖层，边缘会是台阶状**：从圆环体复制后按高度删面做糖霜，边缘呈锯齿台阶。改成按参数方程直接生成网格（每个角度单独算边界），边缘才平滑。
- **`save_as_mainfile` 保存后 `is_dirty` 仍为 True**：这不代表保存失败，要确认是否存成功，就检查文件是否存在、大小是否正常。
