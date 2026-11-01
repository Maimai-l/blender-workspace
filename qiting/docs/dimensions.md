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
| Terraces | 3 tiers; radii 7.33 / 9.26 / 11.20 m; 0.68 m high each | Radii: DWG notched outlines, median 29.9 / 37.8 / 45.7 px. Heights: W02 base −4.6 m and stair foot −5.0 m, split into three; 419 shows three tiers | radii ±0.25 m, heights ±0.1 m |
| Terrace notches | 8, at the column azimuths, 0.60 × 0.85 m | DWG; 419 shows the breaks | ±0.2 m |
| Plaza level | −4.80 m | W02: terrace base −4.6 m; stair foot −5.0 m from the post tops. A flat compromise | ±0.2 m |
| **Balustrade on the podium** | | | |
| Post line radius | 4.72 m | W02, posts at 351–358 px; DWG circle 19.95 px | ±0.08 m |
| Posts | 24 (3 per column bay); 0.20 m square; 1.48 m tall | W02 post pitch about 90 px; post height from y 1388 against the floor at 1500 | ±0.05 m |
| Hand rail | 0.93 m | W02 y 1430 | ±0.05 m |
| **Stair (north)** | | | |
| Clear width | 2.40 m between the parapets; parapets 0.36 m | DWG 2.45 m between the stair lines; master plan 2.3 m | ±0.25 m |
| Flights | 3 flights of 10 / 11 / 12 risers (33 in all, riser 0.145 m); treads 0.272 / 0.355 / 0.390 m | W02 with the solved camera: landing posts at r 7.8 / 9.8 m and 13.8 / 14.9 m, foot post at 19.4 m; landing post tops 1.45 m and 3.15 m below the podium posts | riser count ±1 per flight |
| Landings | 2.20 m at −1.45 m; 1.30 m at −3.05 m | Same as the flights | ±0.2 m |
| Stair foot | r = 19.2 m | Same as the flights | ±0.3 m |
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
