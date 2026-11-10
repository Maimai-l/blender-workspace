# Independent review: Awakening II v7 vs The Moss Keeper

**Verdict.** v7 beats the benchmark as a film. It wins on sunrise light, depth, staging of the beats, hand-drawn timing and effects energy. The benchmark still wins on the thing the brief cares about most: **the robot as a drawn, readable character.** Our robot is a dim, maroon, toon-shaded model with thin uniform lines. It turns into an unreadable dark lump at exactly the two moments that matter: the rise wide (43–47.5 s) and the hero flight (64–67 s). The benchmark's robot is pale, catches the light, has distinctive motifs (peppermint shoulder discs, porthole-wheel chest, teal visor lids) and reads as a full figure in every wide.

The benchmark also still wins on line (wobbly, tapered), painted surface (moss dabs, impasto clouds), its robot-in-the-mist first image (3.0 s), a white shock ring that reads as wind (58.3 s) and a big, lit hero flight figure (64.7–70.7 s).

Method: every frame of both films extracted; cuts, holds and cadence measured from frame differences, change maps and optical flow; luminance and contrast per shot; full-resolution crops of the robot, effects and backgrounds.

---

## 1. Beat by beat (side-by-side sheet)

| Beat (ours / bench) | Better | Why |
|---|---|---|
| Dawn wide (3.15 / 3.0 s) | **Ours, narrowly** | Real sunrise light, aerial perspective and layered hills, against the benchmark's flat light and row of stamped clone conifers. But the benchmark tells the story in one image (the robot looms in the mist), and our bottom third is a navy band of lumpy 3D canopy clumps. |
| Dawn wide 2 (12.26 / 9.0 s) | **Ours** | The ivy trunks frame the kneeling robot in golden backlight with real depth. The benchmark's pale robot dissolves into the mist on a symmetrical clone-tree stage. |
| Bird on shoulder (15.53 / 15.0 s) | **Ours** | The head, shoulder and bird read at once, and the bird is bigger with a clear eye. The benchmark's framing is confusing (a sandy plane and a spider-root tree), although its moss is better painted than our cauliflower clumps. |
| Face close-up (23.53 / 21.5 s) | **Ours, on staging only** | We deliver the beat: the first ray slides across the face. The benchmark's face has more design character (heavy teal visor lids, painted patina). Ours is a boxy rust bin in dim maroon. |
| Chest light (28.5 / 28.0 s) | **Benchmark, narrowly** | Our stepped flicker plays well in motion. As a picture, though, ours is the murkiest frame in the film: maroon on maroon, a CG louvre with bloom, contrast (p95−p5) of 93 against 150–200 in other shots. The benchmark's porthole wheel is an iconic focal point framed by painted moss, even though it glows only faintly here. |
| Rise (45.03 / 45.0 s) | **Benchmark** | Its whole robot reads against the sky, with dust at its feet. Ours has its head and shoulders buried in the canopy, so it reads as a brick column with dotted soil. (In motion, ours is the real kneel-to-stand. The benchmark's robot hardly changes pose in 11 s.) |
| Launch (60.18 / 62.0 s) | **Ours** | Speed lines, drawn flames, debris and real impact frames. The benchmark's dust wall is a flat two-tone noise pattern. |
| Flight (65.5 / 66.0 s) | **Benchmark** | A big, lit, readable hero pose. Ours is a dark, rigid diagonal lump (robot luminance 80 against a sky at 234) with a bloom smudge over the chest. Our sky and debris stream are better, but that doesn't save the shot. |
| Sky + trail (70.75 / 68.0 s) | **Ours** | Exactly the brief: a curving trail of light and mist, the robot a spark at the sun, a mountain for scale. The benchmark's trail is a thin uniform vector stroke. |
| Ending (76.13 / 74.0 s) | **Ours** | The bird beside the empty knee prints is the best storytelling image in either film. The benchmark reuses its clone-tree stage. |

---

## 2. The 10 most damaging problems

1. **The robot reads as toon-shaded CG, not a drawn character.** This is in every robot shot, worst at 43–47.5, 53–56.5 and 64–67 s.
   - Wrong: the contour is a thin, uniform 1–2 px line, about the same weight as the interior lines, with no taper. Volumes are rigid primitives (box head, barrel torso, sphere shoulder pots). The rust is flat decal patches. Next to the benchmark's face at 21.5 s, our crops at 23.5 s and 59.7 s look mechanical.
   - Fix: give the robot its own silhouette/border line set at 2.5–3× the interior weight, with taper and slight pressure noise (Freestyle "Along Stroke" and "Calligraphy" modifiers, or Line Art with a thickness modifier). Replace the decal rust with painted patina (verdigris, streaks under rivets), and paint the shadow masks by hand on the key poses.

2. **The robot's value structure is mud, so the golden light never lands on it.** The emotional close-ups are the darkest shots in the film. The chest at 24.5–29.5 s (torso luminance 61) and the eyes at 35–38.5 s (face luminance 49) are the two darkest, and the face at 18–24.5 s is dim maroon.
   - Fix: raise the local colour to a lighter weathered orange-ochre and keep dark maroon only for cast shadow. Put a warm sun key with a hard terminator and a golden rim on the sun side in every shot. In 24.5–29.5 s, let a slice of sunlight cross the chest.

3. **The hero flight image fails (64–67 s).** The robot is a dark, rigid lump with a fuzzy bloom blob on the chest. Its limbs are unreadable, and it holds one pose for 3 s while the clouds pan by.
   - Fix: re-stage as a ¾ front, slightly low angle, front-lit by the sun, filling about 60 % of the frame. Head up toward the sun, arms swept back, legs trailing. Draw 3–4 key poses on 2s (head turns to the sun, one arm adjusts). Replace the bloom with a drawn 3-tone glow. Keep the fast cloud pan (about 28 px/frame, which works) and add drawn speed streaks.

4. **The ring of wind doesn't touch the forest (56.5–59.5 s).** Corner crops at 56.5, 57.25, 57.9 and 58.75 s show identical tree and fern shapes. Only an expanding ring of cream and lavender puffs moves, and it reads as sand dunes. The benchmark's simple white ring (58.3 s) reads as wind better.
   - Fix: go higher and wider so the ring crosses real forest. Make the treetops flatten outward in a travelling wave, delayed by radius. Add a translucent white shock ring with dry-brush streaks, torn leaves, and mist blown outward. Replace the two candle-like flame tongues on the robot's back with a hot glow under it.

5. **One puff asset is used for every effect.** Soil (29.5–32, 38.5–47.5 s), engine blast (56.25 s), wind (56.5–59.5 s) and launch dust (59.9–61 s) are all the same opaque cream and lavender lobed blobs. At 56.25 s (frame 1350) they sit on the ground like bread loaves, and their colour matches no soil.
   - Fix: design three effects. Soil: dark brown clods and dirt sprays on parabolic arcs. Dust: translucent warm grey with lit tops that thins out. Wind: streaks, leaves and bending grass.

6. **The rise wide's composition kills the key beat (43–47.5 s).** The robot's head and shoulder moss merge with the foreground canopy. Its silhouette is a column, and its eyes are a small orange dot at the top left.
   - Fix: reframe lower and wider so the head breaks the sky gap and the full figure (feet, knees, hands) reads. This should be the clearest silhouette in the film.

7. **Vines and leaves look like vector clip art.** Seen at 4.5–12.5 s and 24.5–47.5 s (frames 672, 742, 1008, 1092): identical bright-green leaf shapes with uniform black outlines on dead-straight strings, like a bead curtain. During the rise they stay plumb-straight while the arm moves.
   - Fix: vary leaf size, hue and rotation. Drop outlines in shadow, darken leaves on the shadow side, sag the strings into curves, and give them drag and secondary swing.

8. **"Soil pouring from the armour" reads as dotted lines** (around 40–47 s, frames 1008 and 1092): stacked brown pellets falling in straight columns.
   - Fix: draw tapered soil streams that break into clumps, with dust trails and a few leaves. Use bigger chunks falling off the shoulder pots, with anticipation (a crack, then a slide).

9. **CG camera and particle motion on 1s.**
   - 47.5–51 s: a 3D tilt on 1s with trunks converging in perspective.
   - 4.5–12.5 s: a perfectly eased 3D tilt (−1 → −19 → −4 px/frame).
   - 32–35 s: soft-edged 3D flock birds animated on 1s.
   - Fix: at 47.5–51 s, hold the camera (or pan a flat painted background) and let the head lift on 2s. Redraw the flock as hard-edged silhouettes on 2s with 3–4-drawing flap cycles. The rise (38.5–47.5 s) already has the robot on 2s with shake. Keep that.

10. **The canopy-gap views look like vector cut-outs** (51–53 s and 61–64 s): flat purple silhouettes with uniform yellow rim lines, and about 1.5 s of an empty hole after the robot is gone (62.5–64 s).
    - Fix: paint the underside of the canopy with backlit, translucent yellow-green leaf masses, darker branches and 2–3 haze layers. Trim the empty tail, or use it for big leaves spiralling through sunbeams.

**Smaller fixes**
- Continuity, 56.5 → 59.5 s: the engines are blazing in the high wide, then the robot stands flameless in a dust-free clearing for 6 frames (59.5–59.71 s).
- 50.25–51.0 s: a hard-edged pink strip (a cloud card's edge) slides in along the top of frame.
- 53–56.5 s and 64–67 s: blue-grey shard patches in the moss on the robot's back read as texture holes.
- 72–79.5 s: the bird's belly turns yellow (white in the bird shots at 12.5–18 and 35–38.5 s).

---

## 3. What reads as 3D/CG, vector or AI art

- **0–4.5 s (S00):** the canopy is instanced 3D clumps, each with the same lit-top, dark-bottom toon ramp, shrinking with perspective. The near band is flat navy. Reads as **CG**.
- **4.5–12.5 s (S01):** a mathematically eased 3D tilt, rigid hard-surface robot volumes, outlined leaf chains. **CG and vector.**
- **12.5–18 s (S02, frame 372):** the moss mounds are toon-shaded "cauliflower" geometry (**CG**). The bird has flat fills and a uniform outline, so it reads as a **vector** mascot.
- **18–24.5 s (S03):** the light shaft is an additive volumetric beam with streaks and soft motes (**CG compositing**).
- **24.5–29.5 s (S04, frame 672):** the louvre grille is 3D geometry in perspective with bloom glare (**CG**). The vines are **vector**.
- **29.5–32 s (S05, frame 742):** the hand is a 3D mitten with a soft gradient and highlight on the thumb. The pebbles are grey spheres. **CG.**
- **32–35 s (S06, frame 796):** the flock is blurry 3D bird particles on 1s. The mid canopy is lavender instanced leaf-card noise. **CG and procedural.**
- **47.5–51 s (S10):** a 3D camera tilt with keystoning trunks. **CG.**
- **51–53 and 61–64 s (S11, S15):** flat purple cut-outs with uniform rim lines. **Vector.**
- **53–56.5 s (S12, frame 1350):** the fan of god rays on the ground is EEVEE volumetrics. **CG.**
- **56.5–59.5 s (S13):** a top view of a 3D model over instanced trees. The river is a flat purple **vector** band.
- **59.75–59.79 s (frames 1434–1435):** stretched-texture smears, a **CG artefact** (barely visible at speed).
- **64–67 s (S16A):** a rigid model with a bloom glow. **CG.**
- **67–72 s (S16B):** the most convincingly 2D shot; only the "pancake" at the trail's base looks like a squashed 3D volume.
- **72–79.5 s (S17):** reads as painted (the ivy is instanced, but acceptable).

Nothing reads as **AI art** (no melted forms or garbled detail). The risk is procedural sameness: identical puffs, leaves, flowers and moss clumps.

---

## 4. Scores (out of 10)

| | Ours v7 | Bench | Note |
|---|---|---|---|
| Design | 6 | 7 | Our sleepy glowing eyes are the best acting in either film (37.5 s, 59.7 s); the rest is a toy-like box with planter shoulders. The benchmark's motifs are distinctive. |
| Composition | 7.5 | 6 | Our framing and depth are strong. Weak at 24.5–29.5, 43–47.5 and 64–67 s. The benchmark reuses one symmetrical stage. |
| Line | 5 | 6.5 | Ours is thin and uniform, with vector-weight outlines on leaves. The benchmark's lines are hand-wobbly and tapered. |
| Colour | 7 | 6 | Our sunrise light is unified in the backgrounds, but the robot is muddy. The benchmark is pastel teal-cream and reads less like sunrise. |
| Animation timing | 6.5 | 4 | Ours: robot on 2s, holds, stepped flicker, shake, impact frames; minus 1s 3D camera moves and flock. The benchmark's robot barely animates. |
| Effects | 6 | 5 | Ours: good flames and speed lines, one puff asset for everything, a ring that moves no trees. The benchmark: a good ring, noise-pattern dust, a vector trail. |
| Climax | 6.5 | 6 | Our structure (impact, canopy breach, trail to the sun) is better, but the hero image fails. The benchmark has a great hero figure and a weak trail. |
| Backgrounds | 7 | 6.5 | Ours has light and depth, but procedural foliage at 0–4.5 and 32–35 s and vector canopies at 51–53 and 61–64 s. The benchmark has painterly dabs but clone trees. |

---

## 5. The single biggest change, and the three weakest shots

**Single change: re-light and re-ink the robot as a cel character, in every shot.**
- Lighter, warmer local colour.
- A sun-side golden key with a hard, hand-shaped terminator.
- A heavy, tapered silhouette line at 2.5–3× the interior weight.
- Painted patina instead of decals.

The robot is on screen most of the runtime, it is the main thing that reads as CG and muddy, and it is where the benchmark is clearly ahead. Fixing it lifts 18–38.5 s and the climax for free.

**Three weakest shots**

1. **64.0–67.0 s (S16A, flight).** Re-stage as a front-lit ¾ hero angle filling about 60 % of the frame. Head raised to the sun, arms swept back. 3–4 drawn key poses on 2s, no chest bloom, drawn speed streaks over the existing fast cloud pan, and readable leg and arm silhouettes against the sky. Steal the benchmark's scale, and keep our sky.
2. **56.5–59.5 s (S13, ring of wind).** Camera higher, so the ring crosses at least 3× the clearing's width. Treetops bend outward in a wave delayed by radius and spring back. A translucent white shock ring with dry-brush streaks. Torn leaves and mist blown outward. A glow under the robot instead of flame tongues. Drop the cream puff ring.
3. **43.0–47.5 s (S09, rise wide).** Reframe so the head and shoulder pots break into the bright sky gap, with the canopy above and clear of the robot. Show the full figure, feet and hands. Replace the dotted soil columns with drawn soil streams and clods. Let the vines swing as it straightens, and hold the final standing pose for 12–16 frames before the cut.
