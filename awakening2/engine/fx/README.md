# fx — drawn 2D anime effects for Awakening II

Pure-Python (numpy + numba + OpenCV) effects animation: every effect is a set of **designed
cel shapes** (round billows, cut-out debris, leaves, flame tongues, ribbons, strokes) with
2–3 hard-edged tones, an optional colour line, timed on 2s. The only soft (airbrushed)
elements are the photography helpers in `light.py`, which go into a separate additive
light buffer. Nothing here samples noise thresholds, downloads assets or calls a model.

Tests, contact sheets and MP4 loops: `awakening2/fx_tests/` (`python3 make_tests.py [names]`).

## Conventions

| thing | convention |
|---|---|
| canvas | straight-alpha RGBA float32 `(H, W, 4)`, sRGB 0..1 — cel effects composite into it with *over* |
| light | additive photography buffer float32 `(H, W, 3)`; apply last with `fx.apply_light(rgb, light)` (screen) |
| frame | integer frame at 24 fps; drawings are held on 2s (`on=2`) unless noted (flames flicker on 1s) |
| seeds | `fx.seed(name, ...)` = `zlib.crc32` of the joined parts; every effect takes a `name` and is deterministic |
| units | screen pixels of the canvas you pass; nothing assumes 1920×1040 (scale sizes with the frame) |
| light direction | `light=(lx, ly)`: screen vector pointing *toward* the sun (y down), e.g. `(0.62, -0.78)` = upper right |

```python
import sys; sys.path.insert(0, 'awakening2/engine')     # or: import engine.fx as fx
import fx

canvas = fx.new_canvas(1040, 1920)
light = fx.new_light(1040, 1920)
puff = fx.DustPuff('S08_hand_puff', origin=(640, 900), frame0=834, size=260, ground=930)
puff.draw(canvas, frame)
rgb = fx.composite(background_rgb, canvas, light)       # bg <- canvas (over) <- light (screen)
```

Every effect object is created once per shot (its random design is fixed by `name`) and then
`draw(canvas, frame, ...)` is called for each frame; nothing is stateful between frames, so
frames can be rendered in any order or in parallel.

## Core (`core.py`, `raster.py`)

* `new_canvas(h, w)`, `new_light(h, w)`, `composite(bg, canvas, light)`, `apply_light(rgb, light)`,
  `over(canvas, rgba_patch, x0, y0, opacity)`, `to_premul` / `from_premul`.
* `held(frame, on=2, start=0)` → the frame whose drawing is on screen.
* `Layer(canvas.shape, x0, y0, x1, y1)` — a premultiplied local cel; paint into it, then
  `layer.onto(canvas, opacity)` (whole cel fades as one) or `layer.onto_light(light)`.
* `PolyBatch` — cel polygons: `add(pts, fill, shade, ink, ink_w, term=(tx, ty, tr), alpha)`.
  Points outside the *terminator disc* take the shade colour (a curved, designed shadow shape
  that stays fixed to the screen light while the shape tumbles); `ink_w` px line on the outline.
  Analytic anti-aliasing (numba); `draw(canvas)` paints the batch as one layer.
* `BillowBatch` — groups of discs ("billows") whose lit cap and shadow boundary are *unions of
  shifted discs*, so the tone shapes are scalloped by the bumps; a silhouette colour line is
  drawn on the shadow side only (under all groups, so only the outer edge shows it).
* `stroke_poly(polyline, widths)` — outline polygon of a tapered stroke; `chaikin`, `resample_polyline`.

## 1. Dust (`dust.py`)

```python
fx.DustPuff(name, origin, frame0, size=150, direction=(0, -1), spread=2.6, life=40, n=9,
            light=(.55, -.83), palette=fx.palettes.DUST, ground=None, rise=.25, drift=(0, 0),
            roll=.5, line=2.5, on=2, aspect=.7, arms=.9, main=None, bits=None).draw(canvas, frame)
fx.GroundDust(name, start, direction, frame0, distance=600, duration=30, height=110, life=26,
              grow=0., ...).draw(canvas, frame)
```
* **Designed billows (round 2)**: every cloud has one dominant mass (alternating big / small
  neighbours around it, never two equal neighbours); bumps cycle big / small / medium; on the
  ground the billows are cut flat and their bumps roll over the top arc as a cauliflower crown
  (small squashed bumps at the base); edges moving sideways get a hook-shaped curl (a lobe with
  its lower front bitten out); breaking billows trail occasional thin curling wisps. Small and
  base bumps borrow the mass's tones while the billow is whole (no polka dots), separating
  pieces shade themselves.
