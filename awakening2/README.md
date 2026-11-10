# Awakening II — a 79.5-second 2D anime short, drawn by our own look engine

A giant robot has knelt in an ancient forest for so long that moss, wildflowers and an old tree
grow over it. At sunrise a small bird lands on its shoulder, the first ray of light crosses its
face, a light flickers on inside its chest; the ground trembles, birds burst from the canopy,
it rises, lifts its head to a gap in the canopy, ignites its engines and tears into the golden
sky, leaving a curving trail of light and mist.

- Film: `deliver/awakening2.mp4` (the final version, v14) and `deliver/awakening2_vN.mp4` (each
  version, v1–v14): 1920×1040 (1.85:1), 24 fps, H.264 + AAC, 79.5 s.
- Benchmark study and scorecard: `notes/benchmark.md`. Progress log: `notes/progress.md`.

## How the frames are made (no image or video models anywhere)

| Stage | Code | What it does |
|---|---|---|
| Robot model | `robot/warden.py`, `engine/r3d.py`, `engine/rig.py` | The Warden is modelled as signed-distance-field parts (smooth forms, no visible polygons), meshed once with marching cubes, rigged as rigid parts. |
| Growth | `robot/surface.py`, `robot/vineplan.py` | Moss cushions, soil, an old tree and flowers are placed once from the kneeling pose (on upward faces), so they stay on-model in every later pose; vines hang from down-facing surfaces. |
| Passes | `engine/r3d.py` | Our own numba rasteriser writes passes, never final pixels: part / material id, depth, normals, world and part-space positions, cast-shadow map. |
| Look engine | `engine/cel.py`, `engine/ink.py`, `engine/look.py` | Turns passes into a drawn cel: designed hard-edged shadow shapes (threshold → clean-up → no islands → smooth edge), a sky-fill tone and a deep tone, hand-designed chipped paint / primer / rust patches / rust streaks (box-projected label maps with smooth edges), rivets, painted moss tufts, flowers, cel lamp-eyes; ink traced from id / depth / normal discontinuities into tapered, pressure-varied strokes that sit exactly on the fill edges. |
| Backgrounds | `engine/gouache/` | A gouache painting engine (bristle strokes, wet edges, dry brush, Oklab mixing, unique trees, aerial perspective) paints every shot's multiplane layers in screen space from the storyboard layouts. |
| Effects | `engine/fx/` | Drawn cel effects in 2–3 hard tones on 2s, with separate looks for soil (clods and dirt sprays), dust (translucent warm grey) and wind (a dry-brush shock ring): soil pours and debris, tumbling leaves, engine flames, drawn smears and impact frames, the light trail with mist billows; airbrushed light only in the photography pass. |
| Birds | `engine/birds/` | A small songbird drawn as a cel from one model, painted as a blue-and-white flycatcher so it stands out from the moss (landing, hops, chirps, startle, take-off), and flocks drawn on 2s. |
| Vines | `engine/vines.py` | Verlet chains drawn as inked strokes with cel leaves; rooted vines tear loose as the robot rises. |
| Shots | `shots/shotdefs.py`, `shots/anim.py`, `shots/shotfx.py`, `shots/render_shot.py` | Cameras, key poses (drawn on 2s/3s with holds), lights, layer order and effects per shot. The robot is redrawn only when its drawing changes; between drawings the cel and the painted layers move as 2D layers under a rostrum-style camera synced to the 3D camera, so pushes and tilts never read as a CG dolly. |
| Photography | `engine/comp.py` | Ground shadows, aerial haze (the ink line is put back after it), light wrap, bloom, grade, vignette, a static paper tooth; no screen grain. |
| Sound | `audio/` | A fully synthesized score and sound design driven by `audio/cues.json`. |

Design work: `design/` (three concepts, the decision, model sheets, face states), storyboard
and layouts: `board/`, style frame: `style/`, QA sheets: `qa/<version>/`.

## Running it

- Sandbox (4 CPUs): `python3 shots/render_shot.py S08` renders a shot to `/home/user/aw2_frames/S08/`;
  `python3 tools/assemble.py vN --qa-only` writes the QA sheets for a delivered `deliver/awakening2_vN.mp4`.
