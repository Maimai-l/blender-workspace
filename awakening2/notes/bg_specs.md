# Background specs — Phase 2 (per shot)

Every shot has a full-resolution layout in `board/layouts/layout_<shot>.png`: the robot's
silhouette at the start (grey) and end (red) of the shot, the horizon / eye level (blue line,
absent when it is off-frame), a perspective ground grid, and an arrow pointing toward the sun.
The storyboard rows are `board/board_<shot>.jpg`. Paint around the robot: the robot is
composited on top, so paint what is *behind* it, and put anything that must pass *in front*
of it (foreground trunks, ferns, hanging vines) on a separate near layer. Frame 1920×1040.
Keep the S01 world consistent: giant ancient broadleaf trunks (4–6 m thick, mossy, ivy), a
clearing where the robot kneels, mist on the floor, low warm sun from behind-right of the
robot (so most shots are backlit: warm rims and glowing mist, cool shadows).

| Shot | Size | What to paint | Layers |
|---|---|---|---|
| S02 | 1920×1040 | Seen from above the robot's left shoulder looking across it: the far forest interior in soft depth (trunks fading into glowing mist, light shafts), no ground plane visible near (the shoulder fills the bottom) | sky/mist, far, mid |
| S03 / S07 | 2100×1140 (slow push) | Looking up past the bowed face toward the canopy: dark mossy trunks converging upward, a bright gap of dawn sky upper-left, a strong warm sunbeam entering from upper-left (the "first ray"), floating motes. The face covers the right two thirds | sky, far, mid, beam (separate soft layer) |
| S04 | 1920×1040 | Behind the chest: deep forest interior at low height, ferns and the ground mist, cool and dark with warm glints (the chest fills most of the frame) | far, mid |
| S05 | 1920×1040 | Ground-level close-up: mossy forest floor, pebbles, dew drops on fern tips and clover, roots, a crack line in the soil near the robot's fingers (left-centre); background: blurred trunks and mist. Pebbles in their own layer so they can jump | far, mid, ground, pebbles (separate small sprites with alpha) |
| S06 | 1920×1040 | Looking up from the floor: the canopy edge of huge trees against a peach-gold dawn sky, branches silhouetted, leaves with warm rims — room in the sky for a flock to burst | sky, canopy |
| S08 | 1920×1040 | Wide front view of the clearing: two huge trunks framing left and right, forest beyond in mist layers, ferns and roots in front, the robot kneels centre (see layout); horizon at y≈757 | sky, far, mid, near, fg |
| S09 | 1920×1040 | Low camera near the ground from the robot's side: ferns and grass in the extreme foreground (bottom), trunks rising up the frame edges, canopy and a patch of sky at the top; horizon at y≈990 | sky, far, mid, fg |
| S10 | 1920×1040 + tilt (paint 1920×1600, the camera tilts up ~500 px) | Low-angle front: canopy high above with the gap of golden sky directly above the robot's head; sunbeams down through the gap | sky, canopy, beams |
| S12 | 1920×1040 | Behind the robot looking toward the sun: backlit forest interior, the sun glowing through the mist between trunks (bright), trunks as dark silhouettes with gold rims | sky/glow, far, mid, fg |
| S13 | 2200×1200 (shake room) | High angle down on the clearing: forest floor with ferns, roots, moss, fallen logs and stones, the tops of shrubs, the bases of the giant trunks (they lean out of frame toward the camera), the clearing's centre where the robot crouches (see layout). The wind ring will flatten ferns radially, so paint the ferns as their own layer | ground, ferns (separate), trunks |
| S17 | = S01 bottom frame | The same clearing as the end of S01 with the robot gone: a mound of moss and soil with the imprint of its knee and hand, scattered flowers, broken vines; sunbeams now strong through the gap | same layers as S01 |

S14 (launch) reuses S08's layers; S15 reuses S11's. S16 is done in Phase 1.

Priorities if time is short: S08, S03, S02, S12, S13, S09, S05, S17, S06, S10, S04.