* **Cauliflower crown (round 3)**: grounded billows (puff main mass, ground-dust head, ring
  wall) carry 6-10 crown lobes in big / medium / small classes (2-3 big), each with its own lit
  cap. Lobes bud at the top centre, roll outward and down the sides on 2s and are absorbed at the
  base; a standing central lobe keeps the crown closed. The mass itself is shape-only and a few
  shade-only belly lobes carry the mid tone down, so the violet underside ends in a scalloped
  terminator above the flat ground cut. Big sideways-moving billows get a spiral curl on the
  leading edge.
* **Ground-contact spray** (round 5): a flat puff (`aspect < 0.6`, or `main=False`) has no
  dominant dome - 3-4 clusters of small billows fan out along the ground with gaps between them
  and uneven heights, small dark bits are thrown out (`bits=True`), and breaking billows trail
  wisps. `main=True` forces the single-mass design below.
* **Impact puff**: primaries thrown out in a fan (edge lobes travel farther = ground arms; `aspect`
  flattens the vertical), fast ease-out burst (~full size in 1/6 of the life), slow growth,
  buoyant rise; late in life the mass shrinks, the bumps drift apart and shrink at staggered
  times, the last 12 % fades.
* **Rolling ground dust**: a *head* of 3 billows rides the front (ease-out) and rolls forward;
  it sheds a *tail* billow on every drawing that rises and breaks up.
* Shading: warm cream lit cap / ochre mid / violet-brown underside (`palettes.DUST`,
  `DUST_DRY`, `DUST_DARK`, `SMOKE`, `STEAM`, `TRAIL_MIST`, `VEIL`; rows = shadow, mid, lit,
  line). `bias` brightens/darkens, `vert` darkens lower billows.
* **Dust veil** (round 3): `DustVeil(name, origin, frame0, width=1400, height=240, life=48,
  palette=None, opacity=.55, ground=None, segments=14, rise=.35).draw(canvas, frame)` — a thin,
  broken, 2-tone, semi-transparent sheet with a lumpy top edge spreading sideways along the
  ground (flat base), opening gaps and holes and fading; for the S14 blast background (draw it
  before the blast puff). Test: `fx_tests/veil_*`.
* Building blocks for other effects: `BillowSet(name, n).groups(idx, x, y, r, breakup, phase, z,
  drawing)` → groups for `paint_groups(canvas, groups, holes, palette, light, centre, size, ...)`.
* Effects cels are flat-painted by default. `texture=` (e.g. .04) adds a low-contrast dry-brush
  grain inside the fills, anchored to the cloud (`core.brush_grain` works on any Layer).

## 2. Debris (`debris.py`, `shapes.py`)

```python
fx.DebrisBurst(name, origin, frame0, count=40, kinds={'clod': .35, 'crumb': .25, 'pebble': .12,
               'moss': .12, 'root': .08, 'vine': .04, 'bark': .04}, size=(4, 16), direction=(0, -1),
               spread=1.2, speed=(8, 22), gravity=1.2, spin=.35, ground=None, bounce=.3,
               trails=.25, origin_radius=0).draw(canvas, frame)
fx.SoilPour(name, emitter, start, end, rate=22, strands=5, size=(2, 8), gravity=1.1, inherit=.7,
            ground=None, veil=True, strand_width=(10, 24)).draw(canvas, frame)
```
* Pieces: soil clods, crumbs (tiny = flat dark specks), pebbles, moss chunks (soil + lumpy moss
  cap), root fragments (thin S-curves tapered at both ends, with rootlets), vine bits with
  leaves, bark (curled irregular slivers tapered at both ends, one grain line; never
  rectangular). Bark and root pieces are drawn at 0.65x the size range. Outlines are coloured
  (brown for soil and wood, dark green for plants) and thin: 0.8-1.4 px.
  Ink outline + lit/shade; ballistic with gravity, bounces and settles on `ground`; rotation
  and positions held on 2s; the larger pieces (`trails` fraction) drag a short tapered two-tone
  dust streak along their path that thins out over ~30 frames.
