---
name: blender-reference-replication
description: Replicate an object in Blender from reference images (front/side/back/top views, design sheets, photos). Covers analyzing the references, building to their measurements, comparing renders against them, and repairing until the differences are within tolerance. Use when the user asks to recreate, copy or match an existing design.
---

# Blender Reference Replication

Model the object from the reference images, not from general knowledge of what such an object looks like. Take measurements, part counts and silhouettes from the references first, then build the Blender model to match those measurements.

## Terms

- **Reference image**: an image supplied by the user that the model must match. Specific views are called the front, side, back and top reference.
- **Structural part**: a separate piece of the object's body that appears as its own mesh. Backgrounds, labels, guide lines and decorative effects are not structural parts.
- **Build script**: the Blender Python script that creates the model from parameters. Repairs change the script's parameters and rebuild the model.
- **Gate**: a check that must pass before work moves to the next stage. A gate passes when the measured value is within its threshold.
- **Offset**: the distance between a measured point in the render and the same point in the reference, as a percentage of the image width.
- **Cheat**: an adjustment that only looks correct from one camera, for example a separate model per view instead of one 3D model.
- **Output folder**: the folder for this task's files, written below as `<output_dir>`.

## When to use this workflow

Switch to this workflow when the user says the model does not match the reference images. If several renders look reasonable but none matches the references, analyze the references before modeling again.

## Reference priority

When references disagree, higher entries win:

1. **Front reference**: silhouette, number of visible parts, positions of features.
2. **Texture atlas**, if supplied: exact part shapes and color or material boundaries.
3. **Side, back and top references**: depth, stacking order, thickness, the back of the object. They must not change the front silhouette once it has passed validation.
4. **User feedback**: treat each point as a requirement and add a gate for it.

## Preflight: reference manifest

Before modeling, write `<output_dir>/reference_manifest.json`:

```json
{
  "source_files": [],
  "primary_view": "front",
  "structural_parts": {"count": null, "labels": []},
  "texture_regions": [],
  "validation_thresholds": {
    "front_mask_iou_min": 0.90,
    "bbox_center_offset_max_pct": 1.2,
    "part_count_exact": true
  }
}
```

`primary_view` is the view whose silhouette takes priority (normally the front). `texture_regions` lists, for each part, its region in the texture atlas; leave it empty if there is no atlas.

If you cannot tell how many structural parts there are, run the analyzer script, show the user what it found, and ask.

## Pipeline

### 1. Classify the references

Classify each supplied file:

- `front_reference`: the main front image or front wireframe.
- `side_view`, `back_view`, `top_view`: orthographic references for depth.
- `texture_atlas`: a base color image containing the parts' textures.
- `material_map`: roughness, bump, normal or emission maps.
- `context`: backgrounds and decorative effects. Exclude them from measurements.

### 2. Analyze the images

Run `scripts/template_analyzer.py` to extract the parts:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/template_analyzer.py \
  --image <path>/front_reference.png \
  --out <output_dir>/front_analysis.json \
  --mode edges
```

The script returns each component's area, a perimeter-based score, bounding box, centroid, contour and a rough class guess. Use `--mode edges` for faint grey wireframes, and `--mode bright_on_dark`, `--mode dark_on_bright` or `--mode alpha` for clean masks. The results are measurements to check, not final answers.

### 3. Place the reference in Blender

Add the front reference as a plane or an Image Empty, aligned to the orthographic camera used for validation. Name it with the prefix `REF_` and exclude it from renders and export. The Blender Manual describes Image Empties as reference images; they can be shown in front of or behind objects, with adjustable opacity, and only in orthographic views.

### 4. Build geometry from the contours

For each structural part:

1. Convert its 2D contour to front-view X/Z coordinates.
2. Fill the contour with a grid or strip of quads.
3. Give it UVs projected from the front view, using the front X/Z bounds or its region in the texture atlas.
4. Add depth along Y (extrude or bulge) only after the front silhouette has passed validation.
5. Name parts by what they are: `GEO_body_top`, `GEO_face_shell`.

Use radial duplication only if the reference is radially symmetric. Many designs have overlapping parts, deliberate asymmetry and a fixed number of visible parts.

### 5. Register the other views

Blender's front view looks along +Y, with the camera on the −Y side.

- Fix the front X/Z silhouette first.
- The side view sets depth and height (Y/Z) only.
- The top view sets width and depth (X/Y) only.
- The back view sets the back of the object and is used for validation; it does not change the front silhouette.

If the views disagree, keep the front silhouette and record the conflict (see "Resolving conflicting views").

### 6. Validate before delivery

Produce these files in `<output_dir>`:

- `front_preview.png`
- `front_overlay_reference.png`
- `front_mask_validation.json`
- `side_preview.png`
- `back_preview.png`
- `top_preview.png`

Compare silhouettes with `scripts/silhouette_validator.py`:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/silhouette_validator.py \
  --reference <output_dir>/reference_mask.png \
  --render <output_dir>/render_mask.png \
  --out <output_dir>/validation.json
```

