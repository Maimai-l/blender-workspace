# engine/birds — the small bird and the flocks of *Awakening II*

The small bird is a **Japanese white-eye (mejiro, *Zosterops japonicus*)**: olive-green upperparts,
lemon-yellow throat and undertail, off-white belly with buff flanks, the bold white eye-ring, a dark
loral stripe, a thin dark beak and lead-grey legs. Naturalistic proportions (no cartoon head or eye);
the charm comes from timing and acting.

Everything is drawn by our own code: no image models, no downloaded assets.

* **Model.** `model.py` turns a pose (a dict of about 50 numbers) into drawing primitives in the
  bird's own frame. The body is a dense chain of spheres along a curved spine, which gives a
  smooth, fluffy silhouette from any angle. The face (eye, eye-ring, lores, beak), the folded wing
  (a hand-designed side-view shape mapped onto the body as a decal), the skeletal flight wings
  (arm, hand, nine primaries, eight secondaries, coverts), the tail and the legs are curves and
  polygons. Because there is one model, every drawing is on-model, including the turnaround.
* **Look.** `draw.py`, `shade.py` and `raster.py` draw it as a cel:
  * flat light colour, one hard-edged shadow tone, a warm rim tone when backlit, and small
    highlights (the eye catch-lights, a sheen on the lit edge of the crown, a glint on the beak);
  * designed cast shadow of the folded wing onto the flank;
  * variable-width, anti-aliased ink in warm dark brown (`#3a2519`). The silhouette line is
    thicker on the side away from the light and pools slightly at concave corners. Interior
    feather lines taper at both ends.
  * Fills are supersampled (2–8×) and box-resolved, so there are no seams. Strokes are analytic.
* **Output.** A straight-alpha **RGBA float32 sRGB** sprite. The drawing works at any size, from
  about 8 px to 500 px tall.

## Quick start

```python
import sys; sys.path.insert(0, 'awakening2/engine')
import numpy as np, birds

canvas = np.zeros((1040, 1920, 4), np.float32)            # straight alpha, sRGB 0..1
sun = birds.Light(dir=(0.8, 0.6), depth=-0.3)             # low sun from screen right, behind -> rim
birds.draw(canvas, birds.pose('idle'), x=960, y=700, scale=200, facing=1, light=sun)

tr = birds.landing(x=1060, y=820, scale=200, facing=1)    # S02 beat, shot-local frames
for f in range(132):
    birds.draw_state(canvas_for_frame_f, tr.state(f), sun)
```

## Conventions

* **`scale`** is the height of the *perched* bird in pixels, from the feet to the crown (6.0 cm).
  A flying bird's wingspan is about 2.55 × `scale`.
* **`(x, y)`** places the pose's root. For perched poses the root is the feet contact point; flight
  poses use the same root, a point below the body. A landing path therefore ends exactly on the
  perch. Sub-pixel positions are rendered exactly.
* **`facing`**: `+1` means the beak points screen-right, `-1` screen-left. The light stays in
  screen space, so a mirrored bird is still lit from the correct side.
* **Detail** is chosen from the scale:

  | scale | detail |
  |---|---|
  | ≥ 90 px | `full`: feather lines, beak glint, double catch-light |
  | ≥ 40 px | `mid` |
  | ≥ 18 px | `low`: silhouette ink and colour masses only |
  | below 18 px | `tiny` |

  Force a level with `detail=`.
* **Line weight**: `line_scale=` multiplies all ink widths. The base width is `clip(0.0118 × scale, 0.7, 3.6)` px.

## API

### Drawing
| call | what |
|---|---|
| `Light(dir=(lx,ly), depth=d, rim=None, bias=0.06, rim_width=0.48, shadow_mul=None, rim_color=None)` | Screen-space light. `dir` points toward the light (y up). `depth`: +1 front light, 0 side light, −1 backlight. When `depth < −0.12` the bird turns to its shadow tone with a warm rim on the lit edge (`rim=True`, the default when backlit). `shadow_mul`: RGB multiplier for the shadow tones; pass the shot's cool shadow colour so the bird belongs to the background. `rim_color`: the warm edge colour. |
| `render(pose, scale, facing=1, light=None, ss=None, detail=None, style='cel', subpx=(0,0), ink_color=None, line_scale=1.0, palette_overrides=None)` | Returns `Sprite(rgba, ox, oy)`. The root lies at sprite pixel `(ox+subpx[0], oy+subpx[1])`. `style='silhouette'` gives two warm-dark tones and a rim, for flocks against the sky. |
| `draw(canvas, pose, x, y, scale, facing=1, light=None, cache=True, **render_kw)` | Renders the pose and composites it with "over" at the root `(x, y)`. A small cache (16 entries) serves an identical drawing again, such as the second frame of a drawing on 2s. |
| `composite(canvas, rgba, x0, y0)` | Straight-alpha "over" at an integer offset. |

