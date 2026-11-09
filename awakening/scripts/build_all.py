"""Rebuild the whole Awakening scene from the library (run inside Blender)."""
import bpy, sys, math, time, importlib
LIB = r'C:\Users\blender\Documents\awakening\lib'
if LIB not in sys.path: sys.path.insert(0, LIB)
import aw_core as C, aw_shade as S, aw_mesh as M, aw_robot as R, aw_set as SET, aw_comp as COMP, aw_anim as A, aw_fx as FX, aw_sheet as SH
for m in (C, S, M, R, SET, COMP, A, FX, SH): importlib.reload(m)
from mathutils import Vector
T0 = time.time()
sc = bpy.context.scene
sc.frame_set(1)
# ---- wipe
for o in list(bpy.data.objects):
    if o.name != 'Sun':
        bpy.data.objects.remove(o, do_unlink=True)
for c in list(bpy.data.collections):
    bpy.data.collections.remove(c)
for m in list(bpy.data.materials):
    bpy.data.materials.remove(m)
for ng in list(bpy.data.node_groups):
    bpy.data.node_groups.remove(ng)
for ps in list(bpy.data.particles):
    bpy.data.particles.remove(ps)
C.purge()
S.setup_render(sc, 960, 540, samples=16)
# ---- robot
E, parts = R.build()
R.pose(E, R.KNEEL, root=(0, 0, R.KNEEL_ROOT_Z + 0.05))
R.bake_weather()
R.moss_clumps(E); R.vines(E); R.sapling(E)
A.animate_robot(E)
# ---- set
SET.terrain(); SET.mist_volume(); SET.sky_image_world(sc)
terrain = bpy.data.objects['Terrain']
SET.ground_texture(terrain.data.materials[0])
SET.sunbeams(sc)
# ---- light
sun = bpy.data.objects.get('Sun')
if sun is None:
    sun = S.setup_sun(sc)
sun.data.energy = math.pi; sun.data.volume_factor = 0.55; sun.data.angle = math.radians(0.6)
A.animate_sun(sun)
# ---- cameras, glows, shakes
cams = A.setup_cameras(sc)
A.animate_glows()
A.shake(cams['s5_tremble'], 24.0, 27.8, amp_deg=0.45, scale=3.0, build=1.0)
A.shake(cams['s6_rise'], 28.0, 31.5, amp_deg=0.25, scale=3.0, build=1.0)
A.shake(cams['s8_ignite'], 44.3, 47.0, amp_deg=0.3, scale=4.0, build=1.0)
A.shake(cams['s9_launch'], 47.3, 48.6, amp_deg=0.5, scale=5.0, build=0.3)
# ---- forest cards (need the cameras for the billboards)
SET.forest(sc)
SET.canopy_overhangs(sc)
SET.cloud_layer()
# ---- FX
sc.frame_set(A.F(10.3))
pauld = bpy.data.objects['RB_pauldron.L']
land = pauld.matrix_world @ Vector((-0.5, 0.2, 1.8))
FX.little_bird(land, (0, -1, 0))
treetops = [(-35, 30, 26), (30, 40, 28), (-50, 10, 24), (45, 15, 25), (-20, 55, 27), (10, 60, 26), (-60, 40, 28), (55, 50, 27)]
FX.flock(treetops)
torso = bpy.data.objects['RB_torso']
flames = FX.engine_flames(torso)
FX.animate_flames(flames)
ring = FX.wind_ring('FX_ring1'); FX.animate_ring(ring, 44.6, 46.3, r0=3, r1=40, z=0.9, alpha=0.75)
ring2 = FX.wind_ring('FX_ring2'); FX.animate_ring(ring2, 47.4, 49.2, r0=4, r1=130, z=0.9, alpha=0.8)
TRAIL_PTS = [(0, 0.6, 5.0), (0.8, 1.6, 13.0), (4.5, 5.5, 41.0), (16.0, 17.0, 115.0), (62.0, 52.0, 425.0)]
TRAIL_KEYS = [(47.4, 0.01), (47.45, 0.02), (48.0, 0.12), (49.0, 0.32), (50.5, 0.62), (56.0, 1.0)]
trail = FX.trail(TRAIL_PTS, 'FX_trail', depth=1.1, color=(1.0, 0.9, 0.6), strength=3.0)
FX.animate_trail(trail, 47.4, 50.5, 55.5, TRAIL_KEYS)
FX.trail_follow(trail, E['root'], z_offset=-5.0)
mist_trail = FX.trail(TRAIL_PTS, 'FX_trailmist', depth=3.0, color=(1.0, 0.95, 0.88), strength=0.9)
mist_trail.data.materials[0].node_tree.nodes['Fade'].outputs[0].default_value = 0.3
FX.animate_trail(mist_trail, 47.4, 51.0, 56.0, TRAIL_KEYS)
FX.trail_follow(mist_trail, E['root'], z_offset=-7.0)
mist_trail.data.materials[0].surface_render_method = 'BLENDED'
# debris from the mossy parts while rising
src = FX.debris_collection()
FX.collision_ground(terrain)
for i, (nm, cnt) in enumerate((('RB_pauldron.L', 70), ('RB_pauldron.R', 70), ('RB_head', 40), ('RB_forearm.L', 35), ('RB_thigh.L', 45), ('RB_torso', 60))):
    FX.particles(bpy.data.objects[nm], 'debris', src, 29.6, 35.5, cnt, life=2.4, vel_normal=0.8, vel_rand=0.5, size=0.55, size_rand=0.6, seed=i + 1)
