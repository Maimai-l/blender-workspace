# gouache — painted backgrounds for Awakening II

A procedural gouache painting engine (numpy + numba + OpenCV, no image models, no
photos, no downloaded assets) and the per-shot background paintings built with it.
Every painting is composed in screen space, layer by layer, from the storyboard
layouts; there is no 3D ground plane and no stamped/repeated tree.

## Render

    cd awakening2/engine
    python3 -m gouache.render S01 S16 S11            # Phase 1 shots
    python3 -m gouache.render S08 S03 S02 -j 2       # any shots, 2 worker processes
    python3 -m gouache.render                         # all shots (S17 last: it reads S01)

Output per shot in `awakening2/bg/<shot>/` (rendered into `bg/.tmp_<shot>/` first, then
moved file by file with `layers.json` last, so a consumer never reads a half-written layer):

| file | content |
|---|---|
| `NN_<layer>.png` | straight-alpha RGBA layer, far → near, colour bled under transparent pixels |
| `flat.png` | all layers composited (normal blending), painting size |
| `preview.jpg` | 960-px preview |
| `layers.json` | painting size, `margin`, per layer: `file`, `depth` (parallax 0 = sky … 1 = nearest), `size`, `offset`, `blend`, `coverage`, `note`; plus shot data (sun position, horizon, robot zone, frames for tilts, pebble/dew/fern positions, render seconds) |

Layer PNGs include an overscan margin (40–48 px) on every side: a layer file is
`(W+2m) × (H+2m)` and its top-left sits at `offset = (-m, -m)` in painting
coordinates, so layers can be shifted for parallax or shake without showing an edge.
Everything is deterministic: each shot seeds from `zlib.crc32(shot_name)`.

Contact sheets: `bg/contact_phase1.jpg` (S01, S16, S11), `bg/contact_phase2.jpg` (S02-S13, S17),
`bg/contact_round4.jpg` (S00, S16, S16A, S12, S13).

## Timings (this sandbox, 1 process per shot)

| shot | size | layers | seconds |
|---|---|---|---|
| S01 | 1920×2900 | 8 | ~90 |
| S02 | 1920×1040 | 3 | ~51 |
| S03/S07 | 2100×1140 | 5 | ~18 |
| S04 | 1920×1040 | 2 | ~17 |
| S05 | 1920×1040 | 5 (far, mid, ground, pebbles, dew) | ~15 |
| S06 | 1920×1040 | 3 | ~13 |
| S08 (S14) | 1920×1040 | 8 | ~45 |
| S09 | 1920×1040 | 5 | ~36 |
| S10 | 1920×1600 (160 px overscan) | 4 | ~29 |
| S11 (S15) | 1920×1040 | 6 | ~12 |
| S12 | 1920×1040 | 5 | ~18 |
| S13 | 2200×1200 | 4 | ~31 |
| S16 | 2400×1040 (160 px overscan) | 7 | ~15 |
| S00 | 2200×1040 (64 px overscan) | 5 | ~11 |
| S16A | 4096×1040, tileable in x | 3 + screen-fixed `sun_glow` | ~10 |
| S17 | 1920×1040 | 8 | ~9 (re-uses the rendered S01 layers) |

All 14 shots: about 3.5 minutes with `-j 2`. First run adds ~20 s of numba
compilation (cached in `__pycache__` afterwards).

## Engine modules

- `kernels.py` — numba rasterisers on premultiplied float RGBA:
  - `k_dabs`: thousands of dabs per call (~400k leaf dabs/s). Shapes: round, leaf
    (pointed), flat (square-ish flat brush), petal. Per dab: ragged edge, bristle
    streaks along the drag direction, wet-edge pigment pooling (`pool`), dry brush
    that only catches the paper tooth (`dry`), two-tone loaded brush (`split`).
  - `k_stroke`: one continuous stroke along a polyline (nearest-segment sweep):
    width/opacity/colour along the stroke, bristle streaks, a second colour loaded on
    one side (`color2`, `load2`), dry-brush tail (paint running out), pooling.
  - `k_sweep`: form fields of a tube (across −1..1, along 0..1, open flat ends) used
    to shade trunks/limbs/roots; `k_blobs`: the cluster G-buffer (coverage, dome
    shading toward a 3-D sun vector, cluster id, radius).
  - composite modes: over, alpha-lock (paint only on existing paint), erase, behind.
- `canvas.py` — `Canvas` (flat coordinates + overscan margin), `dabs()`, `stroke()`,
  `tube_fields()`, `catmull`, `wobble`, `taper`, paper texture (`PAPER`, tileable
  cold-press tooth + fibres, used by dry brush and `grain()`), saving with colour bleed.