* **Pouring soil**: `emitter(frame) -> ((x0, y0), (x1, y1))` (or a point, or an array indexed
  by frame) — pass the projected robot edge per frame. Soil spills from a few points along
  the edge as a few **sheets** (round 5): about one stream per 55 px of ledge (at most
  `strands`), 30-80 px wide and unequal, each ONE ragged two-tone mass hanging from the ledge
  (it keeps ~95 % of the ledge's velocity, so it hangs under a moving ledge instead of trailing
  as a rod), slightly wider at the top, swaying and thinning as it falls; after falling ~5-7
  widths it tears into a few clumps, then crumbs, then powder and dust near `ground`; a thin
  billowing veil behind each stream (`veil_opacity`); very few stray crumbs (`rate` x .03).
  Lines are thin and brown. The falling clumps inherit `inherit` of the ledge velocity. Default
  kinds no longer include roots or vines.
* `add_piece(batch, kind, parts, pos, angle, size, light)` to place single pieces yourself.

## 3. Leaves (`leaves.py`)

```python
fx.LeafFall(name, region=(x0, y0, x1, y1), frame0, count=24, size=(18, 34), fall=(1.2, 2.4),
            swing=(30, 80), period=(40, 70), spiral=.5, wind=(.5, 0), stagger=48, preroll=0)
fx.LeafBurst(name, origin, frame0, count=30, direction=(0, -1), spread=2., speed=(10, 30),
             drag=.09, fall=1.6, size=(14, 30), origin_radius=0, wind=(0, 0))
leaves.draw(canvas, frame, sunlit=lambda x, y: beam_mask[int(y), int(x)])
```
* Shapes: ovate, lance, round, serrate (saw teeth), maple (palmate), willow (long), birch (small,
  toothed), heart, lobed (oak); colours `green`, `deep`, `gold`, `rust` (`palettes.LEAF`) with a
  per-leaf tint; sizes vary per leaf (a few big ones; birch small, willow long); ~35 % are
  curled (one half of the blade narrower, the midrib bent); larger leaves get side veins; the
  outline is a coloured line (leaf shade mixed with ink), not black.
* The flip about the long axis foreshortens the width with cos(flip) and shows the **back
  colour** when it turns over; edge-on leaves become slivers. Pendulum flutter (rises at the
  ends of each swing) or helical spiral (depth changes the scale). `sunlit` warms the leaves
  inside the sunbeams. `preroll` starts the shot with leaves already in the air.

## 4. Wind ring (`wind.py`)

```python
ring = fx.WindRing(name, centre, frame0, radius=1100, duration=36, r0=60, ratio=.45, persp=.3,
                   tilt=0., height=90, slots=44, grass=700, leaves=60, lines=48, band=True,
                   radius_fn=None, mist=0., horizon=None)
ring.draw(canvas, frame, part='back')     # far half + ground marks
# ... draw the robot here ...
ring.draw(canvas, frame, part='front')    # near half
```
* Perspective: the ring lives on the ground plane, projected as an ellipse with minor/major
  `ratio` (≈.4–.6 high angle, ≈.08–.15 eye level), `persp` scales the near side up, `tilt`
  rotates; radius over time = ease-out `r0 → radius` over `duration`, or your `radius_fn(age)`.
  Eye level: pass `horizon=y` for a true ground-plane perspective (camera height = centre y −
  horizon, centre depth = height / ratio): the near side grows as 1/depth and sweeps past the
  camera, the far side flattens onto the horizon.
  `ring.project(rho, phi)` / `ring.R(age)` are public if you need to place other things on it.
* Reads as wind because it is made of: a rolling **dust wall** (head billows in angular slots
  riding the front with cauliflower crowns and flat bases; strongly varied heights - ~20 %
  towering with a second mass stacked on top, ~30 % low - overlapping, ~10 % gaps, ~15 % lagging
  behind the front; each with two smaller followers trailing inward, sporadic billows shed and
  left behind), **flattened
  grass** strokes revealed as the front passes (spring back later), **leaves** thrown outward,
  short-lived radial **speed lines**, and a **pressure band** of broken brush arcs re-drawn
  every drawing; optional `mist` (opacity, e.g. .55) adds translucent floor-mist billows shoved
  out ahead of the wall.
