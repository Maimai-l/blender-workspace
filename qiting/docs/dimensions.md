# Qiting (旗亭): main dimensions and where they come from

All values are in `scripts/lib/qt_dims.py`, which the build scripts read.

Frame used throughout:

- origin on the pavilion axis, at the floor on top of the podium (Z = 0);
- +Y is north, the direction of the podium stair and the pavilion entrance (as in the DWG screenshot); +X is east;
- azimuths are counter-clockwise from east: north 90°, west 180°, south 270°.

## How the numbers were obtained

**Plan scale.** The DWG screenshot (`2390cc8d….jpg`) has no scale bar. It was scaled by registering it to the 1:1500 master plan (`总平.pdf`, page 1, rendered at 1200 dpi):

- The master plan's scale bar (0–10–60–100 m) gives 4.34 px/m at 1200 dpi.
- Both drawings show 旗亭 and the octagonal 赏雪亭. Matching the two pavilions gives 0.243 m per DWG pixel.
- A chamfer fit of the shared road, stream and lake lines gives 0.248 m per DWG pixel.
- The value used is **0.245 m/px (±2 %)**.

**Heights and elevations.** These come from photo W02 (web photo 02, Canon PowerShot SX610 HS at 19.3 mm). It looks at the pavilion from 214 m away, so it is almost an elevation.

- The camera was solved from 14 points: eave, drum and coping silhouettes, the finial top, the podium posts and four columns. Residual: 4.8 px rms on a 5184 px image.
- The solved focal length is 16,046 px. The EXIF focal length gives 16,216 px (19.3 mm on the 6.17 mm sensor). The 1 % agreement is an independent check of the plan scale.
- At the pavilion the image scale is 75.2 px/m.

**Cross-checks.** Four more photos were calibrated against the finished dimensions and rendered from the solved cameras:

- 340d: 5.7 px rms;
- W01: 16 px rms;
- the dusk photo 419: 10.9 px rms;
- af3b: 18 px rms, weak; see `../README.md`.

## Table

