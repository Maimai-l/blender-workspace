---
name: blender-modeling-loop
description: Reference-locked Blender modeling loop (render, measure against references, repair, repeat, stop rules) and organic/character modeling references. Use when a model must match references, when repeated iterations are not converging, or for creatures/characters/organic shapes.
---

# Reference-to-3D Reconstruction

This skill is for **source-locked modeling**: the reference asset is the contract. Do not generate a plausible object from memory and then decorate it. Extract measurements, part counts, silhouettes, and UV regions from the supplied files first, then build the Blender model to satisfy those measurements.

## Triggered failure mode

If the user says the output does not match the templates/textures/wireframes, stop regular `text-to-blender` generation and enter this workflow. Repeated plausible-but-wrong renders usually mean the missing step is **reference analysis**, not another modeling iteration.

## Source-of-truth hierarchy

1. **Front template / front wireframe**: primary silhouette, visible part count, face/feature positions, brand read.
2. **Texture atlas**: exact part shapes, color/material boundaries, decals, lightmap/aura intent.
3. **Side/back/top views**: depth, stacking order, thickness, backside forms. They must not change the locked front projection.
4. **User feedback**: hard constraints; promote it into validation gates.

## Mandatory preflight checklist

Before Blender modeling, write a small `reference_manifest.json` with:

```json
{
  "source_files": [],
  "primary_view": "front",
  "expected_primary_parts": {"count": null, "labels": []},
  "structural_parts": [],
  "decorative_parts": [],
  "texture_regions": [],
  "validation_thresholds": {
    "front_mask_iou_min": 0.90,
    "bbox_center_tolerance_px": 12,
    "part_count_exact": true
  }
}
```

If the expected part count is unclear, derive it from the reference sheet with the analyzer and show the user the uncertainty instead of guessing.

## Pipeline

### 1. Inventory and classify sources

Classify each provided asset:

- `front_template`: hero brand image or front wireframe.
- `side_view`, `back_view`, `top_view`: orthographic depth references.
- `texture_atlas`: basecolor / albedo atlas containing pieces.
- `decal`: transparent face/expression or detail layer.
- `emissive`, `roughness`, `bump`, `normal`, `lightmap`: material maps.
- `aura/background`: optional visual context, not structural body geometry.

### 2. Analyze images locally

Use `scripts/template_analyzer.py` for first-pass component extraction:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/template_analyzer.py   --image /path/to/front_reference.png   --out /tmp/front_analysis.json   --mode edges  # use bright_on_dark/dark_on_bright/alpha when cleaner
```

The analyzer returns components with area, perimeter-derived score, bbox, centroid, contour, and approximate class hints. Use `--mode edges` for faint grey wireframes and Otsu modes for clean masks/atlases. Treat this as measurement input, not final authority.

### 3. Lock the front reference in Blender

Create a front reference plane or Image Empty in the same orthographic camera used for validation. Prefix it `REF_` and exclude it from export. Official Blender docs describe Image Empties as reference images/blueprints and support front/back depth, opacity, orthographic-only display, and axis-aligned display.

### 4. Build geometry from source contours

For each structural part:

1. Convert the 2D contour to front-view X/Z coordinates.
2. Generate a quad strip/grid inside that contour.
3. Assign Project-from-View-style UVs based on front X/Z bounds or exact atlas region.
4. Add only shallow Y-depth/crown/extrusion after the front silhouette is locked.
5. Keep part names semantic: `GEO-subject_part_top`, `GEO-subject_face_shell`, etc.

Do not radial-duplicate a mascot unless the reference is truly radial. Logos often have occlusion, intentional asymmetry, and a fixed visible part count.

### 5. Multi-view registration

- Front X/Z is locked first.
- Side view controls Y/Z depth envelope only.
- Top view controls X/Y spread only.
- Back view controls hidden/backside geometry and validation, not front silhouette.

If views disagree, keep the front brand read and document the conflict.

### 7. Validation gates before export

Always produce:

- `front_preview.png`
- `front_overlay_reference.png`
- `front_mask_validation.json`
- `side_preview.png`
- `back_preview.png`
- `top_preview.png`

Use `scripts/silhouette_validator.py`:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/silhouette_validator.py   --reference /tmp/reference_mask.png   --render /tmp/render_mask.png   --out /tmp/validation.json
```

Refuse final export if:

