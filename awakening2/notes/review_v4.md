# Review: Awakening II v4 against "The Moss Keeper"

Independent review, 2026-11-09. Besides the brief, the only file I read was `audio/cues.json` (for shot times); I read no other notes.
Material: `deliver/awakening2_v4.mp4`, the `qa/v4` sheets and random stills, and the benchmark stills.
I also pulled extra frames from both films with ffmpeg:
- consecutive-frame strips of S02, S07, S08, S09, S14, S15 and S16A;
- full-resolution crops of the face, hands, S13 and S15;
- a per-frame difference pass over both films (greyscale, 480×260) to measure cadence and shake;
- luma percentiles per shot, and samples of the robot's paint colour.

Times are in seconds into each film. "MK" means the benchmark.

## Verdict

- **The two films are now close, and the benchmark still edges it.** The benchmark wins where the brief is most explicit about hand-drawn anime:
  - the robot's design;
  - how readable the story beats are (bird, core, rise, launch);
  - timing.
  Ours wins on backgrounds, light, camera ideas and the sky-and-trail end of the climax.
- **Biggest problem: the robot.** It looks like a glossy red vinyl toy built from capsules, not a heavy, ancient, overgrown machine. It is on screen for most of the film, so it sets the "3D toy" read for everything around it.
- **Second: the film moves like CG.**
  - The camera tilts and cranes in 3D with true perspective change.
  - In about 42 % of the seconds, every frame is a new image (benchmark: 26 %).
  - The whole frame shakes on every frame for about 7 s during the rise.
- **Third: at the climax the hero disappears.**
  - 60.0–61.0: one second of a tan blob instead of the robot.
  - 61.5–64.0: a ghosted robot behind sticker debris.
  - 64–67: a rigid statue in a sky that doesn't move.
- Fix those three and ours should beat the benchmark. The forest interiors, the light, the impact frames and the S16B trail are already better than anything in the benchmark.

## 1. Beat by beat (side-by-side sheet)

| # | Beat | MK | Ours | Better | Why |
|---|---|---|---|---|---|
| 1 | Dawn wide | 3.0 | 3.15 | **Benchmark** | It puts the giant in the first shot (a silhouette standing in the mist) over clear near, middle and far layers. Ours has the better sunrise sky, but the vista is empty, and the canopy is smooth clay-like blobs with the same sawtooth fringe on every ridge. |
| 2 | Dawn wide 2 | 9.0 | 12.26 | **Ours, narrowly** | The framing ivy trunks, sun shafts and mist give real depth; the benchmark is a flat, frontal staging between evenly spaced trunks. But its robot looks centuries-overgrown, while ours looks like a freshly painted red toy squatting on clean feet. |
| 3 | Bird on the shoulder | 15.0 | 15.53 | **Benchmark** | Its blue bird stands out against beige metal and green moss, and the tree whose roots grip the shoulder says "centuries". Our green-and-yellow white-eye disappears into a green moss mound full of yellow flowers. |
| 4 | Face close-up | 21.5 | 23.52 | **Ours** | Ours actually plays the beat: a ray with dust motes crossing sleepy, lidded eyes. The benchmark's face is a muddle of camouflage blotches. But our face is garish pumpkin-orange plastic. |
| 5 | Chest light | 28.0 | 28.5 | **Benchmark** | A round porthole that fills with amber light, framed by moss and flowers, is iconic and readable. Ours is a dim glow behind dark louvres in a large, empty maroon field, and the light spills onto nothing. |
| 6 | Rise | 45.0 | 45.02 | **Benchmark** | Full figure, a readable rising pose, dust at the feet. Ours is a red column seen from behind with its head lost in the canopy, and it doesn't read as a giant standing up. |
| 7 | Launch | 62.0 | 60.17 | **Benchmark** | Its billowing wall of cel dust with debris reads as raw power. Ours is a single smooth tan loaf behind ruler-straight speed lines, with no robot in the frame. |
| 8 | Flight | 66.0 | 65.5 | **Ours, narrowly** | Our diagonal climb trailing soil, leaves and twigs has momentum; the benchmark's robot hangs in a static pose (its 66 s and 68 s frames are almost identical). But ours is a rigid red capsule with barely visible engines, in a sky that doesn't move. |
| 9 | Sky + trail | 68.0 | 70.75 | **Ours, clearly** | A sweeping S-curve of light and mist across a golden cloud sea, with the robot a spark at the sun, is the brief's image. The benchmark repeats its flight framing with a thin trail. |
| 10 | Ending | 74.0 | 76.12 | **Ours, narrowly** | Warmer, deeper, with leaves falling through sunbeams and the bird coming back. But the frame is washed out to cream, the bird is about 30 px tall and the imprint can't be read. The benchmark keeps the trail curling in the sky as a link to what just happened. |

