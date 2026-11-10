# Awakening II v11: independent review

Material: v11 (79.5 s, 1908 frames), The Moss Keeper ("MK", 80.6 s) and the qa/v11 sheets. I pulled full-res stills and crops, diffed consecutive frames, and measured the robot's own spacing with optical flow (camera shake subtracted).

**Verdict.** v11 now beats MK on staging, story and acting, and takes 6 of the 10 matched beats. It still does not pass as a finished theatrical 2D film, for two reasons:
- The robot reads as a cel-shaded 3D model in every shot.
- The climax effects (ring, launch, trail) look like CG particles and vector shapes.

MK still wins wherever a single painted image carries the beat: the vista, the chest light, the rise still and the launch dust.

**Measured timing.**
- The robot is on 3s in S08/S09 (it moves every third frame) and on 2s in S07, S10, S12 and S16A. Camera moves, the S16A sky scroll and the S06 flock are on 1s. This is correct practice.
- Real holds exist: 41.0–41.7, and 54.5–55.7 after a good accelerating crouch.
- The in-betweens are spline-perfect. The S10 head lift (48.1–48.8) steps 3.5, 8.6, 13, 16, 18, 17, 15, 11, 6, 2 px: a symmetric bell. S09 is two identical smooth bumps.
- The stand "thud" at 45.6 is only a 7 px camera jolt; the body does not settle.

## 1. Matched beats (MK time / our time)

1. **Dawn wide (3.0 / 3.15): MK.** MK shows the giant in the mist from the first frame, behind clear depth planes. Ours has better light but no subject, and its lower half is a lilac murk of filter-like daubs.
2. **Dawn wide 2 (9.0 / 12.26): ours.** A kneeling giant framed by huge trunks in warm haze has scale and follows the brief. MK's robot stands among thin repeated poles, although its head-to-toe overgrowth says "centuries" better than our moss caps.
3. **Bird on the shoulder (15.0 / 15.53): ours.** Our bird is the subject and it acts: flare, touch, hop and settle on 2s, 13.5–17.0. MK's bird is a slid sticker, but its sapling with roots gripping the shoulder is better storytelling than our cushion moss.
4. **Face close-up (21.5 / 23.53): ours.** A readable face with heavy lids sits under a slanted beam with motes. MK's face is an illegible stack of goggles and camo. MK's face does look older; ours looks like clean terracotta plastic.
5. **Chest light (28.0 / 28.5): MK.** A round amber porthole filling the frame is an iconic image. Ours is a small Gaussian glow behind a radiator grille on a big plain panel, and no light spills onto the moss.
6. **Rise (45.0 / 45.03): MK, as a still.** MK's robot is large and overgrown, with flat two-tone cel dust. Ours is small and boxy: the head is buried, the back tree merges with the canopy, and the soil reads as tar drips. In motion ours genuinely rises. MK keeps one standing pose from 38 to 46 and simply lifts it while debris falls.
7. **Launch (62.0 / 60.17): MK.** MK's opaque two-tone dust wall under a light column is the best effect frame in either film. Ours has legs and flames leaving the top edge over translucent bubble dust and pebbles with orange cone tails.
8. **Flight (66.0 / 65.5): ours.** Ours has a hard diagonal, flames, streaming debris and lit eyes turned to the sun; MK's robot floats. Still, our silhouette is a barrel under broccoli: the arms are lost and the raised arm reads as a pipe.
9. **Sky + trail (68.0 / 70.75): ours.** This is the brief's image: a long curve over a cloud sea toward the sun. The execution is weak:
   - the trail is a flat pastel ribbon with lilac polka dots and no glow;
   - the sky is flat lemon;
   - the sun barely registers.
10. **Ending (74.0 / 76.13): ours, narrowly.** The bird lands by the imprint, so the frame tells the story of the absence. MK's frame has more depth, real light shafts and the trail still curling in the sky. Ours is low-contrast cream haze, and the imprint reads as brown stains.

## 2. The ten most damaging problems

1. **The robot is visibly a cel-shaded 3D model** (all robot shots; clearest at 12.3, 28.5, 42.0, 49.0, 65.5).
   - Shadows are shadow-map facets: angular wedges and zigzags that follow geometry, not design.
   - The ink is uniform, rivets run in exact rows, and the slats and panels are perfect primitives.
   - Every move is a rigid re-projection.

   *Fix:*
   - For each key drawing, use one or two designed shadow shapes per volume, with curved edges and no facet under about 40 px.
   - Taper the ink: heavy on the shadow side and under-planes, thin or broken on the lit side.
   - Cut rivets and chip decals by about 60 %.
   - Add a small low-frequency shape wobble that changes only when a new drawing appears, so drawings differ the way hand drawings do.