Deliver the model (the .blend file or an exported file) when:

- the number of structural parts matches the manifest;
- the front mask IoU meets the threshold;
- each feature's centroid offset is within its threshold;
- the model contains no context elements (backgrounds, decorative effects).

## Blender code patterns

### Reference plane in the front-view X/Z plane

The plane is placed at positive Y, behind the object as seen from the front camera.

```python
import bpy

def create_reference_plane(name, image_path, width, height, y=0.2, alpha=0.35):
    img = bpy.data.images.load(image_path, check_existing=True)
    mat = bpy.data.materials.new('MAT_' + name)
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
    obj = bpy.data.objects.new('REF_' + name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    obj.hide_render = True
    return obj
```

### Validation output format

```python
print('VALIDATE expected_structural_parts=', expected, 'actual=', actual)
print('VALIDATE front_validated=True reference_overlay_rendered=True')
if actual != expected:
    raise RuntimeError('Part-count mismatch; not delivering')
```

## When to ask the user

Ask only after you can show evidence, such as an overlay image or a JSON report. Ask a specific question, for example: "The analyzer finds N clear structural parts and M faint background or decorative shapes. Should the model include only the N structural parts?"

## Sources

- Blender Manual: Image Empties for reference images; front/back display, opacity, orthographic-only display.
- Blender Manual: the Shrinkwrap modifier moves vertices onto a target surface; use it after the silhouette has passed validation to fit secondary details.
- Blender Manual: Image Texture and Project from View need UV maps and material nodes for renders and export.
- OpenCV documentation: contour moments, area, perimeter, bounding boxes, template matching.
- scikit-image documentation: SSIM, for image similarity when pixel differences are not meaningful.

---

# Validation

Replace visual judgment with measured checks. Write the reference manifest and its thresholds before modeling.

## Required files

Create these in `<output_dir>`:

- `reference_manifest.json`: classified reference files, expected parts, thresholds.
- `source_analysis/*.json`: image metadata, masks, components, landmarks.
- `validation/front_overlay_reference.png`: the reference and the render overlaid.
- `validation/front_mask_validation.json`: IoU, SSIM, bounding box and centroid results.

## Workflow

1. Classify the references: front, side, back, top, texture atlas, material maps, context.
2. Create or update `reference_manifest.json` with the exact expected part counts and the role of each view.
3. Extract masks and components from each reference with `scripts/reference_manifest_compiler.py`.
4. Render the model from the matching orthographic camera, with reference planes hidden.
5. Compare the reference mask with the render mask using `scripts/render_overlay_validator.py`.
6. Deliver when every gate passes.

## Compare like with like

Compare two silhouettes, or two edge images. Comparing a wireframe's edge mask with a shaded beauty render gives a misleadingly low IoU. For gates, render a flat silhouette (matte pass) from Blender, or compare reference edges with render edges. Use `render_overlay_validator.py --reference-mode ... --render-mode ...` when the reference and the render need different mask extraction.

## Metrics

- **Mask IoU**: the overlapping area of the two masks divided by their combined area. It drops when visible area is missing or extra.
- **Centroid**: the center of a mask, computed from image moments.
- **Bounding box**: the center, width and height of a mask's bounding rectangle.
- **SSIM**: a measure of perceived similarity. Use it only as a diagnostic, after the masks pass; differences in materials or lighting lower it even when the shapes match.
- **Part count**: not a soft metric. If the manifest declares N structural parts, the model must contain exactly N structural meshes.

## Gates