- `color.py` — Oklab conversions, `mix`, `ramp`, `shade`, `jitter` (per-dab Oklab
  variation), `aerial` (aerial perspective toward a haze colour), dawn palette `DAWN`.
- `foliage.py` — `Blobs` + `render_gbuffer` + `paint_mass`: foliage masses painted
  like a gouache painter: block-in of 3 value shapes, leaf dabs sorted dark → light
  (lit cluster tops end up as crisp shapes of small leaves), broken leafy edges that
  stick out of the silhouette, translucent sun-through leaves and warm rims on the
  sun side, highlight tips. Also `spray` (irregular leafy twigs with rims) and `vine`.
- `trees.py` — `paint_tube`: banded value shapes with a meandering terminator, warm
  rim, cool reflected light, bark strokes that follow the form (with twist), fissures,
  beech eye marks and lichen, moss patches (solid under-layer + texture), clumpy ivy,
  dappled light flecks, ground-mist fade. `trunk_path` (lean, sway, bulges, buttress
  flare), `buttress_roots`, `limb_fan`, `crown_blobs`; species presets `camphor`
  (twisting, furrowed), `beech` (smooth grey), `cedar` (red-brown fibrous strips).
- `forest.py` — the forest-interior kit used by most shots: `forest_row` (a row of
  varied trunks with a hanging canopy underside, occasional high side branches with
  layered leaf masses, bushy saplings, vines), `layered_mass` (irregular foliage mass:
  many mixed clusters, ragged drooping lower edge, satellites), `broadleaf` (mid tree
  with forked limbs and layered crown masses), `far_trunks`, `giant` (huge trunk with
  buttress roots), `floor` (forest floor with litter, roots, dapples, flowers),
  `undergrowth`, `surface_roots`.
- `ground.py` — `ground` (perspective floor dabs), `fern` with `kind` = sword, lady
  (lacy, twice-divided), bracken (triangular, divided pinnae), hart (undivided strap
  fronds), maidenhair (round leaflets on dark stems); `grass`, `stone`, `flowers`.
- `sky.py` — `sky` (Oklab gradient + sun glow, brushed over with broad tilted strokes
  that sample it with colour jitter), `paint_planes` / `plane_cloud` (round 4: Ghibli
  cumulus painted as big flat value planes, not dabs: whole-form + per-lobe shading cut
  into shadow / mid / lit / crown planes with meandering hard-ish terminators, a crisp
  silhouette, a thin sun-side rim, a few broad form-following strokes and soft wisps;
  also used for distant forest canopies with `leafy_edge` and `leaf_px`),
  `sculpted_blobs` (flat base, big crown lobes, satellites), older dab-based
  `sculpted_cloud` / `paint_clouds`, `sun_disc`.
- `atmos.py` — `mist` (banks of soft low-opacity horizontal strokes, warm where lit,
  lilac in shade), `beams` (streaky soft shafts), `glow`, `dapple`, `haze_pass`.
- `soft.py` — painted soft focus helpers (`mist_strokes`: mist as broad bristle strokes).
  Soft focus itself is a mode of the painters, not a filter: `forest_row(..., soft=px)` and
  `paint_tube(..., soft_edge=px)` paint simplified trunks (few long bark strokes, no moss
  specks, dry-brush edges broken up by the paper tooth) and two-plane foliage masses with
  bristly edges (`paint_planes(..., brush_edge=1)`). Used for S02 and S04 (round 5).
  (`repaint()` and the `soft_*` shape helpers are kept but unused: they looked like an
  impressionist filter / too schematic.)
- `forest.character()` — individual features for near trunks: knot holes with lit lips,
  bracket fungi, a hollow between buttress roots, ivy in distinct climbing bands, moss
  cushions on the root flare (`giant(..., traits=dict(...))`; S08, S09).
- `backlit.py` — canopy undersides against the light (round 7, S11/S15): `backlit_masses()`
  paints leaf masses as translucent foliage. Thickness inside the silhouette (with clumping
  noise) and the light reaching each mass (strong near the gap) give the transmitted light;
  it is cut into ragged painted bands from deep cool green to glowing yellow-green, with
  per-mass translucency and hue, dark overlapping leaves in the bright parts, glowing
  leaves near edges, leaves breaking the silhouette, and a rim that differs per mass
  (none / a few hot leaves / a soft glow, in varied colours, never a continuous line).
  `haze_veil()` and `light_shafts()` paint glowing air between the canopy storeys.
