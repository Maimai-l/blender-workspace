"""Background render: blender -b awakening.blend -P render_job.py -- <start> <end> <outdir> [scale%] [samples]
Writes <outdir>/f_####.png and <outdir>/progress_<start>.txt; a .done file at the end."""
import bpy, sys, os, time
argv = sys.argv[sys.argv.index('--') + 1:]
start, end, outdir = int(argv[0]), int(argv[1]), argv[2]
scale = int(argv[3]) if len(argv) > 3 else 100
samples = int(argv[4]) if len(argv) > 4 else 24
sc = bpy.context.scene
sc.render.resolution_x = 1920; sc.render.resolution_y = 1080
sc.render.resolution_percentage = scale
sc.eevee.taa_render_samples = samples
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGB'
sc.render.use_file_extension = True
os.makedirs(outdir, exist_ok=True)
sc.frame_start = start; sc.frame_end = end
sc.render.filepath = os.path.join(outdir, 'f_')
prog = os.path.join(outdir, 'progress_%d.txt' % start)
t0 = time.time()
def on_frame(scene):
    with open(prog, 'w') as fh:
        fh.write('%d %d %d %.1f\n' % (scene.frame_current, start, end, time.time() - t0))
bpy.app.handlers.render_write.append(on_frame)
def line_boil(scene):
    # hand-drawn line boil: the ink wobble and thickness noise change every second frame (12 fps)
    k = scene.frame_current // 2
    for ls in bpy.data.linestyles:
        for m in ls.geometry_modifiers:
            if m.type == 'PERLIN_NOISE_1D':
                m.seed = 3 + k
        for m in ls.thickness_modifiers:
            if m.type == 'NOISE':
                m.seed = 7 + k
bpy.app.handlers.frame_change_pre.append(line_boil)
# use the marker-bound cameras: render.render(animation=True) switches cameras at markers automatically
bpy.ops.render.render(animation=True)
with open(os.path.join(outdir, 'done_%d.txt' % start), 'w') as fh:
    fh.write('%.1f\n' % (time.time() - t0))
print('RENDER DONE %d-%d in %.1fs' % (start, end, time.time() - t0))