- The Windows PC (28 threads) through the exec MCP: `python3 tools/pc.py sync`, `pc.py bg S01 ...`,
  `pc.py render vN --workers 7`, `pc.py status vN`, `pc.py encode vN`.

## Changes to the prompt, and why

- **Frame 1920×1040 (1.85:1)** instead of 1920×1080: theatrical framing, and the side-by-sides
  line up with the benchmark frame for frame (the prompt allowed either).
- **No Blender for the robot.** The prompt allowed Blender as a helper; we modelled the robot as
  signed-distance fields in our own code and rasterised the passes with our own numba
  rasteriser. That keeps every pass (part ids, part-space positions for decals, light and shadow
  masks) under our control and avoids moving gigabytes of passes between machines.
- **Heavy rendering on the Windows PC** (28 threads, through the exec MCP) instead of the
  4-CPU sandbox, with the same Python code: the PC renders the film in ~25 minutes, which made
  several polish rounds possible. Code goes up as a tarball because the PC cannot reach GitHub
  reliably; background paintings are regenerated there from their deterministic source.
- **Camera moves between drawings are 2D moves of the cels and painted layers** (a rostrum /
  multiplane camera synced to the 3D camera). The robot is only redrawn when its drawing
  changes (on 2s/3s, or once for a held pose). This is how cel animation works and it keeps
  pushes and tilts from reading as a CG dolly; the prompt asked for "camera on 1s, robot on
  2s/3s" and this is the faithful way to get both.
- **One-knee kneel** (a "resting knight") instead of the slumped two-knee kneel of our first
  boards: from the main camera it is the only pose that reads as kneeling at thumbnail size.
- **The first ray is a low sunrise beam** (8° above the horizon) through a gap in the trunks, not
  a shaft from the canopy above: the robot's bowed face points down, so only a low sun can light
  the face itself — and at sunrise that is what the sun does.

## Self-assessment (final)

Four independent reviews (each a fresh agent given only the two films, our QA sheets and the
brief) scored both films out of 10 on design, composition, line, colour, timing, effects, climax
and backgrounds. Each review had a different reviewer, so the scores drift from one review to
the next; what holds is that ours has been ahead since v7. v12, v13 and v14 were not reviewed.

| Review of | The Moss Keeper | Awakening II |
|---|---|---|
| v1 (`notes/review_v1.md`) | 5.4 | 4.3 |
| v4 (`notes/review_v4.md`) | 6.1 | 5.8 |
| v7 (`notes/review_v7.md`) | 5.9 | 6.4 |
| v11 (`notes/review_v11.md`) | 5.4 | 6.0 (6 of the 10 matched beats) |

Where it beats The Moss Keeper:
- **Light and depth.** Backgrounds painted per shot in screen space with layered mist and real
  sunrise light; the benchmark reuses one clearing with clone trees.
- **Timing and acting.** The robot is drawn on 2s/3s from key poses with holds, with overlapping
  action on the head, lids, hands and roof; the eyes open in two stages and blink; camera shake
  only on impacts; smears and impact frames at the launch. The benchmark's robot barely changes
  pose.
- **The beats, staged.** Bird landing, first ray across the face, furnace heartbeat, the eyes
  opening, a three-angle rise from a real kneel, the head lifting to the gap, the engines, the
  wind ring bending the forest, the launch, the climb through the canopy, the hero flight and the
  trail to the sun, the empty imprint with the bird.

Where it still falls short (the v11 review's main points; v12 and v13 fixed effects and
background details, not these):
- The robot still reads as a cel-shaded 3D model. Its shadows follow the geometry, its ink line
  is even, its rivets and panels are regular, and every move is the rigid model turned in
  perspective. The benchmark's robot design is more iconic.
- The in-betweens are computer-smooth (the head lift is a symmetric bell curve), and the stand
  has no overshoot or settle.
- The launch (59.5–61 s) lacks power: the robot leaves the frame early and the rest is empty
  forest.
