"""Contact sheets of render files, made inside Blender (numpy on image pixels)."""
import bpy, os
import numpy as np

def load_rgb(path):
    im = bpy.data.images.load(path, check_existing=False)
    w, h = im.size
    px = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(px)
    arr = px.reshape(h, w, 4)[::-1, :, :3]
    bpy.data.images.remove(im)
    return arr

def sheet(paths, out, cols=3, cell=(640, 360), labels=True):
    rows = (len(paths) + cols - 1) // cols
    cw, ch = cell
    canvas = np.full((rows * ch, cols * cw, 3), 0.18, dtype=np.float32)
    for i, p in enumerate(paths):
        if not os.path.exists(p):
            continue
        a = load_rgb(p)
        h, w = a.shape[:2]
        # nearest resize
        ys = (np.arange(ch) * h / ch).astype(int); xs = (np.arange(cw) * w / cw).astype(int)
        a = a[ys][:, xs]
        r, c = divmod(i, cols)
        canvas[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = a
    H, W = canvas.shape[:2]
    im = bpy.data.images.new('sheet', W, H, alpha=False)
    rgba = np.concatenate([canvas[::-1], np.ones((H, W, 1), np.float32)], axis=2)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = out
    im.file_format = 'PNG'
    im.save()
    bpy.data.images.remove(im)
    return out