### Poses (`poses.py`)
`pose(name, **overrides)` returns a full pose dict. `blend(a, b, t)` is an in-betweener (numeric
parameters are interpolated; `fold`, `legs` and similar switch at 0.5). `POSES` lists the names:

* **perched**: `idle`, `idle_fluff`, `idle_alert`, `idle_lean`, `look_cam`, `look_back`,
  `look_up`, `look_down`, `tilt`, `tilt_other`, `chirp`, `chirp_close`, `blink`, `crouch`,
  `hop_air`, `hop_land`, `settle`, `startle`, `tail_flick`, `shake`, `preen`
* **flight (side view)**:
  * flap drawings: `flap_up`, `flap_down1`, `flap_down2`, `flap_bottom`, `flap_upflick`, `flap_up2`
  * `glide`, `bound` (wings closed between flap bursts)
  * landing: `approach`, `flare`, `flare2`, `touchdown`, `touchdown2`, `fold1`, `fold2`,
    `fold3`
  * take-off: `to_crouch`, `to_spring`, `to_air`
* **flap cycles**: `flap_pose(p, i, 'flap6')` applies drawing *i* of the 6-drawing cycle, including
  its body bob and pitch wobble. `'flap4'` is a faster 4-drawing cycle for small or far birds.

Useful pose parameters:
* body: `tilt`, `fluff`, `neck`, `crouch`, `by` (body height above the feet)
* head: `head_yaw`, `head_pitch`, `head_roll`, `beak` (0–1), `blink`
* tail: `tail`, `tail_spread`
* folded wings: `wdroop`, `wspread`
* flight wings, per wing (prefix `n_` for the near wing, `f_` for the far one): `el`, `sw`, `tw`,
  `ext`, `hel`, `hsw`, `fan`
* legs: `legs` (`perch` / `reach` / `hang` / `tuck` / `none`), `leg_reach`, `toe_open`
* whole bird and view: `yaw` (turnaround: 0 profile, 90 toward the camera, −90 back),
  `pitch`, `roll`, `view_el` (camera elevation: + from above, − from below)

### Animation (`anim.py`)
`Track(on=2)` holds keys:

```python
tr.key(frame, pose, x, y, scale, facing, ease='inout', cycle=None, on=None, pos_ease=None, phase=0, **pose_overrides)
```

* `pose` is a name or a dict. Any of `x`, `y`, `scale`, `facing` left out is taken from the
  previous key.
* `ease` sets the spacing of the segment that starts at this key: `linear`, `in`, `out`,
  `inout`, `snap` or `hold` (`hold` means no in-betweens).
* `cycle='flap6'` or `'flap4'` drives the wings until the next key.
* Positions follow arcs (Catmull-Rom through the key positions).
* `tr.blink(frame, length)` adds a blink.

`tr.state(f)` returns `dict(pose, x, y, scale, facing, drawing)`, or `None` before the first key.
A new drawing appears every `on` frames (on 2s by default), so position and pose both hold for 2
frames, as on a cel. Draw a state with `draw_state(canvas, st, light)`.

Acting sequences (frames are shot-local; the defaults follow `audio/cues.json`):