- The eyes stayed at the same sleepy half-mast from the waking to the flight (v14 adds a
  resolute state from the head lift on; not reviewed).
- In the wide shots the head is small and the tree on the back merges with the canopy.
- The trail across the sky (67–72 s) is a pale ribbon rather than light, and the sky is flat.
- The ring of wind (56.5–59.5 s) is a thin ring that is over in under a second.
- Some backgrounds repeat (pale distant trunks, stamped ivy).
- The sound is synthesized: good synths, not an orchestra.

## Version history

### v1 (12:25) — first complete film
All 17 shots, the full soundtrack. Built with the first versions of every system; the shots
were rendered before most of the fixes below, so v1 is the baseline. Known problems at v1:
the face close-ups (S03/S07) are seen from a steep low angle with a dutch tilt and the face does
not read; the robot is washed pink by haze and bloom; S10 uses a fallback painting that breaks
at its top edge; S16's trail is a vertical plume that buries the light ribbon; S04's light
spill is a flat orange disc; S01's robot drifts against the painted floor during the tilt; no
vines yet; the rise is a simple blend between three poses.

### v2 (12:50)
- Vines on the robot (verlet chains drawn as inked strokes with cel leaves); rooted vines tear
  loose as it rises, the rest swing with the breeze and the motion.
- The rise rebuilt from seven key poses (sink, plant the hand, push, crouch, rise, stand, torso
  up, look up) on 3s with holds; sound cues retimed to them.
- Face shots: level-eyed cameras in front of the bowed face; the first ray is a low sunrise beam
  that lights the face (the brow throws a crescent shadow over the shut eyes), motes in the beam.
- The launch: a held crouch with the engines roaring behind it, two smear frames, two impact
  frames (black/gold), then a blast with ground dust rolls, debris, leaves and speed lines.
- The climax redesigned: the robot climbs along a big screen-space arc toward the sun, the trail
  of light and mist follows the arc (S16).
- All 14 backgrounds repainted by the painter's Phase 3 (golden sky with sculpted clouds, ground
  close-up, layered crowns instead of pads, rim-lit canopy for the flock).
- Fixes: S01 tilt drift, S10 painting window, S04 framing, bigger bird, less haze and bloom,
  rivets, tufts on the roof tree, S05 camera matched to its painting's horizon, flock between
  the canopy layers.

### v3 (14:40)
- The face redesigned: a framed furnace grille with four slats as the muzzle (the three slots
  read as a mouth/nose), eyes that warm up from ember red to gold instead of fading in.
- Grass sprouting from the moss, rounded painted moss tufts, a warm rim band on the sun side
  when the sun is behind the subject, an S-curve grade with more saturation.
- The climax: the robot faces three-quarters toward the camera as it climbs, with engine flames.
- (The session was paused 13:00–14:36 by a usage limit; the PC finished rendering v3 meanwhile.)

### v4 (15:25)
- **Restructured to 79.5 s** (cue sheet v2; picture and sound both read it): an establishing vista
  over the misty forest at sunrise opens the film; the sky shot became two shots — a tracking
  shot where the robot fills the frame, debris, leaves and vines streaming off it against a
  tilted, scrolling flight painting, then the wide where it rises from the cloud sea along a
  curving trail of light and mist and becomes a spark crossing the sun.
- **Robot surface:** faded paint, lichen, longer rust runs from the chips, warmer shadows on
  the red, heavier silhouette line and a lighter interior line, colour-traced and fringed lines
  on the moss and leaves, eyes that stay lit after the robot wakes.
- **Launch and flight:** a flame column under the robot as it rockets out, the canopy burst
  from below (S15), a slower, larger ring of wind with flames and leaves (S13).
- **Effects (helper round 2):** dust with one dominant mass, hooked curls and flat bases (no
  more "popcorn"), soil that falls as clumps and crumbs (no more "planks"), clean smears and
  impact frames, more leaf shapes with curl and veins.
- **Photography:** camera shake moves the whole frame, the robot gets aerial haze by distance,
  no lens-flare starbursts, less grain and bloom; S04's furnace core glows in designed bands.