2. **The launch (S14, 59.5–61.0) has no power.**
   - The robot starts upright and calm (59.50–59.71); the S12 crouch is lost.
   - The impact silhouette (59.83–59.88) is an unreadable stump-shaped blob.
   - The robot is out of frame by 60.4, leaving 0.6 s of empty forest.
   - The dust is stacked translucent circles, and the debris has motion-graphics cone tails.

   *Fix:* see section 5.
3. **The rise effects look like tar and clip art** (S08–S09, 38.5–47.5).
   - The soil curtains are dark-brown vertical drips; at 42.0 they look like chocolate running off the pauldron.
   - The vines are chains of identical leaves hung evenly everywhere, like bead curtains.

   *Fix:*
   - Make the soil lighter and warmer: clumps that break off edges along arcs, trail two-tone dust, then hit the ground and puff.
   - Keep 3–4 heavy, irregular vines that pull taut, snap and whip with overlapping action, instead of thirty uniform danglers.
4. **The S13 ring of wind (56.5–59.5) is a thin chalk ellipse.**
   - It is visible only from 56.75 to 57.50. The shot then holds a near-static top view with streaks for 1.75 s.
   - From straight above, the robot is a heap of moss and planks around a soft orange ball, so we never see who makes the wind.

   *Fix:* see section 5.
5. **The eyes never become resolute.** From 38.0 through S10 (50.8), S14 (59.6) and S16A (65.5), the lids sit at the same sleepy half-mast. The hero launches looking drowsy, so the awakening has no arc in the face.

   *Fix:*
   - Add a "resolve" state: lids up, the brow plate angled down at the inner corners, a hot white core in each eye.
   - Hit it on the eyes_resolve cue (49.7) with a 2-frame flare, and keep it through the flight.
6. **The S16B trail and sky (67.0–72.0) have no light.**
   - The trail is a semi-transparent pink band with evenly spaced lilac ovals, like a vector brush.
   - The sky is flat lemon and the sun is faint.
   - The robot ends as a speck with a CG lens star.

   *Fix:* see section 5.
7. **The spacing is mechanical.**
   - The stand has no anticipation dip, no overshoot and no settle; the 45.6 thud is camera-only.
   - S10's lift is a symmetric bell.

   *Fix:*
   - Time the moves from keys and breakdowns: dip 4–6 frames before each push, take the middle fast on 2s, overshoot 1–2 frames on the stand, then settle with the knees compressing and dust on the thud.
   - In S10: a slow start, a beat, then a decisive snap up into a hold of 12 frames or more.
8. **Backlit shots turn muddy.**
   - In S07 (35.0–38.5) the face is dark maroon under a milky full-frame ray overlay. At 38.0 the mouth slats read as ghosted pale hairpins.
   - In S12 (53–56.5) a dark red-brown back sits against a grey-blue floor.
   - The end fade (77.5–79.5) passes through a cool grey.

   *Fix:*
   - Use a lighter, cooler designed shadow colour with warm bounce light.
   - Draw the ray as a hard-edged light shape on the surfaces it touches, plus a soft glow.
   - Fade straight to black.
9. **The silhouette breaks down at wide and unusual angles.**
   - S09 (45.5) is a box with a tiny buried head, and the back tree merges into the canopy.
   - In S12 (56.0) the head is hidden, the engine bells read as grey pipes, and the smoke is identical cotton balls.
   - In S16A the arms are lost.

   *Fix:*
   - Make the head 15–20 % bigger and raise it so the eyes clear the pauldrons in 3/4 views.
   - Stage the back tree against sky, not canopy.
   - Give the engine bells a lit rim and an inner glow.
   - Re-pose S16A with one arm reaching to the sun.
10. **Backgrounds repeat, and some time is dead.**
    - The far trunks are identical, evenly spaced pale poles (S08, S14 at 60.4, S17).
    - The ivy is one stamp, scattered (9.0), and the S00 foliage looks filtered.
    - S17 is cream haze with no defined light shafts.
    - In S11 (51.0–53.0) only about 0.3 % of pixels change, so it plays as a still.

    *Fix:*
    - Vary the far trunks (lean, width, forks, gaps) and paint the ivy in clusters.
    - In S17, paint 3–4 defined shafts with motes and frame them with darker foreground.
    - In S11, drop leaves across the sun and sway the canopy on 3s.

## 3. What reads as 3D/CG, vector or AI

