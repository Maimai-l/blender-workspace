# paint - procedural hand-painted anime backgrounds

Gouache-style forest textures for flat cards in Blender (Ghibli / Kazuo Oga
look: opaque dabs, visible brushwork, dawn palette, atmospheric perspective).
Pure Python: numpy, scipy, Pillow, OpenCV. No internet, no photo sources.

## Regenerate

    cd awakening/paint
    python3 make_all.py            # everything into out/, 4 worker processes
    python3 make_all.py -j 2       # fewer processes
    python3 make_all.py --only tree_fg   # one family (substring match)
    python3 make_all.py --list     # asset table

A full run takes about 40 s on 4 cores (the slowest single asset is the sky at
~25 s). Everything is deterministic: each asset seeds its generator from its
file name (`brush.rng_for`, crc32), so a rerun reproduces the same pixels.

## Files (out/)

| file | size | notes |
|---|---|---|
| `tree_fg_1..3.png` | 2048x3072 RGBA | huge old broadleaf trees, trunk base at bottom centre; moss, bark, vines |
| `tree_mid_1..4.png` | 1024x1536 RGBA | middle-distance trees, simpler clumps, lighter and cooler (depth 0.22) |
| `forest_far_1..3.png` | 4096x1024 RGBA | far forest bands; 1 nearest, 3 farthest; sky transparent above, bottom edge fully opaque |
| `canopy_fg_1..2.png` | 2048x1024 RGBA | backlit foliage hanging from the top edge (top row opaque), warm rim light |
| `ground_tile.png` | 2048x2048 RGB | seamless forest floor: moss, leaf litter, roots, stones, wildflowers |
| `moss_patch_1..3.png` | 768x768 RGBA | soft-edged velvety moss patches (3 hue variants) |
| `grass_clump_1..3.png` | 512x512 RGBA | grass (1, 3) and fern (2) clumps, base at bottom centre |
| `flower_1..3.png` | 256x256 RGBA | wildflower clusters: white, pale yellow, pale violet |
| `leaf_1..6.png` | 256x256 RGBA | single leaves: broadleaf / lobed / elongated in green, ochre, brown, rust |
| `dust_1..2.png` | 512x512 RGBA | cel-style dust/soil puffs (lumps with darker undersides) |
| `sky_dawn.png` | 4096x2048 RGB | dawn gradient, streaky brush texture, cloud wisps lit from below |
| `contact_sheet.jpg` | ~1900x2200 | thumbnails of everything over mid grey |

RGBA files have straight alpha with colour bled under the transparent pixels, so
bilinear filtering / mipmaps in Blender show no dark fringes. Use them with alpha
blend (or alpha hashed) on emission or diffuse cards.

## Modules

- `brush.py` - the painting library. Premultiplied float RGBA `Canvas`;
  `dabs()` stamps thousands of elliptical bristle dabs in one vectorised call
  (ragged edge noise, bristle streaks, per-dab colour jitter in Oklab);
  `stroke()` renders one continuous stroke along a polyline with width profile,
  bristle texture and light-aware cylinder shading; `clump()` is the foliage
  clump painter (dark base mass -> edge leaf fans -> mid leaf clusters grouped
  in patches -> lit clusters -> pale tips, all driven by one "lit value" field);
  `clump_cluster()` groups clumps into a lump; `paper_grain()`, `save_rgba()`
  (with alpha bleed), colour helpers `mix/shade/jitter/atmos` (Oklab) and
  tileable noise.
- `trees.py` - trees: canopy-first construction (lumps on an envelope that fits
  the canvas, limbs grown from the trunk toward the lumps), big-form lighting
  (top-right lit, lower-left shadow, back lumps darker), trunk/limb painter with
  bark streaks and moss patches, root flare, hanging vines. `fg_spec()` /
  `mid_spec()` are the presets; `TreeSpec` has all knobs.
- `forest.py` - far strips (rows of canopies + spires/emergents, mist fade) and
  the overhanging canopy (backlit, rim light along the lower silhouette).
- `ground.py` - tileable ground (the canvas `wrap=True` makes dabs and strokes
  wrap), moss patches, grass/fern clumps, flowers.
- `sprites.py` - leaves (outline mask filled with directional strokes, dark half,
  lit margin, veins) and dust puffs.
- `sky.py` - sky gradient in Oklab, horizontal low-opacity strokes, lens-shaped
  streaky clouds with gold undersides.
- `make_all.py` - asset table, worker pool, contact sheet.

## Extending

- A new foliage colour: `make_palette(shadow, mid, lit, tip, depth, cool)`;
  `depth` applies atmospheric perspective (toward warm/lavender mist).
- A new tree variant: copy `fg_spec`, change the palette tuple, `lean`,
  `n_top/n_inner/n_low`, `lump_r`; `paint_tree(cv, rng, spec)`.
- Light direction is `LIGHT = (0.62, -0.78)` (toward the sun, upper right) in
  each module; `clump(light=...)` and `stroke(light=...)` take it directly.
- Everything takes an explicit `numpy.random.Generator`; use `rng_for(name)`.
