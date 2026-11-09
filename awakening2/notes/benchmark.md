# Benchmark study: The Moss Keeper vs. Awakening (v1)

Studied on 2026-11-09 from the decoded MP4 of The Moss Keeper (80.6 s, 1920×1040, 24 fps,
1935 frames) and from `awakening/deliver/awakening.mp4` (56 s, 1920×1080). Frames were pulled
at 1 fps for contact sheets, at full resolution at every beat, at 6 fps through the launch,
and frame-to-frame differences were measured to read the timing (on 1s / 2s / 3s).

## The Moss Keeper — shot by shot

Cuts found with scene detection: 6.25, 12.5, 18.5, 25, 30.5, 32.5, 34.75, 37.5, 48.5, 52.5,
54.75, 57.25, 60.4, 61.25 (flash), 61.4–62.8 (launch), 64.7, 70.7, end 80.6.

| # | Time | Shot | What works | What fails |
|---|------|------|-----------|-----------|
| 1 | 0–6.3 | Extreme wide over the forest at dawn: lilac/pink cloud bands, a purple ridge, a mist sea, a row of conifers in front; the robot a faint grey ghost right of centre | Soft dawn palette, mist sits between layers | Robot is ~6 % of frame height and nearly invisible; cloud bands are the same wavy strip stamped 4×; the foreground conifers are one shape repeated; the slow push is on 1s and reads as a 3D dolly; no focal light |
| 2 | 6.3–12.5 | Forest interior, medium-wide: the robot *standing* (the brief says kneeling) between straight trunks, vine curtain at the top, grass at the bottom | Framing layers (canopy, trunks, grass); hanging vines | The robot is the same value and hue as the moss and the background trunks, so its silhouette dissolves (a topiary); every trunk is the same straight cylinder; static for 6 s |
| 3 | 12.5–18.5 | Close shot on a shoulder with a sapling's roots; a blue cartoon bird lands | Moss painted with dabs; roots are a nice idea; bird on 2s | You cannot tell which part of the robot this is; metal is flat beige/lilac with camouflage blotches; the bird is a Western cartoon (round blue body, big eye) |
| 4 | 18.5–25 | Face close-up: a lumpy head with two teal goggle lenses, red/white pinwheel discs, moss tufts; a cream "sun ray" polygon slides across it; a star glint on a lens | Light sliding over the face is the right beat; flowers | The face does not read as a face (no brow, no eye shapes, no expression); straight thin polygon lines cut across the forms; rust is thresholded noise in 3 colours; the ray is a flat sliding shape (web animation); light is on 2s but the moss is static |
| 5 | 25–30.5 | Chest: a round spoked grate, turns orange | Clear read of "light inside the chest" | Light only swaps the fill colour; no flicker build, no spill on the moss, no glow into the air; static 5 s |
| 6 | 30.5–32.5 | Top-down pond rippling (the tremor) | Original idea for the tremor | Reads as a hole in a carpet; ripples tiny |
| 7 | 32.5–34.8 | Shoulder again: the bird flees, clods fall | Debris on 2s | Same framing as shot 3, so it feels like a repeat |
| 8 | 34.8–37.5 | Birds burst over the canopy against the sky | Nice sky | Birds are dark chevrons with no flap design; the canopy is a uniform green mass |
| 9 | 37.5–48.5 | 11 s locked medium-wide: the (already standing) robot shakes, beige dust puffs at its feet, debris | Robot on 2s with real holds | There is no rise: it never gets up from a kneel; one angle for 11 s; dust puffs are beige noise blobs |
| 10 | 48.5–52.5 | Low angle on head and shoulders: the eyes glow yellow, a sapling on the shoulder, clouds behind | The best frame of the film: framing trunks, colour, the tree | Face still a lump with a half-closed visor; lines thin and uniform; head lift is tiny |
| 11 | 52.5–54.8 | POV up into a star-shaped canopy gap | Clear motivation | Flat cut-out hole with a radial gradient |
| 12 | 54.8–57.3 | Side view: arms raised with cylinder engines; orange cone flames ignite | Ignition is shown | Pose stiff (puppet joint rotation); flames are clean cones (vector) |
| 13 | 57.3–60.4 | Top-down: a white double ellipse expands around the robot | A ring is shown | Reads as a UI graphic (two clean white ellipses), not wind: no dust, no leaves, nothing bends |
| 14 | 60.4–61.3 | Wide forest, robot crouched, glow at its feet | Anticipation crouch | Very short, no hold |
| 15 | 61.3 | 1–2 white frames | Impact flash | Pure white, no silhouette design |
| 16 | 61.4–62.8 | Launch: fire columns, a wall of brown thresholded-noise dust | Big and fast | The dust is noise blobs; the robot leaves frame without smears |
| 17 | 62.8–64.7 | Looking up through the canopy: the robot recedes into a glow | Good idea | The robot is a tiny bright sprite |
| 18 | 64.7–70.7 | Sky above a cloud sea: the robot flies diagonally, large at first, on 3s; a thin white line trails behind | Robot large and readable; on 3s against clouds moving on 1s | The "trail of light and mist" is a 3-px white line; cloud sea is one band pattern repeated; the robot's pose is a static T |
| 19 | 70.7–80.6 | Coda in the forest: a white squiggle in the sky, leaves fall, the bird returns | Quiet ending, leaves on 2s | 10 s, mostly static; the trail squiggle is a thin line |