| Check | Threshold |
|---|---|
| Structural part count | exact |
| Front silhouette IoU | ≥ 0.90 |
| Bounding box center and centroid offset | ≤ 1.2% of image width |
| Bounding box size difference, front view | ≤ 3% of image size |
| Bounding box size difference, side, top and back views | ≤ 5% of image size |
| Named landmark offset (eyes, corners, tips), when landmarks are defined | ≤ 2% of image width |

## Overlay images

Produce two overlays:

1. The reference in cyan or magenta, the render in yellow or green, differences in red.
2. The reference, semi-transparent, behind the front orthographic render.

The validation report includes the metric JSON and at least one overlay.

## Sources

- OpenCV: contour features (moments, area, perimeter, bounding rectangles), shape matching with Hu moments, homography and geometric transforms.
- scikit-image: SSIM.

---

# Resolving conflicting views

Use this before rebuilding when the references disagree. One 3D model cannot match orthographic views whose dimensions contradict each other, unless you accept a cheat.

## Workflow

1. Express every view in the same axes:
   - front: width X, height Z;
   - side: depth Y, height Z;
   - top: width X, depth Y;
   - back: width X, height Z.
2. Measure the bounding box of the object itself in each view, excluding labels, backgrounds and context.
3. Compare the axes that two views share:
   - front width with top width;
   - front and back height with side height;
   - side depth with top depth.