**Tally:** 5 beats each. The benchmark's wins are clear-cut, and they fall on story beats (bird, core, rise, launch). Ours are narrow except beat 9.

## 2. The ten most damaging problems (most damaging first)

### 1. The robot reads as a glossy red toy, not an ancient, overgrown giant

**Where:** about 60 % of the film. Worst at 10–12.5 (S01), 20.8–24.5 (S03), 24.5–29.5 (S04), 30.6 (S05), 35–38.5 (S07), 41.1 (S08) and 64–67 (S16A).

**What's wrong:**
- **Construction.** The robot is built from smooth capsules and rounded boxes with two cel tones. There are no dents, plate breaks, chipped edges or drawn wear; the "weathering" is flat decal blotches and vertical pink stripes (11.8, 36.6).
- **Colour model.** The paint jumps between shots: the chest at 26.0 is maroon (#622934), while the face and shoulders at 37.6 are saturated orange (#C85137). That is a jump in hue and value, not a lit variant of one colour.
  - Across the S07→S08 cut (38.5) the robot looks repainted.
  - In S01 and S08 the same paint is veiled to a dusty mauve (#95605A).
- **Overgrowth.** It is only on top surfaces: moss caps on the head, shoulders and forearms, plus identical bead-string vines hanging dead straight. The legs, hands and chest are clean (11.8, 26.0). The benchmark's robot is half buried in moss and has a tree rooted through its shoulder.
- **Not kneeling or grounded.** At 11.8 it squats on two clean feet that sit on top of the ground with a soft shadow, and nothing has grown over its feet or knees in "centuries".
- **Hands.** They are grey cartoon mittens (30.6, 41.1): a Western-cartoon glove, not a machine. The barrel body, grille mouth and mittens read closer to a Western cartoon robot than to the Ghibli reference.

**Fix:**
- **Colour model.** Use one hue family for the metal (oxidised red-brown, or weathered teal-grey). Make the sunlit colour the same hue, lighter and warmer, with its saturation capped. Add a second shadow tone.
- **Wear, drawn into the design.** Dents, rows of rivets, plate seams with weighted lines, chipped paint, rust bleeding from the seams, lichen. Delete the decal stripes.
- **Overgrowth that grows from the ground up.**
  - Soil banked against the shins and roots over the feet.
  - Ferns in the elbow and knee joints.
  - Moss streaks following where rain runs off.
  - A sapling rooted in a crack, not perched on top.
  - Vines that hang in curves, with leaves of varied size, some of them in shadow.
- **Pose.** A real kneel: one knee down and sunk into the soil, the other foot forward, a hand on the knee, the head bowed.
- **Hands.** Segmented mechanical fingers with knuckle plates.

### 2. It moves like CG: 3D camera, motion on 1s, long shakes

**Where:**
- 3D camera moves: the S01 tilt (6.5–10.5), the S10 crane (47.5–51) and S13 (56.5–59.5).
- Shakes: S05 (29.6–32.0) and S08–S09 (38.9–46.0).
- The slow push-in through S03 (18–24.5).

**What's wrong:**
- **True 3D camera.** S01 rotates the camera, so the converging trunks straighten with full parallax. S10 cranes back, and the perspective of every trunk changes. A hand-drawn film slides flat painted layers instead.
- **Cadence.** A rough per-second classification of both films:

  | Motion type | Ours | MK |
  |---|---|---|
  | New image on every frame | 33 s (42 %) | 21 s (26 %) |
  | On 2s/3s | 38 % | 51 % |
  | Holds | 20 % | 22 % |

  The amount of holding is about the same, but our holds are mostly the eased-in start of a camera move.
- **Shake.** The whole frame jitters on every frame for about 2.5 s in S05 and about 7 s through S08–S09. Background areas where nothing is animated change by 5–15 grey levels per frame.
- **Grain.** A screen-space paper grain re-randomises every 2 frames, so the frame is never actually still.
- **Rise and head-lift.** Both are continuous slides, not key poses with holds.

**Fix:**
- **2D camera moves.** Use flat multiplane trucks and pans. For S01, paint a tall background and pan down it. For S10, truck in on the layers.
- **Step the character animation** on 2s, and on 3s for the heavy rise, built from key poses and breakdowns. Hold 8–24 frames on:
  - the eyes opening (36.3);
  - the head raised (about 50);
  - the crouch before launch (about 55.8–56.2);
  - the end of S16B.
- **Shake only on impacts** (the groan hits at 39.4 and 40.1), on 2s, decaying within about 12 frames.
- **Fix the grain to the painted layers** (static per cel and background) instead of on the screen.

### 3. The climax loses its hero (59.5–67)

**What's wrong:**
- **S14 (launch).**
  - 59.49–59.70: the robot stands upright with its arms at its sides; there is no crouch in this shot.
  - 59.74: one smear frame. At 59.78 only the legs are left at the top of the frame.
  - 59.82 and 59.87: two impact frames (a black/yellow silhouette), which are good.
  - 59.91–59.99: jet flames at the top edge.
  - 60.0–60.95 (about 23 frames): a smooth tan dome grows behind ruler-straight speed lines.

  So for about a second at the moment of launch, the frame shows a dust blob instead of the robot.
- **S15 (through the canopy).** From 61.48 to the cut at 64.0 the robot is a translucent ghost under a veil of glare. By 62.6 it has shrunk to a faint orange smudge. It is buried behind rotating sticker debris: planks, twigs and leaves with pink trail wedges. The planks read as broken furniture.
- **S16A (climb).** The pose is identical from 64.1 to 66.8: arms down, legs together. The engine is a small flick of flame (about x 840, y 440 at 65.0), and the sky doesn't move. It "tears into the sky" with no sense of speed.

**Fix:**
- **S14.** Crouch and hold for 6–8 frames, then a 2-frame upward stretch and smear, then the impact frames. Then keep the robot in shot for at least 12 frames, blasting upward with its legs trailing, while a wall of dust billows out at ground level.
- **S15.** Draw the robot as a dark, rim-lit silhouette against the bright gap, with no glare over it and the engines blazing toward the camera. Use only leaves and branches for debris, drawn smaller and thrown outward.
- **S16A.** Give it a flight pose: back arched, arms swept back, head toward the sun. Add long jet flames, and start the mist trail here. Pan the clouds past on 1s, or use a speed-line background.

### 4. The key story beats don't read

**What's wrong:**
- **Bird (S02, 15.5).** The landing is the beat, and the bird is camouflaged: green and yellow on a green mound with yellow flowers. There is no value or hue separation.
- **Chest light (S04, 25.5–29.5).** The core is a dim orange behind six dark louvres, in a flat maroon field that fills about 60 % of the frame. No light falls on the vines, moss or rivets in front of it, and the heartbeat pulses are barely visible.
- **Eyes igniting (S07, 36.3–38.5).** The eyes turn amber inside a saturated orange face, so there is almost no value contrast; it reads as "eyes slightly yellower".
- **Rise (S09, 43–47.5).** It is staged from behind and to the side, with the head above the frame inside the canopy. We never see the giant stand and look.

**Fix:**
- **Bird.** Give it a contrasting colour (a blue flycatcher, or a cream bird with a red breast). Land it on bare metal near the face, hold 8–12 frames after touchdown, and give it a head tilt.
- **Chest light.** Put the chest in shadow and make the core a round lens with a hot white-yellow centre. Let light leak through rivet holes and seams, rim-light the vine leaves in front, and make each pulse a visible halo 2–3 values brighter.
- **Eyes.** Put the sockets in deep shadow under the brow. The eyes go from black to a white-hot core with an orange bloom: a short flicker on 2s, then hold.
- **Rise.** Shoot it from a low three-quarter front angle, with the full figure in frame and soil pouring off. Use key poses with holds:
  1. Pushing off, hand on knee.
  2. Mid-rise, back curved, head down.
  3. Standing, head up, clearing the frame.

### 5. Effects: dust, soil and wind are smooth blobs and balls

**What's wrong:**
- **Dust.**
  - 41.1: a beige ball (about 190 px) with a purple lower half sits at the knee; it reads as a beach ball.
  - 44.4–46.9: lumps at the feet.
  - 56.3: a row of mushroom caps along the ground.
  - 60.0–61.0: one loaf shape that only grows.
- **Soil.** It doesn't pour. It is outlined crumbs sprinkled evenly over the whole body (41.1).
- **Ring of wind (57.0–58.5).** A donut of identical cotton balls and small bubbles with lit caps; it reads as popcorn. It is also shown on a lawn right around the robot, not crossing the forest; the benchmark's high wide shot over the canopy delivers "across the forest", if weakly.
- **Trail (70.75).** A string of equal spheres with hard purple halves.

**Fix:** design the effects as hand-drawn effects animation.
- **Dust.** Cauliflower billows with three tones and hard shadow shapes, irregular silhouettes and small wisps breaking away. They curl, thin out and dissipate over 12–24 frames, on 2s.
- **Soil.** Streams of clumps pouring off the shoulder and forearm ledges, each breaking up into dust.
- **Ring of wind.** A flattened ellipse shockwave racing over the treetops, seen in a true high wide shot. The trees bend in a wave and leaves are torn up behind it.
- **Trail.** A tapering ribbon of uneven lumps with wispy edges, dissolving at the tail.

### 6. Line work: hairlines on the hero, heavy outlines on the props

**What's wrong:**
- **Interior lines.** The robot's interior seams are 1-px hairlines of constant width: the eyelid seam and shoulder seams at 36.6, the chest panel at 26.0.
- **Contours.** At mid distance (11.8, 41.1) the robot's outer contour is as thin as its seams and greyed out by the haze. The hero's silhouette ends up with less ink than the vines hanging in front of it.
- **Props have heavier lines than the hero.** Every vine leaf (11.8, 30.6), soil crumb (41.1) and debris sticker (61.7, 65.0) carries a heavier, uniform outline than the robot, and so does the bird. The dust has no line at all.
- So three line languages share one frame, and the line hierarchy is upside down.

**Fix:** one inking spec for the whole film.
- The hero's outer contour is the heaviest line. It tapers, is heavier on the shadow side and keeps the same width on screen at every shot size.
- Interior lines are thinner, with taper and breaks.
- Props and effects are thinner still, or use coloured lines (brown for soil, dark green for leaves).
- No hairline seams on smooth areas.

### 7. Backgrounds that give away the 3D, including a visible cube

**What's wrong:**
- **S00 (0–4.5).** The canopy is soft clay blobs with smooth gradient shading, and the same sawtooth fringe runs along every far ridge.
- **S13 (56.5–59.5).**
  - **Bug:** at 57.1–57.8, around x 520–880 and y 720–1020, a bush is a box textured with leaves, with its cube edges drawn as thin lines. It shows whenever the dust passes behind it.
  - The ferns are flat, lacy, semi-transparent cards.
  - There is no canopy at all, although S11 framed the gap with dense canopy.
- **S16B (67–72).** The cloud sea is faceted, chunky blocks repeated to the horizon. The mountains are flat triangles with ruler-straight strokes.
- **S06 (33.2).** Every canopy clump has the same yellow rim fringe.

**Fix:**
- **Now:** delete the cube bush or replace it with an irregular shrub, and stop drawing its edges.
- **S00:** paint the vista as a matte, with stroke texture and a variety of tree species.
- **S13:** a painted high-angle canopy with the gap, the robot inside it and the ring crossing the canopy.
- **S16B:** painted cumulus at varied scales.
- **S06:** vary the rim fringe per clump.

### 8. Personality and acting are thin

**What's wrong:**
- The eyes read sleepy and kind in close-up (36.6) but angry in low angles (41.1, 47.6–48.6), because the lid line cuts down toward the nose.
- When the bird leaves, the face does not change at all from 36.9 to 38.45: no glance, no blink.
- The head-lift in S10 is about 10° and drowned by the crane move.
- The benchmark's visor face reads as tired and kind throughout.

**Fix:**
- Make the eyes round lenses with a separate lid that tilts up at the outer corners (kind), never down and inward.
- Have the eyes follow the bird as it flies off, and give the robot a slow blink before the rise.
- Hold on the robot looking up at the gap (about 50–51) before cutting to the POV shot.

### 9. The ending has no final image

**What's wrong:**
- From 72 to 79.5 the clearing is washed out (median luma 135–142).
- The imprint where the robot knelt is a vague patch of dirt, the bird is about 30 px tall, the trail isn't visible, and nothing holds before the fade.
- The fade passes through a muddy olive-brown (78.5).

**Fix:**
- Frame the shot around a clear imprint filled with light: knee hollows, hand prints, torn roots.
- Let the bird hop into it at a readable size (at least 120 px tall), and keep the curving trail visible through the canopy gap.
- Hold for 2 s, then fade to black through a cool dark.

### 10. Finishing: screen-wide grain, glare veils, a pale sky act

**What's wrong:**
- The paper grain boils on 2s over every shot. Because it doesn't belong to any painted layer, it reads as a filter.
- Glare and haze veil the robot's upper body (11.8, 41.1); S15 is the extreme case.
- In the sky act the value range collapses: at 70.75 the darkest 1 % of pixels are grey 109 of 255, so nothing in the frame is dark. The benchmark is similarly pale here, so this is not where we lose to it, but it is where we stop looking theatrical.

**Fix:**
- Bake the texture into the painted layers.
- Keep glare around the light source only.
- Keep at least one dark accent in every shot: the robot's silhouette, a cloud shadow or a bird.

## 3. What reads as 3D/CG, vector or AI, shot by shot

| Time | Read | What |
|---|---|---|
| 0–4.5 (S00) | 3D | Clay-like canopy blobs with soft gradient shading; the same sawtooth fringe on every ridge. |
| 6.5–10.5 (S01) | 3D camera | The tilt rotates the camera: converging trunks straighten, with true parallax. |
| 11.8 (S01) | 3D, vector | The robot's capsule and rounded-box shapes with cel bands; clean feet placed on the ground over a soft contact shadow; vines as identical bead strings with heavy outlines. |
| 14.0–14.4 (S02) | 3D rig, vector | The wings are flat grey planes rotating. The body is flat-shaded, with a uniform outline and an icon-like eye. |
| 20.3–21.8 (S03) | 3D lighting | The edge of the sunlight slides across the face and hugs its 3D forms, like a moving spotlight. |
| 22.5–24.5 (S03) | 3D | Saturated orange plastic. |
| 24.5–29.5 (S04) | 3D | A soft additive glow behind the louvres; a large, smooth crimson surface with decal blotches. |
| 30.6 (S05) | 3D/toy, vector | A grey mitten hand of smooth rounded fingers with a perfect cel terminator; the leg is a smooth cylinder; outlined vines. The shake changes every frame. |
| 33.2 (S06) | 3D | Instanced canopy clumps, each with the identical yellow rim fringe; the flock is repeated silhouettes. |
| 36.6 (S07) | 3D | A rounded-box head; constant-width hairline seams; a highlight band following the curvature of the shoulder pad. |
| 38.9–46.0 (S08, S09) | 3D | The shake changes every frame; the dust is a beach ball (41.1); crumbs are emitted evenly over the body; the limbs rotate rigidly. |
| 47.5–51 (S10) | 3D camera | A crane move with a perspective change on every trunk. |
| 53.5–56.3 (S12) | 3D | The moss on the back is a flat slab, like a planter box. The flames are fine and read as anime. |
| 56.5–59.5 (S13) | 3D | The leaf-textured cube with drawn edges (57.1–57.8); lacy, semi-transparent fern cards; spherical dust balls with lit caps. |
| 60.0–61.0 (S14) | 3D, vector | An inflating smooth dome; ruler-straight radial lines. |
| 61.5–64.0 (S15) | 3D compositing, vector | The robot veiled into a translucent ghost; flat plank, twig and leaf stickers rotating, with pink trail wedges. |
| 64–67 (S16A) | 3D, vector | A rigid model drifting in a static sky; debris stickers with uniform outlines. |
| 67–72 (S16B) | 3D, vector | A low-poly-looking cloud sea, repeated; a trail of equal spheres; a red and yellow fringe along the trail's edges like chromatic aberration; flat triangular mountains. |
| 72–79.5 (S17) | Mostly fine | Procedural ivy scatter on the trunks, all leaves the same size. Otherwise it reads as painted. |
| Throughout | Filter | Screen-space paper grain that re-randomises every 2 frames, independent of the layers. |

**AI:** nothing in our film reads as AI-generated. If anything, the benchmark has more of a filter look (dry-brush clouds at 3.0, posterised camouflage blotches on the robot).

## 4. Scores (out of 10)

| | The Moss Keeper | Awakening II v4 | Note |
|---|---|---|---|
| Design | 7 | 5 | MK's robot is overgrown, kind and iconic (porthole core, pinwheel ears, tree on the shoulder). Ours is a red capsule toy with mitten hands and a colour model that jumps. |
| Composition | 6 | 6.5 | Ours has more depth and variety (framing trunks, POV up the gap, diagonals, the S-curve trail) but fails readability at the key beats. MK is centred and frontal, and reuses one clearing for many shots. |
| Line | 6 | 5 | MK's line is thin but consistent. Ours: hairline seams, thin hazy contours at distance, props outlined heavier than the hero. |
| Colour | 6.5 | 6.5 | Ours has the better light: sun rays, backlight, a golden sky. MK integrates its robot better; ours turns maroon or pumpkin-orange against the gold. |
| Animation timing | 6 | 4.5 | MK is mostly on 2s and 3s with real held poses. Ours: 3D camera moves, 42 % of seconds on 1s, a 7 s shake, and few key poses. |
| Effects | 6 | 6 | Ours: excellent impact frames, flames, bird burst, debris stream and trail idea, but the dust and soil are blobs and balls. MK: a strong dust wall; weak ring and trail. |
| Climax | 5.5 | 6 | Ours has the bigger arc (ignite → impact → through the gap → trail across the sun) but loses the hero for about 4 s. MK's hero is always readable, but its flight is a held pose. |
| Backgrounds | 6 | 7 | Our forest interiors (6.5, 44.4, 73.0) beat MK's reused clearing and dry-brush filter look. Our vista, top view and cloud sea are the weak spots. |
| **Mean** | **6.1** | **5.8** | |

## Keep these: they already beat the benchmark

- The forest interiors with layered mist and dappled ground (6.5, 30.6, 44.4, 73.0).
- The S03 sun-ray idea.
- The S06 bird burst.
- The S11 POV up at the gap.
- The S12 backlit ignition flames.
- The two impact frames (59.82, 59.87).
- The S16A debris stream.
- The S16B S-curve trail across the sun.

Fix the robot, the motion signature and the climax without losing these.