Measured timing: robot moves on 2s (rise) and 3s (sky); the face light on 2s; the opening wide
and the coda move on 1s (slow software pushes and drifts).

Design of their robot: a rounded stone golem — boulder shoulders, a lumpy head with goggle
lenses, red/white pinwheel discs on stalks, a round spoked chest grate, red stripes. It reads
as clay or stone more than as a machine; it has no single readable silhouette idea and no
readable face.

Their strengths (what we must at least match): framing layers in every forest shot; the robot
fills the frame in the close and sky shots; rich, warm colour; painterly moss texture; dense
foliage detail; a sapling growing on the robot.

## Awakening v1 (ours, 56 s) — shot by shot

| # | Time | Shot | What fails |
|---|------|------|-----------|
| 1 | 0–7 | Wide, push-in | Lollipop 3D trees repeated in rows; a ground plane to the horizon (a park); the robot ~15 % of the height in the middle of an empty lawn |
| 2 | 7–13 | Shoulder and bird | A huge flat-green pauldron blob; the bird is a few pixels; no texture, no ink on most shapes |
| 3 | 13–18 | Face in the first ray | Unreadable blocks of grey, brown and green; a dome with a white spot; you cannot find the eyes |
| 4 | 18–23 | Chest lamp | Clean porthole with an X; reads as vector art; flat grey plate |
| 5 | 23–28 | Wide tremor | Robot tiny, birds invisible |
| 6 | 28–38 | The rise | One static medium-wide for 10 s; robot small; the rise is a slow software ease |
| 7 | 38–43 | Head lifts | Primitive spheres and cylinders; Freestyle lines drift off the fills |
| 8 | 43–47 | Ignition and ring | The shockwave is a grey slab |
| 9 | 47–49 | Launch | No anticipation that reads; no smear |
| 10 | 49–56 | Up through the gap | The robot is a dot; the trail a thin line; the sky an empty pink gradient |

v1 failures we must not repeat (from the brief, confirmed above): tiny robot in wide shots;
unreadable close-ups; a single static rise shot; climax robot is a dot and the trail invisible;
a toy made of primitives; flat moss blobs; sketchy drifting Freestyle ink; painterly BG and
flat robot that do not belong together; a 3D ground plane to the horizon; slab shockwave.

## Scorecard (0–10) and how Awakening II will win each line

| Category | Moss Keeper | v1 | Awakening II target | How |
|---|---|---|---|---|
| Robot design | 5 | 3 | 8 | Designed in 2D first (3 concepts → one model sheet). One strong silhouette idea, readable at thumbnail size; a face with a heavy brow and two round eyes behind mechanical lids that can droop, open and narrow (dormant / waking / resolute); a chest furnace grille for the core light; a back with two engine bells for the launch. Built as smooth SDF forms (no visible polygons), kept on-model by one 3D model drawn by our own look engine |
| Composition | 7 | 3 | 8 | Every shot boarded in screen space first with framing layers, eye line, light direction and robot scale. Trees and birds measure the robot. Two alternatives for each key beat |
| Line | 4 | 3 | 8 | Own ink: lines traced from ID / depth / normal discontinuities, so they sit exactly on fill edges; variable width (heavier on the silhouette and on the shadow side), tapered ends, wobble on 2s; panel lines and rivets as thin detail lines; no lines on shadow edges (as in cel animation) |
| Colour | 7 | 4 | 8 | Designed palette per shot; cel fills in 2–3 tones; designed hard-edged shadow shapes (cleaned and simplified, no 3D noise); chipped paint and rust as hand-designed decals with crisp edges; shadows tinted with the same cool colours as the background so robot and BG belong to one picture; warm rim light at sunrise |
| Animation timing | 5 | 4 | 8 | Robot on 2s/3s with real holds and strong keys; anticipation before every big move; overlapping action in vines, the tree on its back, soil and debris; cameras and shake on 1s; no software easing on the robot |
| Effects | 4 | 2 | 8 | Drawn 2D effects in 2–3 hard-edged tones with designed silhouettes on 2s: billowing cel dust, a wind ring that flattens grass and throws leaves and dust, layered cel flames, smear frames and an impact frame for the launch, a wide curving trail of light and mist |
| Climax | 6 | 2 | 9 | A hard anticipation, smears, an impact; then a wide gold-sky shot where the curving trail is big, bright and readable and the robot is a designed silhouette at its head; leaves spiral down through sunbeams |
| Backgrounds | 7 | 3 | 8 | Painted per shot in screen space with a gouache brush engine: every tree unique, layered foliage, mossy roots, aerial perspective in 4–6 depth layers, no 3D ground plane |

The beats we will compare side by side for every version: dawn wide, bird on the shoulder,
face close-up, chest light, rise, launch, ending.