| Part | Value | Source and method | Est. error |
| --- | --- | --- | --- |
| **Podium (台基)** | | | |
| Coping edge radius | 5.42 m | DWG inner circle, 22.1 px | ±0.12 m |
| Relief drum radius | 5.32 m at its raised border; carved ground 5.27 m | W02, 402 px, edge of the drum below the coping | ±0.05 m |
| Coping slab | 0.26 m thick | W02 y 1500–1520 | ±0.03 m |
| Carved band height | 2.25 m (plain borders 0.14 m top and bottom) | W03 drum with plinth 2.52 m; 340d about 2.1 m; W07, against the air-conditioner unit, 2.0–2.2 m | ±0.15 m |
| Moulded plinth | 0.24 m | 340d, 419 | ±0.05 m |
| Terraces | 3 tiers; median radii 7.33 / 9.26 / 11.20 m; 0.68 m high each | Radii: DWG outlines, median 29.9 / 37.8 / 45.7 px. Heights: W02 base −4.6 m and stair foot −5.0 m, split into three; 419 shows three tiers | radii ±0.25 m, heights ±0.1 m |
| Terrace outline (round 2) | 8 rounded lobes between cusps at the column azimuths: cusp R − 0.67 m, crest R + 0.33 m (profile exponent 1.6); a 0.30 × 0.25 m notch at each cusp; a 0.30 × 0.05 m rim | Lobes: A1/A2. Radius spread: DWG. Round 1 had circles with notches | ±0.2 m |
| Plaza level | −4.80 m round the terraces, falling 0.20 m to −5.00 m at the stair foot (north lobe only) | W02: terrace base −4.6 m, stair foot −5.0 m. Round 1 kept it flat | ±0.15 m |
| **Balustrade on the podium** | | | |
| Post line radius | 4.72 m | W02, posts at 351–358 px; DWG circle 19.95 px | ±0.08 m |
| Posts | 24 (3 per column bay); 0.20 m square; 1.48 m tall | W02 post pitch about 90 px; post height from y 1388 against the floor at 1500 | ±0.05 m |
| Hand rail | 0.93 m | W02 y 1430 | ±0.05 m |
| **Stair (north)** | | | |
| Clear width (round 2) | 1.60 m between the parapets; parapets 0.30 m (2.20 m outside) | The DWG (2.45 m) and master-plan (2.3 m) lines are the outer faces: A1/A2 show the stair about 0.6× as wide as round 1 had it, and af3b fits 1.6 m best. Round 1: 2.40 m clear | ±0.15 m |
| Flights (round 2) | 34 equal risers of 0.147 m in flights of 10 / 11 / 13; treads 0.337 / 0.395 / 0.443 m | Re-measured on W02 with the corrected camera (azimuth 14.8°): east parapet posts at r 8.47 / 10.50 m and 14.47 / 15.58 m, tops 1.45 and 3.10 m below the podium posts. Round 1 had used the first, unrotated W02 solution (10 / 11 / 12) | riser count ±1 per flight |
| Landings (round 2) | 2.05 m and 1.13 m | Same as the flights | ±0.2 m |
| Stair foot (round 2) | parapet ends at r 20.9 m, 5.0 m below the podium floor; 3 more steps (0.36 × 0.15 m) beyond them down to the north path | W02; the extra steps from A1/A2 | ±0.3 m |
| Doors in the stair walls | 0.50 × 0.70 m, next to the drum, one on each side | W02 (east side), 340d (west side) | ±0.1 m |
| **Lower storey** | | | |
| Outer columns | 8, at radius 4.37 m; Ø 0.37 m tapering to 0.33 m; entrance bay centred on the stair | W02 column positions (±0.924R and ±0.383R, azimuths offset 22.5° from the stair axis, confirmed by the solved azimuths of W02 and 340d); couplet columns in af3b | ±0.07 m |
| Inner columns | 8, at radius 2.83 m; rise into the upper drum | W02, 214 px; 340d | ±0.07 m |
| Lattice frieze | 2.91–3.17 m, 3 openings per bay; lower beam 2.78–2.91 m | W02, 340d | ±0.05 m |
| Architrave | 3.17–3.44 m | W02 y 1240–1260 | ±0.04 m |
| Plaster bracket band | 3.44 m up to the rafters (about 4.1 m) | W01, af3b | ±0.1 m |
| Lower eave | tile edge r 6.37 m at z 4.48 m; fascia r 6.24 m, z 3.94–4.23 m | W02, 481 px and 471.7 px | ±0.05 m |
| Lower roof | tile-top profile traced from r 6.38 m (z 4.48 m) to r 2.98 m (z 5.64 m); meets the upper drum under a tiled collar at 5.80 m | W02 | ±0.06 m |
| **Upper storey** | | | |
| Drum radius | 2.83 m | W02 | ±0.05 m |
| Sill | 5.80–5.95 m | W02, W01 | ±0.04 m |
| Window band | 5.95–6.48 m, 3 white panels per bay | W02, W01 | ±0.04 m |
| Beam | 6.48–6.62 m | W02, W01 | ±0.04 m |
| Plaster bracket band | 6.62–7.44 m | W02, W01 | ±0.04 m |
| Upper eave | tile edge r 5.03 m at z 7.71 m; fascia r 4.82 m, z 7.25–7.47 m | W02, 380 px and 364.5 px | ±0.05 m |
| Upper roof | tile-top profile traced from r 5.00 m (z 7.71 m) to r 0.84 m (z 9.52 m) | W02 | ±0.06 m |
| **Finial (宝顶)** | | | |
| Base | 9.48 m | W02 | ±0.06 m |
| Rings | 6 stacked rings, Ø 1.56 m at the base and 0.80 m at the top, up to 11.24 m | W02, W01 | ±0.06 m |
| Neck | 11.38 m | W02 | ±0.06 m |
| Bulb | top 12.20 m, radius 0.37 m | W02 (fit residual 4 px); 340d (2 px) | ±0.06 m |
| Rod | to 13.30 m | W01, af3b; the rod is thin, so its length is estimated | ±0.3 m |
| **Boards** | | | |
| Plaque | 1.15 × 0.66 m, on the lower bracket band above the entrance | af3b, scaled by the column diameter | ±0.1 m |
| Couplets | 0.30 × 1.95 m, on the two entrance columns | af3b | ±0.1 m |
| **Openings and relief** | | | |
| Drum windows | 2, each 0.52 × 0.58 m, at azimuths 225° and 315° (either side of the south panel) | 340d and W01 (225°); W02 (315°); 419 | ±3° |
| South panel | 1.60 × 0.95 m, dark | W04 | ±0.1 m |
| Carved gate building | Centred at 161°, 1.55 m wide | W01, with the solved camera | ±3° |
| Round medallions | At 174° (W01) and 293° (W04) | W01, W04 | ±5° |
| Lettered cartouches | At 199° (W01) and 246° (W04) | W01, W04 | ±5° |
| Figure carving (round 2) | Softened at the user's request: the figure field is blurred (Gaussian, 6 cm) and capped at 4.5 cm relief, with a fine fold texture on top; the frames, gate building, medallions and cartouches stay crisp | Round 1 modelled robed figures that read as comical | — |
| **Plaza (地面)** | | | |
| Outer edge | 29.5 m | Outer, nearly circular line of the DWG plaza (广场), 29–31 m. The 419 camera, 27 m west of the axis, stands on the paving | ±1 m |
| Pale band | Along the lobed DWG line: about 24.5 m to the north, 15–18 m to the south | DWG; the pale arcs across the paving in 419 | ±0.5 m |
| Setts | 0.20 × 0.10 m, running bond in courses round the podium | 419 | Sett size estimated from 419 |

