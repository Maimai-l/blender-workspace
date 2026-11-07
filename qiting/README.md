# Qiting (旗亭) replica — round 1: the building

A script-built Blender replica of 旗亭, the round double-eaved pavilion on the hill in 大唐芙蓉园 (Xi'an).

This round covers:

- **The pavilion:** the two round roofs and the gilded finial; the eaves with their rafters and bracket sets; the columns and their bases; the round upper drum between the two eaves; the plaque and the couplets.
- **The podium:** the carved drum and plinth, the three terraces, and the balustrade on top.
- **The north stair:** its three flights, side walls and balustrades.
- **The paved plaza** at the foot of the podium.

The hill, lawns, trees, lamps, sculptures, paths, the lake and distant buildings are left for round 2.

## Deliverables

All on the PC, in `C:\Users\blender\Documents\qiting\`:

| What | Where |
| --- | --- |
| Blender file | `qiting.blend` (Blender 5.2.3; Cycles on the GPU; AgX Medium High Contrast) |
| Comparison renders from the calibrated cameras (5) | `交付\对照渲染\`. The file holds the cameras `CAM_对照_*` |
| Reference and render side by side, plus 50 % overlays | `交付\并排对比\` |
| Beauty shots (6, 1920×1080) | `交付\效果图\`. The file holds the cameras `CAM_效果_*` |
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

**Helper collections:**

- `临时背景（非复刻内容）` holds a flat neutral ground so renders don't float. It is not part of the replica and will be replaced by the hill in round 2.
- `灯光与相机` holds the sun and the cameras.
- `_LIB` holds the hidden instance sources.

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

To rebuild:

1. Copy `scripts/lib/*.py` to `C:\Users\blender\Documents\qiting\lib\` (`tools/push.py` does this).
2. Run `scripts/build_all.py` with `STEPS = ['all']`. The steps are `mats`, `roof`, `frame`, `podium`, `ground` and `boards`. Each step deletes its own objects and builds them again; the whole build takes about 6 s.
3. Render with `scripts/render_view.py` (one view) or `scripts/render_heroes.py` (cameras in `lib/heroes.py`). The comparison views come from `tools/cmpview.py`, using the solved cameras in `tools/cal/*_sol.json`.
4. Run `scripts/finalize.py` to rename the cameras, set the default daylight and save.

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

**Notes on the cameras:**

- The W01 and 340d cameras stand below the plaza, on the hillside, which is not modelled this round. Their comparison renders hide the plaza and the temporary ground so the podium shows.
- The dusk view is rendered with a low evening sun (bearing 292°, 4° elevation). Its reference was taken on an overcast evening, and the people in it are not modelled.
- **af3b:** no single pinhole camera on the stair fits this phone photo better than about 18 px rms. The fits that agree with the pavilion put the camera about 15 m out and level with the podium floor. That is inconsistent with standing on the stair, so the photo is probably cropped, or its lens is not what the EXIF says. Its comparison is useful for the eave, brackets, plaque and couplets, not for the stair.

## What is inferred

1. **Back and top.** No photo looks down on the roofs. The tile layout follows W01, W02 and af3b: about 0.30 m pitch at the eave, with rows halving near the top. The north (entrance) side was copied round the back, except where photos show otherwise: the south panel, the windows, and the doors in the stair walls.
2. **Bracket sets.** The cloud-ended arms, cap blocks, projecting arm and beam end are read from W01 and af3b at low resolution. Exact block sizes are estimated.
3. **Interior.** The ceiling ring and the painted caisson follow the one interior photo, W08. Its painting is procedural: red rosette, green ring, yellow petals and a salmon band, as in W08. It is not a copy of the original pattern.
4. **Relief.**
   - Where things are: the carved gate building, the two round medallions, the two lettered cartouches, the south panel and the windows are placed where the solved cameras put them (W01, W04, 340d, W02).
   - What the figures are: the photos show groups of standing and dancing figures in long robes with flying ribbons, but poses and faces cannot be read. So the figures are robed masses with heads, sleeves and ribbons, spaced and sized as in the photos. They are not invented scenes.
   - The cartouche and medallion characters are not legible in any photo and are left blank.
5. **Stair.**
   - The riser count per flight (10/11/12) follows the landing heights at a 0.145 m riser. af3b shows at least 12 steps in the top flight, so the top flight may have one or two more, smaller steps.
   - The doors next to the drum: one is seen on each side, both small dark openings.
6. **Plaza.**
   - The outer edge (29.5 m) and the pale band come from the DWG. The pale band follows the lobed inner line.
   - The plaza is flat. The photos suggest it falls about 0.4 m toward the stair foot.
   - The DWG's planting pockets and spotlights are round-2 items.
7. **Colours.** The photos are graded: hazy blue W02, warm 340d, blue dusk 419, grey overcast af3b. Natural daylight colours were chosen instead:
   - warm cream marble;
   - vermilion lacquer, with darker oxblood on the brackets and rafters;
   - off-white lime plaster;
   - mid-grey clay tiles;
   - grey granite ashlar;
   - dark grey granite setts;
   - gold leaf on the finial.

## Remaining differences from the references

1. **Plaque and couplet text.**
   - Plaque: 旗亭, read right to left, as in af3b.
   - Couplets: only four characters per board can be read (時有落花 / 遠聞流水). The fifth is hidden behind the balustrade in every photo and is left blank.
   - The small inscriptions beside the characters are not legible and are left out.
2. **Relief detail.** The carving in the photos is denser and finer, with drapery folds and faces. The model reproduces where things are, their relief depth and the overall rhythm of figures, not the exact figures.
3. **Stair foot and plaza level.** These differ by up to about 0.2 m from W02, because the plaza is modelled flat.
4. **af3b view.** Only the upper half matches well; see the camera notes above.
5. **No hillside.** Views from below the plaza, like W01 and 340d, need the hill from round 2 to look right.

## Checks

Run on the final model:

- **Normals:** 1,135 closed shells, 0 inside out. Both roof decks face up.
- **Poke-through:** 0 points of any non-roof part or instance rise above a roof deck, out of 18,130 tested.
- **Coplanar overlap (flicker risk):** one pair remains: the small gold 回 ornaments under the plaque characters are built from overlapping strips. Both strips are the same gold material, so it cannot show. Everything else is 0. Tiles overlap obliquely by design and cannot be coplanar.
- **Renders:** no tile flicker or gaps were seen in the comparison renders and beauty shots.
- **Viewport load:** 1.07 M triangles and 109,401 instances in the viewport depsgraph. In the viewport the plaza setts are one-quad proxies; renders use the full bevelled setts. Without the proxies the setts alone were 2.0 M triangles.
- **Not done:**
  - the real viewport frame rate on the PC was not measured (only triangle and instance counts were taken);
  - no animation or walk-through test.

## Note on the Blender MCP connection

On 2026-11-01 the cloud endpoint for Blender stopped working early in this session. A fetch of an 11 MB response made the Blender MCP server exit, and nothing restarted its proxy.

All the work in this session went through the exec server instead:

- `tools/pcx.py` sends code to Blender's add-on socket on the PC with `tools/pc/brelay.py`.
- It copies files with `tools/pc/pack.py`.

On 2026-11-07, with the user's consent, Blender was started on the PC and the Blender MCP service was started again. Both went through the exec server:

- Blender was launched the way the PC's agent launches it, and the add-on's socket started by itself.
- The service was started by a request to the agent on the PC, `POST /mcp/blender/start`, authenticated with its local token.

The cloud endpoint answers again. `tools/bmcp.py` now uses the endpoint first and falls back to the exec route when the endpoint is down.