- primary part count differs from manifest;
- front-mask IoU is below threshold;
- face/feature centroid is outside tolerance;
- optional aura/decorations are included in the base GLB by mistake.

## Blender code patterns

### Reference plane in front-view X/Z

```python
import bpy

def create_reference_plane(name, image_path, width, height, y=0.2, alpha=0.35):
    img = bpy.data.images.load(image_path, check_existing=True)
    mat = bpy.data.materials.new('MAT-' + name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get('Principled BSDF')
    tex = nodes.new('ShaderNodeTexImage')
    tex.image = img
    mat.node_tree.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    mat.node_tree.links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
    bsdf.inputs['Alpha'].default_value = alpha
    mat.blend_method = 'BLEND'
    verts = [(-width/2,y,-height/2),(width/2,y,-height/2),(width/2,y,height/2),(-width/2,y,height/2)]
    mesh = bpy.data.meshes.new(name + 'Mesh')
    mesh.from_pydata(verts, [], [(0,1,2,3)])
    mesh.update()
    uv = mesh.uv_layers.new(name='UV')
    for li, uvco in zip(mesh.polygons[0].loop_indices, [(0,0),(1,0),(1,1),(0,1)]):
        uv.data[li].uv = uvco
    obj = bpy.data.objects.new('REF-' + name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    obj.hide_render = True
    return obj
```

### Validation print contract

```python
print('VALIDATE expected_primary_parts=', expected, 'actual=', actual)
print('VALIDATE front_locked=True reference_overlay_rendered=True')
if actual != expected:
    raise RuntimeError('Part-count mismatch; refusing export')
```

## When to stop and ask for human input

Ask for a correction only after generating evidence, e.g. an overlay image or JSON showing ambiguity. Do not ask vaguely. Example: “The analyzer finds N prominent structural components plus M faint background/decorative shapes. Should the GLB include only the structural components?”

## Sources distilled

- Blender Manual: Image Empties for reference images/blueprints; front/back display, opacity, orthographic and axis-aligned controls.
- Blender Manual: Trace Image to Grease Pencil works best from manually prepared black/white images and controlled resolution.
- Blender Manual: Shrinkwrap moves vertices to a target surface and is useful after silhouette lock for conforming secondary details.
- Blender Manual: UV/Image Texture and Project-from-View-style workflows require UV maps and material nodes for renders/exports.
- OpenCV docs: contour moments, area, perimeter, bounding boxes, template matching.
- scikit-image docs: SSIM for image similarity when pixel-MSE is not perceptually meaningful.

---

# Reference Analysis Validator

This skill converts “looks close” into measurable gates. For brand/logo/mascot work, **do not model or export until a source manifest and validation thresholds exist**.

## Required outputs

Create these in the asset output folder:

- `reference_manifest.json` — classified source files, expected parts, thresholds.
- `source_analysis/*.json` — image metadata, masks/components/landmarks.
- `validation/front_overlay_reference.png` — reference and render overlay.
- `validation/front_mask_validation.json` — IoU/SSIM/bbox/centroid report.

## Workflow

1. Classify sources: front, side, back, top, texture atlas, decals, maps, lightmap, aura/context.
2. Build/refresh `reference_manifest.json` with hard expected counts and view roles.
3. Extract masks/components from each source using `scripts/reference_manifest_compiler.py` or existing analyzers.
4. Render model from matching orthographic camera with reference planes hidden.
5. Compare reference mask vs render mask using `scripts/render_overlay_validator.py`.
6. Refuse final export if hard gates fail.

## Modality rule

Compare like with like. A wireframe edge mask compared against a shaded beauty render gives misleadingly low IoU. For hard gates, render a flat silhouette/matte pass from Blender or compare reference edges to render edges. Use `render_overlay_validator.py --reference-mode ... --render-mode ...` when the source and render need different mask extraction modes.

## Default validation gates

- primary structural part count: exact.
- front silhouette IoU: target >= 0.90 for rigid/logotype shapes; >= 0.82 acceptable for first mascot reconstruction pass.
- bbox center drift: <= 12 px at 1024 px validation size.
- bbox size drift: <= 3% of image dimension.
- face/eye/smile landmark drift: <= 2% of image dimension when landmarks are defined.

## Read when needed

- `references/metrics-and-thresholds.md` for metric definitions and recommended gates.

## Sources distilled

Official/library docs to prefer while extending this skill:

- OpenCV contour features: moments, area, perimeter, bounding rectangles.
- OpenCV shape matching / Hu moments.
- OpenCV homography and geometric transforms.
- scikit-image SSIM for perceptual comparison.

---

# Multiview Constraint Solver

Use this before another rebuild when references disagree. A renderer cannot make one rigid mesh satisfy mutually incompatible orthographic dimensions unless you allow view-specific cheats.

## Workflow

1. Normalize every reference view into a common axis contract:
   - front: width X, height Z;
   - side: depth Y, height Z;
   - top: width X, depth Y;
   - back: width X, height Z.
2. Measure visible body bboxes, not labels/background/aura unless they are part of the model contract.
3. Compare shared axes:
   - front width vs top width;
   - front/back height vs side height;
   - side depth vs top depth.
4. If ratios differ beyond tolerance, write a conflict report and select a policy:
   - `front_side_canonical`: front brand read and side depth/height are authoritative;
   - `front_top_canonical`: front brand read and top footprint are authoritative;
   - `corrected_templates_required`: no rigid rebuild should claim final fit;
   - `view_specific_cheats`: separate camera/view variants allowed, not one rigid asset.
5. Feed the chosen policy into `fit-repair-optimizer` before any geometry, UV, or lighting work.

## Hard gates

- Do not restart modeling until canonical policy exists.
- Do not treat top-view aura/context as body depth.
- Do not average contradictory dimensions unless the user explicitly asks for an approximate stylized compromise.
- Record part-count disagreements separately from bbox disagreements.

## Script

- `scripts/view_constraint_report.py` reads a JSON file of per-view body bboxes and emits shared-axis compatibility and a suggested canonical policy.

---

# Multiview Fit Loop

This skill closes the missing loop: **render → compare → adjust → render again**. It is mandatory when a user says the model still does not fit the templates/originals.

## Required loop

1. Render flat, material-independent silhouettes for every available template view: front, side, back, top.
2. Extract the template object mask, excluding labels, cyan guides, and background.
3. Compare template vs render per view:
   - bbox center and size
   - centroid drift
   - silhouette coverage/IoU where modality is valid
   - visual overlay
4. Convert measured deltas into model/camera/recipe adjustments.
5. Rebuild or transform the model.
6. Repeat until all hard gates pass or document the remaining conflict.

## Constraint inconsistency gate

Before forcing adjustments, check whether the supplied orthographic templates are mutually consistent. A single rigid 3D model cannot simultaneously satisfy contradictory physical ratios, for example if side view says total depth is 0.39 of height but top view says depth is 0.98 of width. When this occurs, stop claiming final fit, write a conflict report, and create separate variants or ask which view is canonical.

## Hard gates

- all required views have validation reports and overlays;
- bbox center drift <= 1.5% of image width;
- bbox size drift <= 3% for front, <= 5% for side/top/back first-pass depth;
- structural part count exact;
- texture UV regions still valid after geometry changes.

## View mask rule

For annotated wireframes, choose a template mask mode that isolates the intended construction/object lines and excludes guide colors, labels, captions, and background annotations. For Blender validation renders, use a flat white silhouette on black, not beauty renders with glow/context elements.

## Scripts

- `scripts/multiview_fit_report.py` compares view pairs and writes JSON + overlays.

## Adjustment rule

Prefer changing recipe parameters or source geometry over camera scale tricks. Camera scale may be used only after model dimensions are correct.

---

# Landmark Fit Repair

Bbox and IoU are too coarse for final mascot/logo matching. This skill turns named feature drift into recipe edits.

## Landmark classes

- `structural_tip`: outer part tips and extrema;
- `shell_corner`: face/shell/rim corners;
- `feature`: eyes, smile, brows, decals;
- `ring`: aura center/radius/dots;
- `depth_marker`: side/back/top thickness markers.

## Workflow

1. Define a landmark JSON for the source reference.
2. Detect or render corresponding product landmarks.
3. Compare by name and view.
4. Convert deltas into repair actions: move boundary control point, scale one component, shift feature curve, tune depth, or adjust aura radius.
5. Rebuild from recipe; do not hand-edit final geometry without updating the recipe/manifest.

## Hard gates

- No final export when named structural landmarks exceed tolerance.
- Face features must be validated separately from body silhouette.
- Aura/context landmarks must not affect base GLB acceptance.

## Script

- `scripts/landmark_fit_report.py` compares two named-landmark JSON files and emits repair deltas.


## Landmark JSON schema