* Shockwave read (round 4): ahead of the dust races a wide translucent ground-hugging band of
  flattened-grass streaks (R..1.28R) led by a thin bright pressure line (~1.29R), slightly broken
  and re-drawn on 2s. The wall uses ~0.55x `slots` heads, so there are fewer, larger masses.

## 5. Engine flames (`flame.py`)

```python
fl = fx.EngineFlame(name, ignite=1236, sputters=[(1222, .32), (1227, .5), (1231, .28)],
                    shutoff=None, diamonds=True, shimmer=False, smoke=True, sparks=True)
fl.draw(canvas, frame, nozzle=(x, y), direction=(dx, dy), radius=56, length=560)
fl.glow(light, frame, nozzle=(x, y), direction=(dx, dy), radius=56, length=560,
        preglow=(1181, .25))     # bell warms up from back_plates_open until ignition
```
* Composite the flame canvas *under* the robot cel so the bell rim hides the flame root
  (the flame starts slightly inside the nozzle); add `glow` to the light buffer on top.
* Timeline: each sputter pops in one frame and chokes out (sparks + smoke billows); the real
  ignition ramps over ~4 frames with an 18 % overshoot. `fl.power(frame)` is public (drive the
  bell glow / shake with it).
* Flame: four cel layers (red-brown edge, orange, yellow, white core), each a body that swells
  past the nozzle plus tapered licks whose lengths / waves change **every frame** (1s flicker);
  shock diamonds along the core; optional shimmer strokes past the tip; glow in the light buffer.

## 6. Launch tools (`launch.py`)

```python
sm = fx.smear_stretch(robot_cel, motion=(0, -420), stretch=.35, tail=1.4, name='S14', frame=f)
mm = fx.smear_multi(robot_cel, motion=(0, -320), n=4, spacing=1.)
imp = fx.impact_frame(1040, 1920, robot_cel, mode='black_gold'|'gold_black'|'inverted'|'red_black', frame=f)
fx.speed_lines(canvas, centre, frame, n=90, inner=(.28, .55), width=(2, 14), colour=None, clear=None)
fx.streak_lines(canvas, direction=(0, -1), frame=f, n=40, length=(200, 700), width=(1.5, 6))
```
* `robot_cel` = the robot drawing as straight RGBA (usually full frame, robot in place).
* **Stretched smear** (round 2): the cel is stretched along the motion from its leading edge,
  keeping its own colours, and tapered speed streaks sampled from its trailing edge (in the
  body colour found there, not the ink) trail behind, thinning and fading in three steps.
  `flatten` (default .25) mixes the streaks toward the body's mean colour; `streaks=False`
  gives the plain stretch.
* **Multiple-image smear**: afterimages flattening toward one colour, short streaks, cel on top.
* **Impact frame**: opaque 2-tone frame — field colour, radial wedges + a ring of heavy spikes in
  the figure colour, the robot as a solid silhouette separated from the lines by a halo. Round 2:
  the silhouette is cleaned (`clean_shape`: small gaps closed, holes below an area filled,
  specks dropped, outline smoothed) and only the few largest of its brightest shapes (eyes,
  core; `max_open=6`) open up in the field colour, cleaned the same way.

## 7. Light trail (`trail.py`)

```python
tr = fx.LightTrail(name, width=90, life=96, mist=True, mist_size=1., light=(.6, -.8), mist_every=4)
tr.draw(canvas, frame, points, births=None, light_buf=light)
```
* `points`: the trail history in **current** screen space, oldest first (newest = the robot);
  `births`: the frame each point was laid (default: one per frame ending now).
* Ribbon (round 4): white-gold core with a soft gold edge - no thin coloured fringe lines -
  lumpy edges, widest just behind the head, tapering, and breaking into three thin wisps over the
  oldest third (it dissolves at the tail). Mist: uneven lumps of strongly varied size (a few big,
  many medium, some small), many stretched 1.5-3x along the path, hugging the ribbon, with soft
  light-lilac shadows biased toward the light (no hard purple halves) and wisps where they break
  up; glow along the core and a head glow in the light buffer.
  Designed to read at thumbnail size against a gold sky (value contrast from the lilac shadows
  and the white core).

## 8. Light / photography (`light.py`)

