# Mana cafe (玛娜茶金观景台咖啡厅)

A photographic still of the cafe on the Manachajin ridge beside Yading, rendered in Blender 5.2 (Cycles) from the
SketchUp model `玛娜茶金总图咖啡厅.skp`. Everything around the building is rebuilt by the scripts in this folder.

![preview](renders/mana_cafe_preview.jpg)

## Files on the PC (`D:\Blender\Projects\mana_cafe\`)

| File | What it is |
| --- | --- |
| `renders\mana_cafe_final_4k.png` | the final image, 3840 × 2160 |
| `mana_cafe_final.blend` | the final scene (textures stay in `assets\`, paths are relative) |
| `mana_cafe.blend` | the SketchUp import, untouched |
| `mana_cafe_work.blend` | the working file |
| `assets\fab\` | render-sized copies of the Megascans textures from `D:\fab_downloads`, and `manifest.json` |
| `assets\ph\`, `assets\hdri\` | Poly Haven assets (CC0): the fir trees and the sky `waterkloof_farm` |
| `dem\` | Copernicus GLO-30 tile and the processed terrain rasters and meshes |

## What is in the picture

- **Building**: as modelled. Its materials are rebuilt (`lib/mc_building.py`) and warm lamps are added inside. One
  piece of geometry is added on request: `Door frame (added)`, a steel surround with real depth round the entrance.
- **Terrain**: Copernicus 30 m elevation, registered to the SketchUp geo-location (`proc/terrain_lib.py`), with
  synthesised relief and stream-power erosion (`proc/far_build.py`). The ground within 3 km of the cafe is the real
  ridge; beyond 6 km it is the real Yading massif, moved from 30 km to 10.8 km (`proc/composite.py`) so that the
  peak is the focus of the frame. Snow, rock, scree, turf and forest floor are shaded from terrain masks
  (`lib/mc_mats.py`).
- **Megascans** (from `D:\fab_downloads`, imported by `lib/mc_fab.py`):

  | Asset | Use |
  | --- | --- |
  | Tundra Rocky Ground × 2, Grassy Soil | ground of the first 500 m: box-projected, blended by their height maps; the two 3D ground scans are baked top-down into tiles first (`bake_ground.py`, `proc/fab_seamless.py`) |
  | Gravel Ground | terrace surface and the rutted track |
  | Wild Grass, Tundra Grass, Tufted Grass, Dry Grass, Yellow Flower | turf between the shrubs, in drifts (`lib/mc_ground.py`) |
  | Dwarf Birch, Dwarf Willow, Lingonberry | the dark low shrub cover |
  | Tundra Boulder × 2, Tundra Stone, Massive Tundra Rock Formation | rock: hand-placed groups in the foreground, rule-based scatter in the middle distance (`lib/mc_rocks.py`) |
  | Mossy Stone Wall | retaining walls, bent along the terrace outline (`lib/mc_stone.py`) |
  | Worn Wooden Planks | boardwalk |
  | Rusty Metal, Wall Rust Leakage × 2 | corten skin and the streaks below its seams |
  | Plain Wool Fabric, Furniture Fabric | bean bags (cloth-simulated, `lib/mc_beanbag.py`) |
  | Granite Cliff | crags on the valley flank, 1.4 km away |

  Not used in the final frame: Fresh Snow, Snowy Ground (no snow lies within the first kilometre of this view) and
  Japanese Stone Wall (`build_site.py` takes `WALL='jp_wall'` to swap it in).
- **Light and sky**: a sun lamp (azimuth 116°, 28.6° high: a mid-October morning) and a photographed sky. The sky the
  camera sees is graded apart from the sky that lights the scene. Air between camera and mountains is a shader
  (`aerial_group`). Cloud in the valley and on the peak is volumetric (`lib/mc_clouds.py`).
- **Grade**: in the file: AgX, High Contrast look, a tone curve, and a compositor step (saturation 0.82, slightly
  cool white balance), set by `lib/mc_light.py` (`render_settings`, `grade`).

## Rebuilding

The scripts run from the cloud session through the tools in `tools/` (see `tools/README.md`).

```bash
tools/pyrun.py scripts/proc/fab_prep.py          # texture copies and manifest
tools/pyrun.py scripts/proc/far_build.py far_hi  # then far_lo, near
tools/pyrun.py scripts/proc/mesh_far.py          # then mesh_near.py, trees.py
tools/rdefer.py scripts/build_fab.py             # Megascans meshes into the open .blend
tools/rdefer.py scripts/bake_ground.py && tools/pyrun.py scripts/proc/fab_seamless.py
tools/rdefer.py scripts/build_terrain.py         # then build_site, build_building, look, build_forest,
                                                 # build_scatter, build_rocks, build_clouds, build_bags
tools/rr.py name --scale 100 --samples 400 --res 3840x2160 --png
```

`tools/rr.py` leaves the scene at the resolution it was given: pass `--res 3840x2160` after any debug render, because
`lib/mc_rocks.py` reads the picture's aspect when it picks ground positions through the camera.

## Notes

- Nothing in the view is nearer than 30 m to the camera, so the 8K scans are used at 4K (ground bakes at 2K per
  2.4–3.7 m tile). The whole scene renders in about 6 GB of GPU memory.
- The terrain and tree materials carry an emission closure for the air. They are excluded from light sampling
  (`emission_sampling = 'NONE'`); otherwise the light tree of 7 M triangles overflows the GPU.
- Alpha-cut foliage must get the air *before* the transparent mix, or every card the ray crosses adds haze.
- Volume shaders: use object coordinates for a box's envelope; `Generated` is not usable there.
- Blender's display curve (`view_settings.curve_mapping`) acts on scene-linear values before the view transform.
