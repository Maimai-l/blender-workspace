# Qiting (旗亭) replica

A script-built Blender replica of 旗亭, the round double-eaved pavilion on the hill in 大唐芙蓉园 (Xi'an), and, from round 2, its surroundings.

- **Round 1 (2026-11-01): the building.** The pavilion (two round roofs and the gilded finial; the eaves with rafters and bracket sets; columns and bases; the upper drum; the plaque and couplets), the podium (carved drum, plinth, terraces, balustrade), the north stair and the paved plaza.
- **Round 2 (2026-11-07): the surroundings.** The hill and lawns, paths and garden stairs, the lake with its lakeside walk, the planting, lamps, sculptures and plaza furniture, and the far scene across the lake: the island, 紫云楼, boats, hall groups, housing and the city, with distance haze. At the user's request the figure carving on the podium drum was softened. Round 2 also corrected the stair and the terraces and fixed two camera errors in the round-1 comparison renders. See [Round 2](#round-2-the-surroundings).

## Deliverables

All on the PC, in `D:\Blender\Projects\qiting\` (moved from `C:\Users\blender\Documents\qiting\` on 2026-11-11; the old path is a junction to it):

| What | Where |
| --- | --- |
| Blender file | `qiting.blend` (Blender 5.2.3; Cycles on the GPU; AgX Medium High Contrast) |
| Comparison renders from the calibrated cameras (7: the five photos and, from round 2, the aerials A1 and A2) | `交付\对照渲染\`. The file holds the cameras `CAM_对照_*` |
| Reference and render side by side, plus 50 % overlays | `交付\并排对比\` |
| Beauty shots (10, 1920×1080; round 2 re-rendered the six of round 1 with the surroundings and added four) | `交付\效果图\`. The file holds the cameras `CAM_效果_*` |
| Dimension table | [`docs/dimensions.md`](docs/dimensions.md) (also `交付\尺寸表.md`) |
| These notes | `交付\说明.md` (this file) |

Copies of the side-by-sides and beauty shots are in [`deliverables/`](deliverables/).

## Scene structure

**Collections by part**, as asked:

- `屋面`: roof decks, tiles, collar, finial;
- `檐下`: rafters, fascia boards, purlins, plaster bracket bands, bracket sets, ceiling, painted caisson;
- `柱与墙身`: columns, bases, architrave, lattice frieze, upper drum with windows, inner wall;
- `台基`: floor, coping, carved drum, plinth, terraces;
- `台阶与栏杆`: podium balustrade, stair, stair walls and balustrades;
- `匾联`: plaque and couplets;
- `地面`: plaza setts, pale band, curb, joint bed.

**Round 2 collections:**

- `地形`: the terrain of the surveyed site (0.5 m grid) and the land round it;
- `地面` (extended): paths, the pink promenade, the lakeside walk, the garden stairs, the plaza bed and kerb;
- `水体`: the lake surface, the revetment, the lakeside railing, the viewing platform;
- `植物`: trees, shrubs, lawn grass, clipped hedges;
- `灯具与小品`: lamps, the plaza's stone tables, egg stones, bronzes and sign, the 丽人行 sculptures, the golden gate, the sightseeing cart;
- `远景`: everything beyond the surveyed site: far land, island, far planting, 紫云楼, boats and dock, hall groups, housing, the city.

**Helper collections:**

- `灯光与相机` holds the sun and the cameras.
- `_LIB` holds the hidden instance sources, including the tree templates and their viewport proxies.
- Round 1's `临时背景（非复刻内容）`, a flat stand-in ground, was removed in round 2.

**Frame:**

- Origin on the pavilion axis at the podium floor (Z = 0).
- +Y is north, toward the stair and the entrance. +X is east.
- The plaza is at Z = −4.80 m.

**Instancing.** These are all instanced with geometry nodes (`XY_Instancer`):

- tiles: 4,800 cover, pan and eave tiles;
- rafters: 832, in two layers;
- columns and bases;
- bracket sets;
- balustrade posts and bays;
- the 103,642 plaza setts.

Viewport load is listed under "Checks".

**Real geometry, no textures standing in for it:**

- The carved drum is a displaced mesh with a 2 cm grid. Its raised border, the figures and the features are 2–11 cm deep.
- Every coping block, floor slab, step and terrace-top slab is its own bevelled solid, with its own tone.
- Materials are procedural and include wear: grime in crevices, rain streaks on the plaster, per-tile tone, fading on the lacquer.
- No photo is projected onto anything.

## How it is built

The scripts are in [`scripts/`](scripts/), the library in [`scripts/lib/`](scripts/lib/).

The library modules:

- `qt_dims.py`: every dimension;
- `qt_roof.py`: round roofs, tiles, rafters, finial;
- `qt_frame.py`: columns, frame, brackets, upper drum, boards;
- `qt_podium.py`: podium, relief, terraces, balustrades, stair;
- `qt_ground.py`: plaza;
- `qt_mats.py`: materials.

These were reused from `xingyuan/scripts/lib`:

- `xy_core.py`: mesh builder and instancer;
- `xy_roof.py`: tile sources;
- `xy_parts.py`: bracket and column helpers;
- `xy_props.py`: text meshes;
- `xy_mats.py`: shader helpers;
- `xy_light.py`: sky, sun, render settings.

Round 2 added:

- `env/make_env.py` (run in the cloud session): builds the site layout from the DWG, the master plan and the aerials, and writes `scripts/lib/qt_env_data.py` and `qt_env_grid.py`;
- `qt_env.py`: terrain, paving, stairs, lake, planting, lamps, furniture, sculptures, gate and cart;
- `qt_far.py`: the far scene;
- `qt_haze.py`: distance haze in the compositor;
- `xy_plants.py`, copied from Xingyuan: trees, willows, shrubs and grass.

To rebuild:

1. Copy `scripts/lib/*.py` to `C:\Users\blender\Documents\qiting\lib\` (`tools/push.py` does this).
2. Run `scripts/build_all.py` with `STEPS = ['all']` for the building. The steps are `mats`, `roof`, `frame`, `podium` and `boards`. Each step deletes its own objects and builds them again; the whole build takes about 6 s.
3. Run `scripts/build_env.py` with `STEPS = ['all']` for the surroundings. The steps are `mats`, `terrain`, `paving`, `lake`, `plants`, `lamps`, `furniture` and `far`; together they take about 15 s.
4. Render with `tools/cmpview.py` (the comparison views, using the solved cameras in `tools/cal/*_sol.json`) and `tools/heroes_run.py` (the beauty shots in `lib/heroes.py`). Both render from a Blender timer and wait through exec, because full-scene renders outlast the ~100 s limit of the Blender endpoint; see `tools/README.md`.
5. Run `scripts/finalize.py` to rename the cameras, set the default daylight and save.

The geometry checks are `scripts/check_overlap.py`, `scripts/check_normals.py` and `scripts/check_poke.py`.

The helper tools are described in [`tools/README.md`](tools/README.md).

## Sources and calibrated views

The references are 19 photos, a video, the master-plan PDF, a DWG screenshot and 8 web photos. [`refs/README.md`](refs/README.md) lists them and the downscaled copies kept in the repo.

**Plan.** Plan sizes come from the DWG screenshot. It was scaled at 0.245 m/px by registering it to the 1:1500 master plan.

**Heights and details.** These come from web photo W02, an almost orthographic view from 214 m. Its solved focal length agrees with the EXIF value to 1 %.

**Cameras.** Five reference cameras were solved with `tools/calq.py`, a pinhole fit to silhouette tips and points. Each was then rendered and compared:

| View | Photo | What it shows | Camera | Fit |
| --- | --- | --- | --- | --- |
| 侧面 | W02 (web 02, Canon SX610 at 19.3 mm) | East side, stair in profile | Azimuth 15°, 214 m, z +6.3 m. f = 16,046 px; EXIF gives 16,216 | 4.8 px rms on a 5184 px image |
| 西侧 | 340d (morning sun) | West side, stair going down to the left | Azimuth 170°, 66 m, z −5.6 m (on the lawn below the plaza) | 5.7 px rms on 5712 px |
| 近景仰视 | W01 (web 01, SX610 at 13.2 mm; f fixed from EXIF) | Low close view of the relief, eaves and finial | Azimuth 177°, 48 m, z −7.3 m | 16 px rms on 5184 px |
| 台阶正面 | af3b (phone) | Looking up the stair at the plaque and couplets | Azimuth 90°, about 15 m, z ≈ 0 | 18 px rms on 4096 px. **Weak**: see below |
| 傍晚（有人物） | 419 (dusk, with people) | West plaza, people for scale | Azimuth 166°, 27 m, eye height 1.45 m above the plaza (fixed). f = 837 px (ultra-wide) | 10.9 px rms on 1702 px |
| 航拍 A1 (round 2) | Drone aerial A1 | The whole site and the far scene, looking south | 71 m north, 29 m up; f = 1,263 px | 1.9 px rms near; far points from the master plan |
| 航拍 A2 (round 2) | Drone aerial A2 | As A1, from higher | 71 m north, 40 m up; f = 1,161 px | Edge fit 2.2 px; far points from the master plan |

**Notes on the cameras:**

- The W01 and 340d cameras stand below the plaza, on the hillside. In round 1 their comparison renders hid the plaza and the stand-in ground. From round 2 the hillside is modelled and nothing is hidden; but W01 and W02 date from 2019 (EXIF) and 340d is undated, and the trees round the plaza have grown since, so their comparisons leave out the planting between the camera and the building (`cmpview.py --thin`).
- **Correction in round 2:** the round-1 comparison renders were turned by twice each camera's roll (the camera helper applied the roll with the wrong sign). That was 6° for 419 and 2° for 340d, and under 1° for the others. The measurements were unaffected, since they were made in Python. All comparisons were rendered again.
- The dusk view is rendered with a low evening sun (bearing 292°, 4° elevation). Its reference was taken on an overcast evening, and the people in it are not modelled.
- **af3b:** no single pinhole camera on the stair fits this phone photo better than about 18 px rms. The fits that agree with the pavilion put the camera about 15 m out and level with the podium floor. That is inconsistent with standing on the stair, so the photo is probably cropped, or its lens is not what the EXIF says. Its comparison is useful for the eave, brackets, plaque and couplets, not for the stair.

## What is inferred (round 1)

1. **Back and top.** No photo looks down on the roofs. The tile layout follows W01, W02 and af3b: about 0.30 m pitch at the eave, with rows halving near the top. The north (entrance) side was copied round the back, except where photos show otherwise: the south panel, the windows, and the doors in the stair walls.
2. **Bracket sets.** The cloud-ended arms, cap blocks, projecting arm and beam end are read from W01 and af3b at low resolution. Exact block sizes are estimated.
3. **Interior.** The ceiling ring and the painted caisson follow the one interior photo, W08. Its painting is procedural: red rosette, green ring, yellow petals and a salmon band, as in W08. It is not a copy of the original pattern.
4. **Relief.**
   - Where things are: the carved gate building, the two round medallions, the two lettered cartouches, the south panel and the windows are placed where the solved cameras put them (W01, W04, 340d, W02).
   - What the figures are: the photos show groups of standing and dancing figures in long robes with flying ribbons, but poses and faces cannot be read. So the figures are robed masses with heads, sleeves and ribbons, spaced and sized as in the photos. They are not invented scenes.
   - The cartouche and medallion characters are not legible in any photo and are left blank.
5. **Stair.**
   - Round 1's riser count per flight (10/11/12) and its 2.4 m clear width were replaced in round 2: 1.6 m clear, 34 risers in flights of 10/11/13 (see `docs/dimensions.md`).
   - The doors next to the drum: one is seen on each side, both small dark openings.
6. **Plaza.**
   - The outer edge (29.5 m) and the pale band come from the DWG. The pale band follows the lobed inner line.
   - Round 1 kept the plaza flat; round 2 lets it fall 0.2 m toward the stair foot, as W02 shows.
   - The DWG's planting pockets are paved, as the aerials show; the spotlights at the terraces were added in round 2.
7. **Colours.** The photos are graded: hazy blue W02, warm 340d, blue dusk 419, grey overcast af3b. Natural daylight colours were chosen instead:
   - warm cream marble;
   - vermilion lacquer, with darker oxblood on the brackets and rafters;
   - off-white lime plaster;
   - mid-grey clay tiles;
   - grey granite ashlar;
   - dark grey granite setts;
   - gold leaf on the finial.

## Remaining differences from the references (round 1)

1. **Plaque and couplet text.**
   - Plaque: 旗亭, read right to left, as in af3b.
   - Couplets: only four characters per board can be read (時有落花 / 遠聞流水). The fifth is hidden behind the balustrade in every photo and is left blank.
   - The small inscriptions beside the characters are not legible and are left out.
2. **Relief detail.** The carving in the photos is denser and finer, with drapery folds and faces. The model reproduces where things are, their relief depth and the overall rhythm of figures, not the exact figures.
3. **Stair foot and plaza level.** In round 1 these differed by up to about 0.2 m from W02, because the plaza was flat; fixed in round 2.
4. **af3b view.** Only the upper half matches well; see the camera notes above.
5. **No hillside** in round 1; modelled in round 2.

## Round 2: the surroundings

### What was asked

Two drone aerials, A1 and A2, came with the request: continue with the pavilion's surroundings, and soften the stone relief round the podium. The relief's small figures could not be read in any photo, and the round-1 version looked comical.

### The relief

The figure field of the carved drum is now blurred: a 6 cm Gaussian, the relief capped at 4.5 cm, with a fine drapery-fold texture on top. It reads as weathered, crowded carving with no faces or poses to get wrong. The frames, the gate building, the medallions and the cartouches stay crisp, as in the photos.

### How the site was measured

- **Plan.** The DWG gives the plaza outline, the paths and stairs, the lakeside walk, the planting pockets and 54 spot heights. The terrain is a thin-plate fit to the spot heights, relaxed so that it meets the paving. The master plan (1:1500, scale bar checked in round 1) gives the lake, the island and 紫云楼.
- **Aerials.** A1 and A2 were calibrated like the photos (see the table above and `docs/dimensions.md`). They were then used three ways:
  - orthorectified onto the ground, with the DWG drawn over them, to check the path layout and read the planting;
  - by casting rays from known pixels into the terrain, for the golden gate, the sightseeing cart, the hedges and the sculptures;
  - by casting rays into vertical planes, for 紫云楼's heights and widths.
- **The far field.** The aerials' near points fix each camera well but not its focal length. A longer lens farther back fits the pavilion almost as well, and that choice moves everything far away: A1 calibrated on near points alone put 紫云楼's terrace 450 m south of the pavilion instead of the master plan's 270 m.
  - So both solves also use far points from the master plan.
  - The focal lengths that result (1,161 and 1,263 px) were checked against the skyline: with much longer lenses the true horizon would sit above the tops of the city's towers.
  - The skyline's vertical edges set A1's roll.
- **紫云楼** was measured on both aerials. They agree on its depth and heights but differ by 7 m on its axis, so the model sits between them (plan −7 m, A1 −8 m, A2 0 m).

### What is inferred (round 2)

1. **Planting.** The aerials show the species mix and density per area, not individual trees: a dense deodar wood north of the plaza, a grove of small round trees east of it, lawns with groups of trees east and west, willows along the walk. Trees are scattered at those densities, so no single tree is where its counterpart stands.
2. **Lamps** are of the four kinds the photos show. They are spaced along the paths, not surveyed.
3. **The far scene** is built to read correctly at 300 m and beyond:
   - generic Tang-style hall groups;
   - streets of hipped-roof houses where A2 shows the grey-roofed housing;
   - long white blocks south-east of the lake;
   - mid-rise and high-rise compounds for the city, with heights set by the horizon check.
   None of it is surveyed.
4. **紫云楼's detail** (bracket bands, windows, the flying galleries' arches) is generic. Its masses, heights and positions are measured.
5. **Terrain away from the spot heights**, and everything outside the DWG, is smooth and generic.
6. **Colours.** Lawns, foliage, water and haze were matched to A2's colours in a few sampled regions, not to a colour chart.

### Remaining differences (round 2)

1. **Trees.** The deodars read correctly from above (A1, A2), and the round heads of the broadleaf trees are close. Individual crowns are more regular than the real ones, and the tree-by-tree layout differs, as noted above.
2. **Lake.** The water reflects the far shore a little more clearly than in A1/A2, where the surface is more broken. Its tone is close.
3. **Sky.** The sky stays greyer than the photos' pale blue.
4. **City.** The towers are generic boxes with window bands. They read right through the haze, but the skyline's individual buildings are not reproduced.
5. **W01, W02 and 340d** predate the aerials (W01 and W02 by seven years). Their comparisons leave out the planting between the camera and the building; with today's planting the stair is hidden behind the deodars in W02's view.
6. **W01** still has the round-1 inconsistency: its camera solves 2.5 m below the plaza, so the plaza edge hides the foot of the podium a little.

### Notes on the renders

- **Instancing.** The tree templates scatter their leaves as instances. Instancing those templates again for the 28,800 far trees overflowed the GPU's acceleration structure (OptiX ran out of memory). The far trees use single-mesh copies of the templates with the leaves realized: 40 % of the leaves enlarged 1.5×, or 18 % enlarged 2.1× for the leaf-heavy deodars and willows. In the viewport they show as low-poly crowns.
- **Render time.** Full-scene renders take about 7–45 s on the RTX 5070 Ti. That is too long for a reply from the Blender endpoint, which the tunnel cuts at about 100 s, so they run from a Blender timer and report through a file (`tools/README.md`).

## Checks

Run on the final model of round 2, after the last change (the scripts run from a Blender timer through `tools/rdefer.py`):

- **Normals:** 3,311 closed shells, 0 inside out. Both roof decks face up.
  - The first run found 8 inside-out shells: the swept iron rails of the lakeside railing and the viewing platform. Their builders now recalculate normals.
- **Poke-through:** 0 points of any non-roof part or instance rise above a roof deck, out of 18,132 tested. The hidden tree templates, which sit at the origin and never render, are left out.
- **Coplanar overlap (flicker risk):** 8 object pairs remain.
  - The round-1 gold 回 ornaments under the plaque: same material, cannot show.
  - Inside 紫云楼, at 270 m and more: 154 + 115 faces between stacked boxes of its base and halls, 14 between the balcony floors and the podium top, 32 between the top roof and its ridge.
  - 2 hedge faces, 1 city face, 1 path face.

  Fixed in round 2:
  - the paths' and promenade's side faces were wound inward and lay in the plane of the kerbs (6,657 and 1,674 faces);
  - the garden steps were flush with their cheek walls;
  - the extra steps at the stair foot overlapped one another.
- **Renders:** no flicker or gaps were seen in the comparison renders or beauty shots. A full-scene render takes about 7–45 s.
- **Viewport load:** 5.5 M triangles and 108,000 instances in the viewport depsgraph, not counting the hidden sources. The 28,800 far trees show as low-poly crowns, the grass at 1 %, the setts as one-quad proxies.
- **File:** `qiting.blend` is 240 MB. Most of it is the realized far-tree templates (2.3 M faces), the terrain and the far land.
- **Not done:**
  - the real viewport frame rate on the PC was not measured;
  - no walk-through or animation test;
  - the haze, lawn and foliage colours were matched to A2 in sampled regions only.

## Note on the Blender MCP connection

On 2026-11-01 the cloud endpoint for Blender stopped working early in this session. A fetch of an 11 MB response made the Blender MCP server exit, and nothing restarted its proxy.

All the work in this session went through the exec server instead:

- `tools/pcx.py` sends code to Blender's add-on socket on the PC with `tools/pc/brelay.py`.
- It copies files with `tools/pc/pack.py`.

On 2026-11-07, with the user's consent, Blender was started on the PC and the Blender MCP service was started again. Both went through the exec server:

- Blender was launched the way the PC's agent launches it, and the add-on's socket started by itself.
- The service was started by a request to the agent on the PC, `POST /mcp/blender/start`, authenticated with its local token.

The cloud endpoint answers again. `tools/bmcp.py` now uses the endpoint first and falls back to the exec route when the endpoint is down.

In round 2, replies longer than about 100 s came back as "No data received", because the tunnel in front of the endpoint drops them. Long renders and checks therefore run from a Blender timer and report through a file on the PC, which the session polls through exec (`tools/README.md`, "Long jobs").