```python
mask = fx.sunbeams(light, src=(1350, -420), angles=[math.radians(a) for a in (101, 107, 112)],
                   widths=[30, 55, 22], spread=.035, intensity=.33, frame=f, scale=.5)
motes = fx.Motes(name, region, count=200); motes.draw(light, frame, mask=np.clip(mask * 3, 0, 1))
fx.glow(light, (x, y), radius, colour=None, intensity=.5)
fx.lens_flare(light, src, strength=.3, frame=f)
rgb = fx.bloom(rgb, threshold=.78, radius=24, strength=.5)
```
* Shafts with soft (airbrushed) edges, length fade and slow breathing; the returned mask lets
  motes, sparkles and leaves light up only inside the beams.

## Round 6: three distinct looks - SOIL, DUST, WIND (opt-in `style=`)

Every dust-like effect used to share one opaque cream/lavender billow. Pass `style=` to pick a
design (default `None` = the previous look, so existing calls are unchanged):

| look | where | what it is |
|---|---|---|
| `style='soil'` | rise contacts, pours, landings (S05, S08, S09) | dark brown clods on parabolic arcs (2 tones + thin brown line) and arcs of dirt specks; a little earthy brown-grey dust (`palettes.SOIL_DUST`, darker and browner than `DUST_DARK`) that thins out within ~12-18 frames |
| `style='dust'` | launch blast (S14), engine wash (S12, S14) | translucent warm grey (`palettes.DUST_WARM`): body alpha ~0.6, lit crowns ~0.86, no outline; thins (opacity falls ~45 %) and breaks up over its life; `main=True` still gives the single-mass blast, translucent |
| `style='wind'` | the ring (S13) | `WindRing`: a translucent white shock ring of dry-brush strokes (bundles of broken white bristle arcs, densest and brightest at the leading edge, re-drawn on 2s), flattened-grass streaks, torn leaves, a little light mist (`palettes.WIND_DUST`, alpha ~0.45-0.75); the billow wall is ~0.22x and sparse (`wall=0` turns it off, `wall=1` restores it) |

Supported on: `DustPuff(style=)`, `GroundDust(style=)`, `DustVeil(style=)`, `SoilPour(style='soil')`
(its veil and landing dust become `SOIL_DUST`), `WindRing(style='wind', wall=None)`.
Low level: `paint_groups(..., tone_alpha=(shadow, mid, lit))` makes any billow cel translucent per
tone (`palettes.TONE_ALPHA`).

Call-site parameters used for the round-6 verification (`fx_tests/render_styled.py` injects them):

```python
# S05
fx.GroundDust('S05_dust', ..., style='soil')
# Rise (S08, S09)
fx.SoilPour(f'{sid}_{name}', emit, ..., style='soil')
fx.DustPuff(f'{sid}_{name}', ..., aspect=0.45, palette=fx.palettes.DUST_DARK, style='soil')
# S12 engine wash
fx.GroundDust('S12_dust', ..., style='dust');  fx.GroundDust('S12_dust2', ..., style='dust')
# S13
fx.WindRing('S13_ring', ..., style='wind')          # add wall=0 for no billows at all
# S14
fx.DustPuff('S14_blast', ..., main=True, style='dust')
fx.DustVeil('S14_veil', ..., style='dust')
fx.GroundDust('S14_ringL', ..., style='dust');  fx.GroundDust('S14_ringR', ..., style='dust')
fx.GroundDust(f'S14_wash{k}', ..., style='dust')
```
Tests: `fx_tests/styles_*` (soil spray vs translucent blast + wash) and `fx_tests/wind_style_*`.

## Shot recipes (starting points at 1920×1040; frames = seconds × 24 from `audio/cues.json`)