- **Staging:** S08 seen three-quarters so the kneel reads, S09 framed to keep the head in, S10 lit
  from the canopy gap above, S12's crouch snaps down instead of easing.
- Known slip in v4: the flight painting (S16A) was missing on the render PC, so the tracking shot
  used the static fallback sky (the clouds do not stream past). Fixed for v5.

### v5 (15:55)
- **A real kneel.** The old kneeling pose hung the knee 0.8 m and the hand 2 m above the ground
  (the toes carried the body), so it read as a crouch; the pose is now solved so the right knee
  and the knuckles rest on the ground, and the anticipation pose presses the hand down.
- **Overlapping action:** the head, lids, hands and roof halves follow the body a few frames late.
- **Backgrounds (round 5):** the canopy seen from below repainted in flat planes with a soft sun
  halo (no starburst), painted soft focus instead of fog gradients in the close shots, bigger
  margins for the tilts, characterful near trunks (buttress roots, knot holes, bracket fungi).
- **Effects (round 3):** dust crowns built from rolling lobes, a varied ring wall, a dust veil
  behind the launch blast.
- **Sound:** re-scored for the 79.5 s cut: a music-box opening over the vista, the full theme
  landing on the cut to the tracking flight, the roar flying away, a chime as it crosses the sun.
- The flight painting is in place, so the tracking shot's clouds stream past.

### v6 (16:20)
- **Launch (S14):** the robot stays in frame on its flame column for longer before it exits the
  top, so the hero is never lost in the blast.
- **Engines:** the bells point down and the glow sits inside the flame, so the lit bells no
  longer read as a second pair of eyes on the robot's back.
- **Flight (S16A):** the head turns toward the sun and the arms sweep back during the climb.
- **Eyes (S07):** the lids open in two stages (crack, hold, open), each held on 2s.
- **QA:** every version is checked for card edges and missing-background bands
  (`tools/check_edges.py`; v1 had 9 suspicious frames, v4–v6 have none).

### v7 (16:50)
Fixes from the second independent review (`notes/review_v4.md`: benchmark 6.1, ours 5.8; the
robot read as a red vinyl toy, the film moved like CG, and the hero vanished at the climax).
- **One colour model for the robot:** an oxidised red-brown family (lit, shadow, deep shadow,
  highlight and sky fill share one hue, saturation capped), rust and primer decals in the same
  family, a 4 % lower saturation in the grade. No more maroon-in-one-shot, pumpkin-in-the-next.
- **Line hierarchy:** the silhouette is the heaviest line (5 px), interior lines thinner (detail
  1.2 px), vines and leaves get thin dark-green colour lines instead of heavy outlines.
- **Motion:** camera shake only on impacts, on 2s, decaying (`impacts` per shot); no screen
  grain at all (the paper texture lives in the painted layers); S01 and S10 move as flat
  painted layers (2D tilt), not a 3D camera.
- **Story beats:** a blue-and-white bird that stands out from the moss; S07 backlit so the
  waking eyes carry the shot, and the head follows the bird as it flies off; a brighter
  heartbeat halo on the chest furnace; S09 seen from a low three-quarter front angle; lids
  that tilt up at the outer corners in every shot (kind, not angry).
- **The robot:** segmented mechanical fingers with painted backs (no mittens), moss on the
  legs, feet and hands (not only on top surfaces).
- **Climax:** S15 draws the robot as a dark rim-lit shape in front of the glow with leaves and
  twigs only; S16A gets long jet flames and the trail starting at the engines; S14's blast is
  smaller and lighter so the robot stays readable; S12's two engines sputter at different
  moments (two simultaneous flashes read as eyes on its back).
- **Ending:** a darker clearing with a lit imprint (knee hollow, hand print, torn roots), the bird
  hopping into it at 112 px, and a cool fade to black.
- **Backgrounds (round 6):** S13's "cube" (a bracken fern drawn with straight spokes) repainted,
  a canopy band around the top view; S00 repainted with flat brush-stroked crowns and broken
  ridges; S16B's cloud sea as painted cumulus at varied scales; S06 rims vary per clump.