```json
{
  "schema": "landmarks.v1",
  "image_size": [width, height],
  "landmarks": [
    {"view":"front", "name":"leaf_top_tip", "class":"structural_tip", "x":627, "y":130}
  ]
}
```

For part masks, generate initial landmarks from extrema: top/bottom/left/right, centroid, and contour inflection points. Then rename them to semantic names before repair.

---

# Fit Repair Optimizer

This skill converts validation failures into an executable repair queue. The source templates are the contract; the current model is disposable.

## Decision: sequential or parallel?

Use **sequential repair** when failures are coupled:

1. Canonical view / source conflict unresolved.
2. Front silhouette or part count fails.
3. Geometry dimensions fail before UVs can be trusted.
4. Texture region boundaries depend on geometry changes.
5. Lighting/look depends on final material placement.

Use **parallel repair** only for independent tracks with disjoint write scopes:

- geometry recipe/placement tuning;
- atlas-region classification;
- material/look calibration;
- validation tooling improvements.

Do not parallelize two tasks that both edit the same Blender recipe, object transforms, or UV assignment file.

## Mandatory repair order

```
0 source-conflict / multiview-rigidity gate
1 structural part count
2 front silhouette and landmarks
3 side/back/top depth and projection
4 UV/texture region fit
5 material/light/look calibration
6 export and final validation
```

If an earlier stage fails, later stages may be analyzed but must not be finalized.

## Source-conflict gate

Before repair, use `multiview-constraint-solver` to check whether templates are mutually satisfiable. If the same physical axis receives incompatible ratios across views, write a conflict report and require a canonical policy:

- front+side canonical;
- front+top canonical;
- corrected template sheet;
- view-specific cheat renders only, not a rigid 3D model.

## Repair queue schema

Each repair item must include:

- `id`
- `stage`
- `view_scope`
- `failure`
- `measured_delta`
- `proposed_action`
- `write_scope`
- `parallel_group`
- `blocked_by`
- `acceptance_gate`

## Skill-gap rule

If the same failure recurs twice, stop and invoke `quality-refinement-autoloop` before another rebuild. The autoloop must capture evidence, diagnose the missing method, sanitize the lesson into generic publishable guidance, patch the relevant skill(s), validate the skill stack, then return here with a new repair queue.


## Output

Write a project repair plan such as `ALIGNMENT_REPAIR_QUEUE.json` and a human-readable `ALIGNMENT_REPAIR_METHOD.md`.

---

# Quality Refinement Autoloop

Use this when the user says the result is wrong, ugly, not aligned, not textured, not animated, not exportable, or otherwise below expectation. The goal is not to keep tweaking blindly. The goal is to convert failure into a reusable, generic skill improvement before trying again.

## Autoloop phases

### 0. Freeze and preserve

- Stop making product changes immediately.
- Preserve the last accepted baseline and the failed artifact.
- Name the failed branch/version honestly; do not overwrite accepted outputs.

### 1. Evidence capture

Collect the smallest evidence set that proves the failure:

- user feedback quote or summary;
- source/reference files used;
- current output path/version;
- relevant render/contact sheet/overlay/audit report;
- scene/material/object inventory if the failure is inside Blender.

### 2. Diagnose failure dimension

Classify the primary gap:

- geometry / silhouette / landmarks;
- multiview/depth consistency;
- UV / atlas / texture fit;
- closed surface coverage (front/back/side);
- look/material/lighting calibration;
- animation/motion/export truth;
- orchestration/handoff between skills;
- missing validator or missing deterministic helper script.

### 3. Skill-gap decision

Ask: does the current skill stack already contain a generic method for this failure?

- If yes: run the existing skill and repair the artifact.
- If no: add/refine a generic skill first, then repair.
- If repeated failures come from skill interplay, update the harmonizer/handoff rule, not just a leaf skill.

### 7. Repair product only after skill gate

Rebuild or repair from the correct baseline using the improved skill. Do not reuse rejected outputs unless explicitly marked as source evidence.

## Hard rules

- Do not call overlay curves/planes “texture coverage” unless the real mesh surface also passes coverage gates.
- Do not tune lighting/materials to hide geometry or UV failures.
- Do not claim export support if the effect exists only in Blender Python or a render sequence.

## Organic modeling references

- `references/sculpting-retopo.md`
- `references/characters-scope.md`
- `references/infinigen-creature-parts.md`
- `references/metrics-and-thresholds.md`