* **`landing(x, y, scale, facing, t_flare=38, t_touch=50, t_hop=70, t_chirp=101, t_end=132, enter=(-2.6,-1.5), hop_dx=0.42, looks=None, chirps=2)`**,
  for S02 and S17. The bird flaps in on an arc, glides in and flares (two drawings across the
  cue's 12 frames), touches down with its wings still up and absorbs the landing. It then lowers
  its wings (half open, then a loose fold with spread tips, then a tidy fold) and settles. After that it hops: an
  anticipation crouch, one airborne drawing, a landing with a tail flick, and a settle. It then
  looks around with snap turns and holds (toward the camera, a head tilt, over its back), chirps
  twice, and blinks.
  * For S02, use `t_flare=(9.6-8.0)*24`, and so on.
  * For S17, pass `t_hop=None` and/or `t_chirp=None` to skip those beats.
* **`flee(x, y, scale, facing, t_startle=31, t_flee=50, t_exit=None, exit=(3.2,-3.0))`**, for
  S07 (eyes ignite at 31.8 s, flee at 32.6 s). The bird looks toward the camera, snaps to a
  startled pose and holds it, makes an anticipation crouch, springs (on 1s), takes its first
  downstroke and flaps away on an accelerating rising path.
* **`crossing(p0, p1, f0, f1, scale, facing=None)`**, for S01 (the far bird). This is the
  bounding flight of small passerines: bursts of the 4-drawing flap cycle alternate with closed-wing
  "bounds".
* **`follow_path(points, f0, f1, scale, cycle='flap6', base='glide', ease='linear', glide_every=0, glide_len=6, scale_end=None)`**
  flies along any polyline of screen points. The facing follows the horizontal direction, and the
  scale can change along the way (for birds that approach or recede).

### Flocks (`flock.py`)
* **`burst(n=150, canopy=((x0,y0),(x1,y1)), f_start=0, frames=72, seed=7, span=(8,46), up_speed=(14,24), groups=3, drift=(-0.45,-0.4), sources=None, stagger=3, launch_boost=1.9, recede=0.3)`**,
  for S06. It returns a `FlockSim`; `sim.at(f)` gives the list of bird states at frame `f`.
  * The birds erupt from a few source trees on the treetop line. `sources` are fractions along
    the line; the default is 3 random trees. A few stragglers launch anywhere.
  * Each tree goes off `stagger` frames after the previous one, so the alarm ripples across.
  * Birds fan out fast, at `launch_boost` × cruise speed with drag, then bend into loose groups,
    about one per tree, that drift away in different directions. They shrink by up to `recede`
    as they leave.
  * Near birds are bigger and faster. Each bird has its own flap phase and runs on 1s (small) or 2s.
  * Some birds glide for a few frames.
  Birds start just below the treetop line at full opacity. Composite the flock under the
  front canopy layer, so the trees hide the launch.
* **`circling(n=40, centre, radius=(rx,ry), frames, period=150, span=(6,22))`**: a wide circling
  flock, with loose rings and phase scatter. The near side of the orbit is lower and larger. The
  birds alternate flap bursts and glides.
* **`draw_flock(canvas, states, light=None, style='silhouette', tint=None)`** draws a frame.
  * Sprites are drawn by the same renderer: 6 flap drawings plus a glide, in three views
    (`below`, `low`, `side`), at 7 size buckets.
  * The sprites are cached, then rotated to each bird's heading, scaled and composited.
  * A state is `dict(x, y, span, heading, drawing, view, alpha)`. You can also write your own
    simulator and draw with this.

## Speed (one core, this sandbox)
| job | time |
|---|---|
| perched bird, 500 px | 1.0 s per drawing |
| perched bird, 250 px | 0.25–0.5 s (backlit flare: 0.48 s) |
| perched bird, 200 px | 0.12–0.2 s |
| perched bird, 100 px | 0.05 s |
| perched bird, 40 px | 0.02 s |
| perched bird, 12 px | 0.013 s |
| 132-frame 1920×1040 landing video (background, bird, x264) | 16 s |
| 72-frame flock burst video, 160 birds | 7–8 s, including the one-off sprite build |

* Drawing on 2s halves the work: `draw()` caches identical drawings, so the second frame of
  each drawing is only a composite.
* numba compiles for a few seconds on the very first import; the result is cached in
  `__pycache__`.

## Test renders (`awakening2/bird_tests/`, regenerated by `make_tests.py`)
* `model_sheet.png`:
  * turnaround, 14 perched poses, the 6-drawing flap cycle with the glide, landing and take-off
    keys;
  * light options (key, side, backlight with rim, facing left);
  * a scale ladder (120 down to 8 px), flock cycles in 3 views, and palette swatches.
* `landing_contact.png`: every drawing (every 2nd frame) of the S02 landing, at 24 fps, frames
  14–130. The timing uses the cue sheet: flare at f38, touchdown at f50, hop at f70, chirp at
  f101. `landing_f040/046/052/072/104.png` are full-resolution frames. `landing.mp4`.
* `takeoff_contact.png` and `takeoff.mp4`: the S07 startle and flee.
* `flock_burst_contact.png`, `flock_burst_f013.png` and `flock_burst.mp4`: the S06 burst.
  `flock_circling_f030.png` shows the circling flock.
* `crossing_far.mp4`: the S01 far bird in bounding flight.

## Known weaknesses (v1)
* **Wings.** Flight wings are flat polygons from a feather skeleton.
  * Mid-stroke drawings are designed for a slightly-above side view (`view_el` about 15°). From
    other angles the in-betweens can look stiff or edge-on.
  * The change from the folded wing (a body decal) to the open wing (the skeleton) is a cut
    between drawings, not a morph. On 2s it reads as the snap of a real wing, but there is no
    smear drawing.
* **Front view.** The front and back turnaround views are correct but plain. The front face looks
  goggle-like, because birds' eyes really are on the sides of the head.
* **Shading.**
  * The shadow terminator comes from smooth 3D normals with a hard threshold, so it is clean but
    "designed by light", not hand-placed.
  * There is no chin shadow: a cast-shadow attempt read as a collar and was removed.
* **Detail.** There is no feather texture or breakup on the silhouette (deliberately clean). The
  legs are simple capsules; on the moss the toes stand on the surface, they do not sink in.
* **Flocks.** Flock birds are rotated sprites, and the views are picked from the heading only.
  There is no wing smear or motion blur on fast burst frames.
* **Sequences.** The acting sequences are fixed choreographies with parameters; retime or edit them
  with `Track.key` for anything else.