- **Effects (round 4):** soil pours in streams, the trail is a white-gold ribbon with lumpy
  edges that dissolves into wisps (no colour fringe), a pressure band of flattened grass leads
  the ring of wind, curled bark and S-curve roots, thin coloured outlines on debris.
  The S16B trail now has perspective: thin at the far robot, wide where it passes the camera.

### v8 (17:20)
- **Centuries of growth at the base:** the forest floor has grown up around the knee, both feet
  and the hand: moss mounds with grass and flowers, fixed in the world, so when the robot rises
  it leaves them behind with the hollow where it knelt. What touches the ground dissolves into
  the painted floor instead of ending on a hard line.
- **A heavier machine:** riveted armour plates (flank plates in two rows, a helmet cap, pauldron
  lames, bands on the thighs, shins and upper arms) with rows of rivets along the seams; fewer,
  shorter rust runs (the regular vertical stripes are gone).
- **Acting:** the robot blinks slowly as the bird flies off (S07), and its eyes stay wide during
  the push (S08) instead of showing two lit crescents under the lids.
- **Effects (round 5):** soil slides off the ledges as ragged sheets that tear into clumps (no
  more beads or stick-like rods); the dust at the hand, knee and feet sprays low along the
  ground in broken clusters instead of one smooth blob; the launch blast keeps its single mass.
- **Fixes:** no glare from the trail over the robot's chest in S16A; S14's focus lines are a
  short burst with the impact.

### v9 (17:50, encoded 19:40)
- **S03:** the sunlit face is warm brick with small highlights instead of salmon plastic.
- **S13:** the ring of wind now moves the forest: the treetops, ferns and shrubs bend outward as
  the front passes and spring back (a travelling 2D deformation of the painted layers, on 2s).
- **S04:** the chest furnace no longer lights the undersides of the lids (two lit crescents
  read as eyes opening before the eyes actually open in S07).
- **S15:** seen from straight below, the two jets merge into one ring of flame tongues (two
  small discs side by side read as a pair of eyes).
- **Sound:** a soft servo-and-click blink in S07.
- (The session was paused 17:25–19:35 by a usage limit; v9 had finished rendering on the PC.)

### v10 (20:15)
Fixes from the third independent review (`notes/review_v7.md`: ours 6.4, benchmark 5.9; it
said the robot read as a dim maroon toon model with a thin contour, the hero flight was a dark
lump, the rise wide lost the head in the canopy, and the flock and S10 moved like CG).
- **The robot catches the sunrise:** a lighter, warmer weathered red-ochre (dark maroon only in
  the deep shadow), lighter faded paint and rust in the same family, the roof's shadow a deep
  green so gaps in the moss read as shade, not holes.
- **The contour survives the air:** haze and light wrap used to wash the outline into the
  background; the drawn line is now put back after them (75 % of its darkness, tinted by the
  air), so the silhouette is again the heaviest line in every shot.
- **Hero flight (S16A) re-staged:** front-lit by the sun ahead, closer and lower, the whole
  robot in frame, drawn key poses with holds on 2s (out of the canopy; arms swept back with
  the head up to the sun; a balancing arm; swept back again), no glow over the chest.
- **Rise wide (S09):** a wider camera so the head clears the canopy and the full figure, feet
  and hands read. **S10:** the camera holds while the head lifts on 2s (no 3D tilt).
  **S01:** the tilt moves like a hand-cranked rostrum (short ease, constant speed).
- **Launch (S14):** the engines are already roaring in the crouch (continuity with S13), with
  no glow veiling the robot. **S15:** a slower climb, so the robot stays in the gap longer
  (sound retimed to the new crossing).
- **Vines and the flock:** vines sway with per-vine gusts; leaves in three greens, shadow
  leaves darker and without outlines. The flock is drawn on 2s as hard-edged silhouettes.
- **S17:** the bird's breast stays white in shadow (its overridden colour now drives the
  shadow tone).