| shot | effect | starting call |
|---|---|---|
| S03 face in the first ray | motes in the ray | `mask = fx.sunbeams(L, src, [a], widths=[90], intensity=.3, scale=.5)`; `fx.Motes('S03', box, 160).draw(L, f, mask=np.clip(mask*3, 0, 1))` |
| S04 chest light | glow on the grille | `fx.glow(L, grille_xy, 220, fx.palettes.LIGHT_WARM, intensity=heartbeat(f))` |
| S05 tremor | pebbles hop | `fx.DebrisBurst('S05', (x, ground), f0, count=14, kinds={'pebble': .6, 'crumb': .4}, size=(3, 9), speed=(4, 9), ground=y, bounce=.35, origin_radius=120, trails=0)` — one burst per shake beat |
| S06 birds burst | leaves shaken loose | `fx.LeafBurst('S06', canopy_xy, f0, count=40, direction=(0, -1), spread=2.8, speed=(6, 18), fall=1.4, origin_radius=300)` |
| S08 hand presses earth | impact puff + torn roots + soil | `fx.DustPuff('S08', hand_xy, f0, size=260, ground=y, aspect=.6, life=50)`; `fx.DebrisBurst('S08', hand_xy, f0, count=46, size=(7, 36), kinds={... 'root': .16, 'moss': .18}, trails=.4)`; `fx.SoilPour('S08', forearm_edge, f0, f1, ...)` |
| S09 rise B wide | soil curtains + ground dust | `fx.SoilPour('S09', edge_fn, f0, f1, rate=30, strands=5, ground=y)` per falling edge; `fx.GroundDust('S09', foot_xy, (±1, 0), f, distance=500, height=120)` at the thud |
| S11 POV up | drifting leaves + flare | `fx.LeafFall(..., spiral=.6)`, `fx.lens_flare(L, sun_xy, .3)` |
| S12 engines | sputter + ignition | `fx.EngineFlame('S12_L', ignite=1236, sputters=[(1222, .32), (1227, .5), (1231, .28)])`; `.draw(..)` + `.glow(.., preglow=(1181, .25))` per bell |
| S13 ring (high) | wind ring | `ring = fx.WindRing('S13', robot_feet_xy, 1248, radius=1250, duration=40, ratio=.5, persp=.25, height=110, slots=56, mist=.55)`; `part='back'`, robot, `part='front'` |
| S13 alt (eye level) | wind ring | `fx.WindRing(..., ratio=.1, horizon=horizon_y)` |
| S14 launch | smears, impact | f+0/f+1: `fx.smear_stretch(cel, (0, -260), .45, 1.2)`, `(0, -420), .9, 1.8`; f+2: `fx.impact_frame(H, W, cel, 'black_gold')`; f+3: `'inverted'`; f+4/5: `fx.smear_multi(cel, (0, -320), n=4)` + `fx.streak_lines(c, (0, -1), f)` |
| S15 through the canopy | branches / leaves explode | `fx.LeafBurst('S15', gap_xy, f0, count=60, spread=6.28, speed=(14, 40))` + `fx.DebrisBurst('S15', gap_xy, f0, kinds={'bark': .5, 'vine': .3, 'moss': .2})` |
| S16 sky climb | light trail | `fx.LightTrail('S16', width=90, life=110).draw(c, f, history_in_screen_space, births, light_buf=L)` |
| S17 ending | beams, motes, leaves | as `fx_tests/scenes.py: LightScene` (beams from the gap, `sunlit=` leaves, motes masked to the beams) |

## Performance (1920×1040, one core, ms per frame of the draw calls, test scenes)

Measured by `fx_tests/make_tests.py` (`fx_tests/timing.json`) on the shared 4-core sandbox while
other jobs were running, so treat as upper bounds. Numba kernels compile on first use (a few
seconds) and are cached in `__pycache__`.

| effect (test scene) | mean | max |
|---|---|---|
| dust (puff + rolling ground dust + small puff) | 43–60 | 75–105 |
| debris (46-piece burst + soil pour + pebble hops) | 85–90 | 165–195 |
| leaves (26 falling + 34 blown) | 16–18 | 20–24 |
| wind ring, high angle (56 slots, 700 grass strokes, 60 leaves, mist; round 4 crowns + shock band) | 400–450 | 500–690 |
| wind ring, eye level (round 4) | 700–800 | ~1100 |
| engine flames (2 bells + glow) | 23–31 | 31–48 |
| launch scene (mean over hold / smear / impact / multi frames) | 150 | 600 |
| … single calls: smear_stretch / smear_multi / impact_frame | ~340 / ~440 / ~390 | |
| light trail (120-frame history, mist) | 90–112 | 180–205 |
| light (5 beams at half-res mask, 260 motes, flare, 14 leaves) | 70–73 | 79–85 |

Costs scale with covered area: the billow kernel is the expensive part (wind ring, trail).