4. If the ratios differ by more than 12% (the script's default, `--tolerance 0.12`), write a conflict report and choose one policy:
   - `front_side_canonical`: the front silhouette and the side view's depth and height are correct;
   - `front_top_canonical`: the front silhouette and the top view's footprint are correct;
   - `corrected_references_required`: no single model can claim to match; ask for corrected references;
   - `view_specific_cheats`: a separate model per camera view is allowed instead of one 3D model.
5. Apply the chosen policy before any geometry, UV or lighting work (see "Repair order").

## Gates

- Choose a policy before modeling again.
- Keep contradictory dimensions as they are rather than averaging them, unless the user asks for an approximate compromise.
- Record disagreements about part count separately from disagreements about bounding boxes.

## Script

- `scripts/view_constraint_report.py` reads a JSON file of per-view bounding boxes, reports whether the shared axes agree, and suggests a policy.

---

# Fit loop

Repeat this cycle until all gates pass: render, compare with the references, adjust, render again. Use it whenever the user says the model still does not match the references.

A **round** is one pass through the cycle below: change the build script, rebuild, render every view, and measure every gate. Matching a reference usually takes many rounds, and slow progress is normal.

## Cycle

1. Render a flat silhouette (white on black, no materials) from every view that has a reference: front, side, back, top.
2. Extract the object's mask from each reference, excluding labels, guide lines and background.
3. Compare each reference with its render:
   - bounding box center and size;
   - centroid offset;
   - silhouette IoU, when both images are silhouettes;
   - an overlay image.
4. Turn each measured difference into a change to the build script's parameters, or to the camera.
5. Rebuild the model with the changed parameters.
6. Save each round's version and keep track of the best one so far: the version with the most gates passing, and among those, the highest front IoU. If a round turns out worse than the best version, continue from the best version.

## When a gate stops improving

If a gate has not improved after two rounds, work out why before making the next change. Common causes:

- The measurement is wrong: the wrong mask mode, labels or background counted as part of the object, or a wireframe compared with a shaded render.
- The reference views contradict each other (see "Resolving conflicting views").
- The parameter being changed does not control the difference being measured.
- The method cannot produce the shape, for example primitives used for a curved silhouette that should be built from its contour.

Write down the most likely cause and how you checked it, change the approach to address it, then continue the loop from the best version.

## When the loop ends

- The loop ends when all gates pass.
- If the references contradict each other, check them as described in "Resolving conflicting views" and ask the user which view to follow.
- If you cannot find why a gate is not improving, show the user the overlay, the measurements and what you checked, and ask how to proceed.

## Adjustments

Change the build script's parameters or the source geometry. Scale the camera only after the model's dimensions are correct. Move or scale whole objects only to fix placement.

## Masks

For annotated wireframes, choose a mask mode that keeps the object's lines and drops guide colors, labels, captions and background notes. For renders from Blender, use a flat white silhouette on black, not a beauty render.

## Script

- `scripts/multiview_fit_report.py` compares each reference with its render and writes a JSON report and overlays.

---

# Landmark repair

Bounding boxes and IoU are too coarse for final matching. Use named landmarks to measure specific features and turn their offsets into changes to the build script.

## Landmark classes

- `structural_tip`: tips and extreme points of parts;
- `shell_corner`: corners of surfaces and rims;
- `feature`: eyes, mouth, brows, markings;
- `depth_marker`: thickness markers in the side, back or top view.

## Workflow

1. Write a landmark JSON file for the reference.
2. Detect or render the same landmarks on the model.
3. Compare them by name and view.
4. Turn each offset into a change: move a boundary control point, scale one part, shift a feature curve, or change a depth.
5. Rebuild from the build script. If you edit geometry by hand, update the build script and the manifest to match.

## Gates

- Deliver only when every named structural landmark is within its threshold.
- Validate features (eyes, mouth) separately from the body silhouette.

## Script

- `scripts/landmark_fit_report.py` compares two landmark JSON files and reports the offset of each landmark. Its default `--tolerance-px` is 12 pixels; pass 2% of the image width instead (for example `--tolerance-px 20` for a 1024-pixel image).

## Landmark JSON format

```json
{
  "schema": "landmarks.v1",
  "image_size": [width, height],
  "landmarks": [
    {"view":"front", "name":"top_tip", "class":"structural_tip", "x":627, "y":130}
  ]
}
```

To start a part's landmarks, take its extreme points (top, bottom, left, right), its centroid and the contour's inflection points, then rename them to describe what they are.

---

# Repair order

Turn failed gates into an ordered list of repairs. The references define the target; rebuild the model whenever that is simpler than editing it.

## Sequential or parallel

Repair in sequence when failures depend on each other:

1. A conflict between views is unresolved.
2. The front silhouette or the part count fails.
3. Dimensions fail, so UVs cannot be trusted yet.
4. Texture region boundaries depend on geometry changes.
5. Lighting and appearance depend on where materials end up.

Repair in parallel only when the tasks change different things:

- geometry parameters and placement;
- assigning texture atlas regions to parts;
- material and appearance;
- validation scripts.

Run two tasks in parallel only if they change different build scripts, objects or UV assignments.

## Order

```
0 conflicts between views
1 structural part count
2 front silhouette and landmarks
3 depth from the side, back and top views
4 UV and texture regions
5 materials, lighting and appearance
6 export and final validation
```

If an earlier stage fails, later stages may be examined but not finalized.

## Conflicting views

Before repairing, check whether the references can all be matched (see "Resolving conflicting views"). If one axis gets incompatible ratios from different views, write a conflict report and choose a policy:

- front and side are correct;
- front and top are correct;
- corrected references are needed;
- a separate model per view (a cheat), not one 3D model.

## Repair list format

Each repair item has:

- `id`
- `stage`
- `view_scope`
- `failure`
- `measured_delta`
- `proposed_action`
- `write_scope`: what the repair changes (a script, object transforms, UVs)
- `parallel_group`
- `blocked_by`
- `acceptance_gate`

## Output

Write the plan to `<output_dir>/repair_queue.json`, with a readable summary in `<output_dir>/repair_method.md`.

---

# After a rejected result

Use this when the user rejects a result. Before changing the model again, work out what kind of problem it is and whether these instructions already have a method for it.

## Steps

### 1. Keep both versions

- Keep the last accepted version unchanged.
- Save the rejected version under its own name, for example `v3-rejected`.

### 2. Collect evidence

Collect the smallest set of files that shows the failure:

- the user's feedback, quoted or summarized;
- the reference files used;
- the path and version of the current output;
- the relevant renders, overlays or reports;
- an inventory of scene objects and materials, if the failure is inside Blender.

### 3. Classify the failure

Name the main problem:

- geometry, silhouette or landmarks;
- consistency between views or depth;
- UVs or texture fit;
- parts of the surface that no reference view shows (for example the back or the underside);
- materials, lighting or appearance;
- export (the exported file does not show what the Blender scene shows);
- a missing validation script.

### 4. Decide whether a method is missing

Ask: do these instructions already cover this failure?

- If yes, follow them and repair the model.
- If no, write down the missing method first, then repair.

### 5. Repair

Rebuild or repair from the last accepted version, using the method from step 4. Use the rejected version only as evidence.

## Note

Fix geometry and UV problems in the geometry and UVs. Changing lighting or materials can hide them in a render, but they remain in the model.