# force fields, scoped by collection so each effect feels only its own fields
fields_none = C.coll('FieldsNone'); fields_wind = C.coll('FieldsWind'); fields_sky = C.coll('FieldsSky')
def scope(ps, coll):
    ps.settings.effector_weights.collection = coll
for ob in bpy.data.objects:
    for ps in ob.particle_systems:
        scope(ps, fields_none)
# leaves blown by the ignition wind: a ground disc emitter
disc = FX.disc_emitter('FX_leafdisc', 45, (0, 0.6, 0.6), n=1200)
ps_wind = FX.particles(disc, 'windleaves', src, 44.6, 46.8, 500, life=3.0, vel_normal=0.0, vel_rand=0.3, size=0.6, size_rand=0.4, gravity=0.35, drag=0.15, seed=9, emit_from='VERT')
ps_wind.settings.object_align_factor = (0, 0, 1.2)
scope(ps_wind, fields_wind)
wind = FX.force_field('FX_wind', 'FORCE', (0, 0.6, 2), 0.0, falloff_type='SPHERE', falloff_power=1.0)
C.link(wind, fields_wind)
wind.field.strength = 0; wind.keyframe_insert('field.strength', frame=A.F(44.5))
wind.field.strength = 120; wind.keyframe_insert('field.strength', frame=A.F(45.3))
wind.field.strength = 60; wind.keyframe_insert('field.strength', frame=A.F(47.0))
wind.field.strength = 260; wind.keyframe_insert('field.strength', frame=A.F(47.6))
wind.field.strength = 0; wind.keyframe_insert('field.strength', frame=A.F(49.0))
# leaves spiralling down through the sunbeams in the last shot
top = FX.disc_emitter('FX_leaftop', 26, (-4, -6, 34), n=600)
ps_fall = FX.particles(top, 'fallleaves', src, 47.8, 54.5, 150, life=9.0, vel_normal=0.0, vel_rand=0.8, size=0.7, size_rand=0.4, gravity=0.06, drag=0.25, seed=5, lifetime_rand=0.1, emit_from='VERT')
scope(ps_fall, fields_sky)
vortex = FX.force_field('FX_vortex', 'VORTEX', (0, 0.6, 15), 1.6, falloff_type='SPHERE', falloff_power=0.5)
turb = FX.force_field('FX_turb', 'TURBULENCE', (0, 0, 20), 2.5, size=6.0, flow=0.3)
C.link(vortex, fields_sky); C.link(turb, fields_sky)
# dust: tremor puffs around the base, a big rolling cloud at the launch
ring_small = FX.ring_emitter('FX_dustring', 4.5, 9.5, z=2.3)
scope(FX.dust_particles(ring_small, 'tremordust', 24.0, 27.6, 70, 3.0, life=2.6, vel=0.9, seed=4), fields_none)
ring_big = FX.ring_emitter('FX_dustring2', 3.0, 14.0, z=2.6)
scope(FX.dust_particles(ring_big, 'launchdust', 47.35, 48.1, 140, 8.0, life=1.25, vel=3.5, gravity=-0.02, seed=5), fields_wind)
scope(FX.dust_particles(ring_big, 'ignitedust', 44.6, 47.0, 90, 5.0, life=2.0, vel=1.5, gravity=-0.03, seed=6), fields_wind)
# ---- ink and post
vb, vi = S.setup_layers(sc)
S.setup_freestyle(sc, (('Robot', 1.3), ('Birds', 0.75)), vl=vi)
bird_names = [o.name for o in bpy.data.collections['Birds'].objects if o.parent is None]
ng = COMP.setup(sc, w=960, mattes=['J_root'] + bird_names)
COMP.fades(ng, [(1, 0.0), (A.F(1.2), 1.0), (A.F(54.6), 1.0), (A.F(56.0) - 1, 0.0)])
sc.frame_set(1)
# particle caches on disk, so background renders (which start mid-way) see the same simulation
for ob in bpy.data.objects:
    for ps in ob.particle_systems:
        pc = ps.point_cache
        pc.use_disk_cache = True
        pc.frame_start = 1; pc.frame_end = sc.frame_end
if bpy.data.filepath:
    bpy.ops.ptcache.free_bake_all()
    bpy.ops.ptcache.bake_all(bake=True)
sc.frame_set(1)
print('BUILT in %.1fs; objects %d' % (time.time() - T0, len(bpy.data.objects)))
