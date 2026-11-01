# References

## The full set

The full set is on the Blender PC under `C:\Users\blender\Documents\qiting\refs\`:

- `旗亭\`: the contents of `D:\Downloads\旗亭.rar`:
  - 19 photos;
  - the video `4d22005f….mp4` (36 s, 1280×720);
  - `总平.pdf`, the 芙蓉园 master plan, 9 A4 pages;
  - `芙蓉园规划地形图0917-1.dwg`;
  - the DWG screenshot `2390cc8d….jpg`.
- `web\大唐芙蓉园_旗亭_建模参考\`: the 8 web photos from `D:\Downloads\旗亭_建模参考图.zip`, extracted there in this round.
- `_pdf\`: the PDF pages rendered as images.

`tools/pcx.py fetch` copies any of them into the session. In this round they were kept in `~/.cache/qiting/ref/`.

## Copies in this folder

Downscaled to 1600 px, except the plans.

| File | Original | Used for |
| --- | --- | --- |
| `photos/W02.jpg` | web `02_白天高处俯瞰_高台与侧梯.jpg`, Canon SX610 at 19.3 mm, 5184×3456 | Main elevation: heights, radii, roof profiles, stair landings. Calibrated camera `W02` |
| `photos/W01.jpg` | web `01_白天正面全貌.jpg`, SX610 at 13.2 mm | Relief layout (gate building, medallion, cartouche), finial, window. Camera `W01` |
| `photos/W03.jpg` | web `03_夜景侧面全貌_长坡梯.jpg`, EOS 50D, night | Soffit rafters, the long stair beyond the plaza (not modelled) |
| `photos/W04.jpg` | web `04_夜景中轴正面_台阶与台基.jpg`, night, south axis | South panel, flanking figures, cartouche and medallion |
| `photos/W07.jpg` | web `07_白天近景_画壁浮雕细节.jpg` | Relief depth, coping, balustrade fret |
| `photos/W08.jpg` | web `08_亭内藻井彩画.jpg` | Interior caisson painting |
| `photos/340d.jpg` | `340d186f….jpg`, 5712×4284 | West side in sun. Camera `P340d` |
| `photos/af3b.jpg` | `af3b264c….jpg`, phone, 4096×1848 | Plaque 旗亭, couplets, eaves, brackets, stair top. Camera `Paf3b` (weak fit) |
| `photos/419.jpg` | `微信图片_20260819201153_419_174.jpg`, dusk | Terraces, plaza setts and pale band, people for scale. Camera `P419` |
| `plans/dwg_screenshot.jpg` | `2390cc8d….jpg` | Plan: rings, terraces, stair, plaza outline. 0.245 m/px |
| `plans/masterplan_p1_1200dpi_crop.png` | `总平.pdf` page 1 at 1200 dpi, cropped round the hill | Scale bar 4.34 px/m. Registration of the DWG |

## Not used, or used only to check

- **Distant lawn photos** (`0fe4…`, `1b06…`, `2d9a…`, `e197…`, `f030…`, `f45a…`, `5c54…`, `94b7…`, `9cf0…`, `cb1e…`, and the WeChat photos `415`, `416`, `420` and `421`): checked for silhouette and colour.
- **`4f82…`:** the south garden stair leading up to the plaza; round 2.
- **The video:** a pan across the lawn. The pavilion is small in it; frames 21–30 show a person on the stairs.
- **PDF pages 2–9:** enlargements of other parts of the park.

The text, labels, dimension lines, legends and grids on the PDF and the DWG were not modelled.