- **0–4.5 (S00):** posterized "paint-filter" daubs on blob trees. This is the nearest thing to an AI or filter look in our film.
- **9.0:** the trunk ivy is one leaf stamp, scattered.
- **12.3:** shadow-map facets on the torso; the vines are a vector pattern brush.
- **15.5:** the moss is identical round cushions with identical two-tone shading. The bird is vector-clean, which is acceptable for anime, but its line has no taper.
- **18–24.5:** the face is built from smooth plastic primitives with perfect ellipse eyes. The beam is a streaked translucent overlay.
- **28.5:** the slats and rivet rows are perfectly regular, and the core is a Gaussian bloom ball.
- **33.5:** the sky is a smooth digital gradient.
- **35–38.5:** a milky ray overlay across a dark face, with ghosted slats.
- **38.5–47.5:** rigid model rotation on spline eases, and tar-like soil.
- **47.5–51.0:** a perspective-perfect barrel torso tilts on a spline. It reads as a 3D camera on a model.
- **53–56.5:** cloned cotton-ball smoke.
- **56.5–59.5:** a game-camera top-down view, a perfect perspective ellipse for the ring, and a Gaussian engine glow.
- **59.9–61.0:** translucent circle dust, cone-tailed pebbles, and the robot sliding up rigidly.
- **61–64:** a radially stamped canopy ring.
- **64–67:** a rigid 3D model turning against a scrolling sky, with broccoli moss. It reads like a game cutscene.
- **67–72:** a vector ribbon trail and a lens star on the robot.
- **72–79.5:** cloned pole trunks, and an imprint made of flat stains.

Nothing in our film has AI art's melted detail. MK reads as far more AI-like, with crunchy filter textures and nonsense parts such as the pinwheel discs.

## 4. Scores

| | Ours v11 | MK | Why |
|---|---|---|---|
| Design | 6 | 5.5 | We have a readable face; MK has better overgrowth |
| Composition | 6.5 | 5.5 | We stage; MK centres everything and reuses its plates |
| Line | 5.5 | 5 | Both uniform; ours has more weight, MK's is sketchier |
| Colour | 6.5 | 6 | Our golden light is better but our backlit shots are muddy; MK is harmonious but washed out |
| Timing | 6 | 4 | Ours really acts; MK moves near-identical poses like a puppet |
| Effects | 5 | 5.5 | MK's two dust effects beat all of ours |
| Climax | 6 | 5.5 | Ours is more complete; MK has the strongest single frame |
| Backgrounds | 6.5 | 6 | Ours have real depth, but repeated trunks and stamped ivy |
| **Average** | **6.0** | **5.4** | |

## 5. The biggest single change, and the three weakest shots

**The single change:** make the robot drawn, not rendered. It carries more than 50 of the 79.5 seconds. In order:
1. Designed, facet-free shadow shapes for each key drawing.
2. Tapered, broken ink.
3. About 60 % less rivet and decal noise.
4. A shape wobble that changes with each drawing.
5. The resolve eye state.

This one change does more than anything else to remove the "cel-shaded game" read, which is what disqualifies us under the brief.

**Three weakest shots:**

1. **S14, 59.5–61.0 (launch).**
   - Open on the S12 crouch, held 6 frames, with the engines blasting the ground and dust building.
   - Then 2 smear frames.
   - Draw the impact frame from that crouch, with head and arms readable.
   - Then a stretched exit drawing held 2 frames.
   - Replace the bubbles with an opaque 2–3 tone dust wall rolling outward on 2s, and remove the cone tails.
   - Keep the robot in frame for about 12 frames riding the flame column, and cut after at most 6 empty frames.
2. **S13, 56.5–59.5 (ring of wind).**
   - Change the camera from straight down to a high 3/4, so the standing robot and the engine flare read.
   - Make the ring a thick, ground-hugging dust and air wall with a bright rim, expanding for the full 3 s.
   - Bend the trees behind it on drawn keys (push, then recoil), tear leaves off and shove the mist out.
   - Add a second, fainter ring at about 58.3 so the shot never goes static.
3. **S16B, 67.0–72.0 (trail).**
   - Repaint the sky as an amber-to-blue dawn with a bright sun and halo.
   - Rebuild the trail as a hot white-gold core line inside a billowing mist envelope, lit on the sun side and lilac on the shadow side.
   - Taper the trail toward the robot, and let the old end drift and break up.
   - End with the robot crossing the sun disc as a dark silhouette with a rim flare, in place of the lens star.

**Keep:**
- the S02 bird animation;
- the S03 beam composition;
- the S06 flock;
- the S07 two-stage eyes and blink;
- the S10 low-angle lift with sunbeams;
- the S12 crouch timing;
- the S16A diagonal energy;
- the S16B cloud sea.

*Working crops, frame strips and timing scripts: /tmp/claude-0/-home-user-blender-workspace/025617e1-c491-52ad-8f4f-905a73681e63/scratchpad/review_v11/ (scratch only).*