## Counts

| Item | Count | Source |
| --- | --- | --- |
| Outer columns | 8 | W02, 340d, af3b |
| Inner columns | 8 | W02, 340d, W08 |
| Bracket sets per storey | 8 | W01, af3b |
| Terraces | 3 | 419, 340d |
| Stair flights | 3 (landings 2) | W02 |
| Podium posts | 24, plus the 2 stair-edge posts | W02 |
| Tile rows | Lower roof 120 → 60 near the top; upper roof 96 → 48 → 24 | Chosen to match the tile pitch in W02 and W01, about 0.30 m at the eave |
| Rafters | Lower eave 240 per layer; upper eave 176 per layer | W01, af3b: two rows of square ends |

## Round 2: the site and the far scene

**Aerial cameras.** The two drone aerials A1 and A2 were solved like the photos. The near field (eave tips, finial, stair axis) fixes each camera well, but not its focal length: a longer lens farther back fits the pavilion almost as well. That ambiguity moves everything far away. So each solve also uses far points from the master plan, and the result was checked against the skyline:

| | A1 | A2 |
| --- | --- | --- |
| Camera (x, y, z), m | (2.1, 70.7, 29.1) | (−0.3, 71.1, 40.1) |
| Focal length | 1,263 px | 1,161 px (fixed) |
| Vertical stretch `ky` | 1.046 | 1.040 |
| Roll | 0.67° | 1.50° |
| Near-field fit | 1.9 px rms | edge fit 2.2 px |
| Far constraints | 紫云楼's terrace edge on the axis and the island's east tip (rows only); 78 skyline verticals | 紫云楼's terrace front, the island's east tip, the lakeside walk |

- **Check on the focal length:** at 1,250 px and longer for A2 (1,350 px for A1) the true horizon would sit above the tops of the city's towers, which cannot be. The plan-constrained solutions put it just below them.
- **The leans of the skyline towers** set A1's roll. They suggest about 0.4° less roll for A2 as well. Forcing that worsened A2's other residuals, so A2 was kept.

**The site** (`env/make_env.py`, 0.5 m grid over x −130…130 m, y −120…85 m):