### v11 (20:45)
- **Three effect vocabularies instead of one puff:** soil is dark brown clods and dirt sprays
  on arcs with a little earthy dust (the rise, the hand on the ground); dust is translucent warm
  grey that thins out (the launch, the engine wash); wind is a white dry-brush shock ring with
  flattened grass, torn leaves and a little mist (S13), no more ring of cream puffs.
- **S13:** seen from above, the jets are a hot pool of light under the robot instead of two
  candle flames on its back.
- **Backgrounds (round 7):** the canopy seen from below (S11, S15) is painted as backlit,
  translucent leaf masses with branches reaching into the gap and haze between the storeys (no
  more purple cut-outs with yellow rim lines); S00's near band is painted crowns and dead snags
  in mist; S06's mid canopy is painted crowns; S10's sky card no longer shows its edge.
- **Weathering:** rust runs bleed from a share of the rivets.
- **S16B:** the trail no longer swells into a "pancake" where it passes the camera.

### v12 (21:20)
- **Smear frames drawn, not stretched (S14):** the two smear frames redraw the robot as flat
  colour shapes taken from its own cel, dragged down into tapered smear fingers with speed
  streaks and ghost edges, the flames showing through the notches.
- **Effects (round 7):** debris leaves short tapered dashes instead of rods; overlapping
  translucent dust merges instead of doubling in density; the wind ring's few billows lie flat
  and pale under the white brush ring.
- **Backgrounds (round 8):** S12's floor is in cool shade crossed by warm sunlit stripes with
  dry-brush edges (no radial fan of soft rays); the trunk base that read as a purple river in
  the top view is gone; the masses at the canopy gap are crisp and the outer ceiling varies;
  the vista's near band is a low broken line of leaves with two crooked snags.
- **S09:** the camera re-aimed so the standing robot's head is in the bright sky gap, not
  against a dark crown.
- **S03:** the sunlit band on the face is a little less saturated.

### v13 (rendered 21:43, encoded the next morning at 07:46)
- **A face for the design:** a faded cream sun crest on each shoulder plate (the sunrise motif
  of the film, chipped and rusted like the rest of the paint), on the model sheet too.
- **Effects (round 8):** pebbles are faceted stones that hop from the ground (not grey spheres
  appearing in the air); leaves tumble in 3D: they narrow edge-on as they roll and show their
  paler underside; the smear frames have bigger, simpler colour shapes.
- **Backgrounds (round 9):** the ending's imprint is ringed by broken clods and torn moss (no
  pale outline); the top view's floor is moss, grass, soil and leaf litter with a hard canopy
  shadow; the vista's corner crowns are backlit leaf clusters; S12's light is dappled golden
  pools with leaf-shadow holes instead of converging stripes.
- **Not in v13.** From about 21:45 until 07:44 the session was stopped by a usage limit, so
  the last hours before the 04:30 deadline were lost, and the work started after v13 was not
  rendered until v14. It is kept as `notes/post_v13_wip.patch`:
  - a 15 % bigger, raised head;
  - a resolute eye state from the head lift on (lids up, white-hot cores, a flare on the cue);
  - a fade straight to black;
  - bigger tumbling leaves in S16A and bigger pebbles in S05;
  - the first parts of two helper rounds: an opaque dust wall for the launch, and an
    amber-to-blue dawn sky for S16B.

### v14 — final film (09:33 the next morning, after the deadline, at the user's request)
v13 plus `notes/post_v13_wip.patch`, applied unchanged and rendered without further work:
- **A bigger head (15 %), raised** so the eyes clear the shoulder plates in three-quarter views.
- **Resolute eyes** from the head lift on: the lids open up and the lamps get white-hot cores,
  with a two-frame flare as the eyes resolve in S10; the model sheet shows the state.
- **A fade straight to black** at the end.
- **S16B:** an amber-to-blue dawn sky with a clear sun disc and halo behind the trail.
- **Effects:** no more tails behind thrown debris; bigger tumbling leaves in the flight and
  bigger stones in the ground close-up. (The patch also adds an opaque "wall" dust style that
  no shot uses yet.)
The source in the tree is exactly the code that rendered v14.
