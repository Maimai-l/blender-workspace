## Characters / avatars (limited scope)

### Stylized broadcaster avatar (primitives-only — scope boundary documented below)

**This is the kind of subject the skill CANNOT do well automatically.** Production-quality character work requires sculpting + retopology + hand-painted textures + manual blendshape sculpting — see `docs/avatar-design-kit/prompts/04-blender-workflow.md` ("Estimated artist time: 6-10 hours for a competent Blender character artist").

What the skill CAN produce: a stylized primitives-based broadcaster silhouette, useful as concept-stage placeholder or for non-photoreal stylized content. Build pattern:

- **Head**: UV sphere, ø20cm, slightly stretched vertically (1.0 × 0.95 × 1.15)
- **Neck**: cylinder ø10cm × 10cm tall, just below head
- **Body / blazer**: tapered cube — wider at shoulder, narrower at top via Edit-Mode upper-vert scale 0.85
- **Hair (Caesar cut)**: UV sphere top-half (delete bottom half via bmesh), scaled flat (0.55 in Z), slightly forward of head crown
- **Tie**: small cube extending forward from front of body (tie's Y position must be MORE FORWARD than body's front face — otherwise hidden)
- **Glasses**: use Eyewear/sunglasses recipe above

**Materials**:
- Skin: Subsurface scattering with `set_input` helper for `Subsurface IOR` (Blender 5.x quirk), Base (0.85, 0.62, 0.48), Subsurface Weight 1.0, Radius (1.0, 0.25, 0.10)
- Suit: cloth with sheen, deep plum (0.12, 0.05, 0.18), Sheen Weight 0.3
- Hair: warm blond (0.65, 0.48, 0.22), Roughness 0.55
- Tie: dark crimson (0.35, 0.03, 0.05), Roughness 0.30

**Cyan/magenta synthwave lighting** (from BRIEF.md):
- Cyan key from upper-left: 250W, color (0.20, 0.80, 1.0)
- Magenta rim from behind-right: 200W, color (1.0, 0.15, 0.65)
- Subtle warm fill from below: 15W only (any more washes out colors)
- World Strength 0.15 (very dark)

**What doesn't work without artist intervention**:
- Realistic facial features (eyes, nose, mouth, ears) — primitives can't carve these
- Animatable visemes (15 lip-sync blendshapes per TECH-SPEC.md)
- Hand-textured skin (no pores, no per-area variation)
- Believable hair (single mass instead of strand-based)
- Posing / rigging / animation
- Anatomy correctness

**Honest scope statement**: the orchestrator should warn the user when they request character work that automated generation produces a recognizable silhouette only; for production-quality character output, recommend commissioning a Blender character artist with the brief in `prompts/04-blender-workflow.md`.

### Why primitive-based "head with face features" still doesn't look human

Adding nose / ears / mouth / brows as separate small primitives to a sphere head crosses from "ball" to "abstract avatar" but **does not cross to "human"**. See validation iteration `assets/v1.2.0-validation/04_broadcaster_with_features_still_not_human.webp` — a sphere head with cube-nose, sphere-ears, line-mouth, bar-brows reads as a slightly less abstract placeholder, not a face.

The hard limit: a real human face requires **subtractive sculpting** (eye sockets recessed into the head, cheekbones pulled out, lip curvature, jaw line, chin shape) — features that can't be added as separate floating primitives, only carved into a base mesh.

**Three realistic paths past this limit, all out of pure-recipe scope**:

1. **Import an existing human base mesh** via the Blender MCP's other tools:
   - `mcp__blender__download_polyhaven_asset` — Poly Haven has CC0 character assets
   - `mcp__blender__download_sketchfab_model` — Sketchfab CC-BY models
   - `mcp__blender__generate_hyper3d_model_via_text` — text-to-3D AI generation
   These produce a real human mesh foundation that the orchestrator can then materially / lighting / pose via existing skills.

2. **Sculpt mode** — gestural, not driven well from natural-language. The skill can prepare a base mesh and recommend the user sculpts manually.

3. **Commission a Blender character artist** — `prompts/04-blender-workflow.md` documents the brief (6-10 hours).

The orchestrator should suggest path 1 (Hyper3D / Sketchfab / Polyhaven asset import) when the user asks for a character — that's the cheapest automated route to a real human silhouette before the recipe pipeline takes over for materials, lighting, and rendering.