- `atmos.light_stripes()` (round 8, S12) — sunlit stripes on a shaded floor in a backlit scene: wedges
  radiating from the point on the horizon under the sun, with wandering widths, breaks from small
  shadows, cut by the near trunks' cast shadows (`occluders`), hard dry-brush edges, a warm tint that
  keeps the floor texture, mottling, grass catching the light. `atmos.clean_shaft()` — a translucent
  light shaft with clean edges (flat fill, faint streaks), used instead of soft radial ray fans.
  (`ground_stripes()` and `floor_light()` are earlier attempts, kept but unused: one read as road
  markings, the other as a sunburst emblem.)
- `atmos.light_patches()` (round 9, S12) — a few irregular sunlit pools on a shaded floor, built from
  leaf-sized flecks (scalloped edges), with leaf-shaped foliage-shadow holes, each turned a little off the
  sun's direction so they do not converge; hard dry-brush edges; replaces `light_stripes()` in S12.
- `imprint.py` (round 9): the displaced-soil lip is no longer a pale raised ring but broken soil clods and
  torn moss, each with a small cast shadow away from the sun and a lit sliver only on the sun side.
- S13 floor (round 9): a patch map (dark moss, bright moss, grass, bare soil with fallen leaves) with ragged
  edges and per-class texture, small fern rosettes, a value-key pass so the robot reads first, and a
  hard-edged canopy shadow with sun flecks / leaf shadows along its edge.
- `backlit_masses(..., palettes=, pal_p=, pocket=)` — per-mass palettes (olive, teal, russet) and light
  pockets for variety in large backlit ceilings (S11 outer canopy).
- `imprint.py` — `paint_imprint()`: depressions pressed into the floor (round 6, S17):
  bowls and capsules in a foreshortened ground frame -> height field with a raised soil
  lip -> sun lighting with a cast shadow from the far rim -> flat painted soil planes,
  contour-following strokes, crumbs, a pool of light, broken roots with pale cut ends and
  rootlets, torn moss in irregular groups (some overhanging), flowers on the rim.
- `ground.fern(..., body=1)` — opaque two-tone frond bodies under the leaflets, curved
  light stems (no thin dark spokes), used in S13. `paint_mass(..., rim_vary=1)` varies the
  rim per clump (on/off, width, colour, position), used in S06.
- `layers.py` — `Painting`: per-layer grain, PNG + running flat composite + json.
- `shots/sNN.py` — one composition per shot (`build(outdir)`).

## Tileable layers (S16A)

`shots/s16a.py` paints every element (stroke, cloud, wisp) once on its own small canvas
and pastes it at x and x ± W, so each layer wraps exactly (the wrap-edge difference
equals a normal neighbouring-column difference). Scroll `sky` slowest, `cloud_bank`
medium, `wisps` fastest; `sun_glow` is a 1920×1040 overlay fixed to the camera.

## Writing a new shot

```python
from ..layers import Painting
from ..noise import rng_for
from ..forest import forest_row, giant, floor
P = Painting('S99', 1920, 1040, 48, outdir); rng = rng_for('S99')
cv = P.layer('far', 0.2)
forest_row(cv, rng, -80, 2000, 760, -120, 14, 0.75, HAZE, L3, SUN2, mist_col=HAZE_W, mist_band=(500, 770))
P.add('far', 0.2, cv, 'note')
...
P.save(sun=[x, y])
```

Conventions: `L3 = (sx, sy, z)` points toward the sun in image space (x right, y down;
z < 0 = backlit rims, z > 0 = front light); `SUN2` is its 2-D part; `HAZE`/`HAZE_W`
are the aerial-perspective colours; depth `d` 0..1 drives aerial perspective.

## Known weaknesses (honest)

- Foliage is the strongest element; it can still read as clustered "broccoli" in
  large dark masses (S01 crowns). S11 was repainted in round 5 with flat-plane masses lit
  toward the gap (radial light via `paint_planes(G=..., glob=0, rim_point=...)`).
- Bracket fungi (S08/S09) are simple stacked ellipses; knot holes read slightly cartoonish.
- Round 4 replaced every dab-built cloud with flat value planes (`plane_cloud`):
  S00, S01, S03, S06, S10, S16, S16A. The old dab painter is kept only for reference.
- The plane-painted canopies (S00 mid/near, S16 fg) are clean but simple: no inner
  branch gaps or individual crown structure.
- Floors in the backlit/flat views (S12, S08 centre) are mostly texture + light
  patches; they lack designed shapes (puddles, paths, root systems).
- Trunk bark is convincing at mid scale; at full scale on the near giants the
  stroke texture is uniform and the ivy is a dense, even net in places.
- S13 (top-down) trunk bases leaning toward camera read only weakly as trunks.
- Everything is hand-tuned per shot; the kit has no automatic composition checks
  (value/contrast maps), only my visual review at full resolution.