| Item | Value | Source | Est. error |
| --- | --- | --- | --- |
| Terrain | 54 DWG spot heights, thin-plate fit, then relaxed with the paved areas held; Z −17.9 to −4.8 m (423.5–436.6 m above sea level) | DWG | ±0.5 m away from the spot heights |
| Lake level | 426.50 m (Z −14.90 m); the viewing platform at the axis 427.30 m | Master plan label 428.60 (426.50); DWG | ±0.1 m |
| Paths | promenade (pink) 5.2 m; lakeside walk 6.0 m; north road 6.0 m; park paths 2.4–2.8 m; garden stairs 2.6–3.0 m | DWG lines, checked on the rectified aerials | ±0.3 m |
| Plaza outline | DWG outer line; the DWG's planting pockets are paved, as in A1/A2 | DWG, A1/A2 | ±0.5 m |
| Lamps | 82 in four kinds (park, lantern, walk, mast), every 15–24 m along the paths | Kinds from A1/A2 and the photos; positions spaced, not surveyed | — |
| Sculptures (丽人行) | 8 white figure groups on plinths between the promenade and the walk | DWG symbols, A1/A2 | ±2 m |
| Plaza furniture | 6 stone tables with stools, 3 egg stones, 3 small bronzes, a sign | A1/A2, 419 | ±1 m |
| Golden gate | at (−45.0, −41.8): posts 6.3 m apart, 7.4 m tall; beams at 4.7 and 6.6 m; slats down to 2.8 m; red lanterns | A2, by casting rays onto the terrain | ±1 m |
| Sightseeing cart | at (−35.9, −37.0), 5.0 × 1.6 m | A2 | ±1 m |
| Trees | 289: deodar 68, broadleaf 161, columnar 11, small 17, willow 32 | Species mix and spacing per area read off A1/A2 (dense deodar wood north of the plaza, a grove east of it, lawns with groups east and west, willows along the walk) | positions not surveyed |
| Shrubs, hedges, lawn | 160 shrubs on the bank band; 5 clipped hedge segments outside the plaza edge; about 222,000 grass clumps within 70 m | A1/A2 | — |

**The far scene** (`scripts/lib/qt_far.py`):

| Item | Value | Source |
| --- | --- | --- |
| Lake and island | Outline and island from the master plan; the near shore is the DWG lakeside walk | Master plan, A2 |
| 紫云楼: position | Axis at x −3.5 m (plan −7, A1 −8, A2 0); terrace front at y −270 m (plan −268) | Master plan, A1/A2 rays |
| 紫云楼: terrace | 145 m wide, 30 m deep, 1.2 m above the water; a rimmed pool 110 × 34 m in front; broad steps up 1.5 m to the forecourt; 8 lamps 5.6 m tall at ±13.5 / 23 / 32.5 / 42 m | A2 rays |
| 紫云楼: que towers | Bastions at ±35 m from the axis, 11 × 14 m, 7.7 m high, battered; two-tier pavilions, finials 19.4 m above the terrace; arched flying galleries to the podium | A2 rays |
| 紫云楼: main tower | Podium 9.4 m high with a central stair 19 m wide up to a landing at 6.8 m and three doors; lower storey with balcony, pent roof (eave 15.8 m, 42 m wide), upper storey with balcony, double-eaved hip-gable roof (eaves 24.6 and 28.9 m, top roof 34 m wide, ridge 14 m long), ridge 35 m above the terrace | A2 rays; ridge length and widths from the eave ends |
| Hall groups | 8 groups, 32 Tang-style halls on the far shores | A1/A2 |
| Housing | 2,866 two- and three-storey houses with hipped roofs, x −110…−1,150 m, y −345…−1,500 m | A2 rays onto the ground |
| City | Mid-rise blocks 15–30 m at 1.0–1.5 km; high-rise compounds 40–75 m (a few to about 100 m) at 1.25–3.9 km; the ground rises 0.8 % south of y −700 m | A2 rays and the horizon check above |
| Far planting | About 28,800 trees: shore belts, dense park woodland thinning with distance, the wood round 紫云楼, street trees in the housing | A1/A2 |
| Haze | Compositor mist: colour (0.52, 0.60, 0.70), from 200 m, full at 3.8 km, strength 0.72; the sky gets 0.25 | Matched to A2 |
