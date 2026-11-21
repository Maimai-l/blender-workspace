---
name: arknights-ui-flow
description: Turn a game UI task that MAA cannot do (Arknights on the PC's LDPlayer: Security Deployment sweeps, workshop crafting, switching a factory's product, shop purchases, claiming event rewards) into a guarded, repeatable flow by walking it once with the recorder. Use when the user asks to automate such a task, or a hosting job needs one.
---

# Arknights UI flows: record once, run guarded

MAA covers fights, base shifts, recruiting and the like. Anything else is a **flow**: a small Python file on top
of `arknights/tools/uiflow.py`, run on the PC with the agent-ocr venv. The engine supplies all the safety; a flow
only declares its screens, the only places it may tap, and its decisions. Reference flow:
`arknights/tools/tower_sweep.py` with its recording in `arknights/flows/tower/` (Security Deployment sweep, in the daily run since 2026-11-20).

## Rules that are not negotiable
- The user's words (2026-11-20): this must be extremely stable; never wake up to originium converted to orundum,
  a skin bought or a pull made. So:
  - never tap anything the engine refuses; never widen `NO_TAP` or remove `FORBIDDEN` words to make a flow pass;
  - a flow taps only OCR'd texts (or points derived from one) inside its `ALLOW` boxes;
  - every confirm button is guarded by reading what the dialog says (item, count, cost) and comparing it with the
    plan; any mismatch taps 取消;
  - leaving is the back key only (`go_home`), which on a dialog means cancel.
- Material-consuming actions (crafting, promotion, mastery, factory product changes) need an approved order in
  `arknights/goals.json` or the user's word; spending originium, orundum, green or yellow certificates, or pulling,
  is never automated (`ops/maa/README.md` section 6).
- Work on the PC only while no `run.ps1` is running (0:00 / 8:00 / 12:00 + ~20 min) and say so if the user might
  be on the phone; opening the game logs the phone out.

## Recording a new flow
1. Open the game without phone notifications: `D:\Projects\maa-cli\open_game.ps1` (source `ops/maa/open_game.ps1`;
   start it detached with Start-Process and wait for `state\open_game.done`), not `run.ps1`. Close the emulator
   with `ldconsole.exe quit --index 0` when done.
2. Explore with `arknights/tools/ui.py` (`shot`, `ocr`, `tap`, `back`), looking at screenshots. Never tap a confirm
   button while exploring unless the action is wanted anyway.
3. Walk the path again with the recorder, one call per screen:
   ```bash
   python3 -I arknights/tools/ui.py rec <flow> <screen> --tap-text <text>     # or --tap X Y <label>, --back, nothing
   ```
   Each call saves `arknights/flows/<flow>/NN_<screen>.json` (OCR items without the nickname, ID and 6+ digit
   numbers) and then acts. Name screens by what they are (`terminal`, `confirm`), reuse a name when a screen
   comes back. Record the cancel path, not the commit path, unless committing is wanted.
4. Draft the flow: `python3 -I arknights/tools/ui.py gen <flow>` prints SCREENS, ALLOW and a run() outline.
   Review it:
   - drop signature texts that change with time (event names, banners, dates, counts); keep 2-4 stable labels;
   - widen an ALLOW box only to the button's real extent; a point tap (`tap_point`) should be derived from a
     nearby text if the layout can shift (tower cards: "6/6" label + offset);
   - add the decision before any confirm (read the dialog; compare with the plan; else 取消), and a `--dry` path
     that cancels at the last dialog.
5. Check offline: `python3 -I arknights/tools/ui.py check <flow> <flow file>` must print `ok` for every
   recorded screen. Add pure-function tests for parsing (as `card_groups` / `decide` in tower_sweep).
6. On the PC: upload the flow and `uiflow.py` to `D:\Projects\maa-cli\`, run `--dry` (Start-Process, poll a
   done file; exec calls stop at ~90 s), then look at the screenshots in `state\uiflow\<flow>\`.
7. Icons and buttons without text (the ✓ of a dialog, a gear, an item icon): use MaaCore's own templates instead of
   guessing coordinates. `Flow.find_node(name)` / `tap_node(screen, name)` take a node of
   `D:\Projects\MAA\resource\tasks\tasks.json` and match its template inside its roi with its threshold, as
   `ops/maa/upstream/maa/protocol/task-schema.md` describes (Ccoeff = TM_CCOEFF_NORMED on the screenshot scaled to
   1280x720, default threshold 0.8, maskRange honoured). Look the node up in tasks.json first (never guess a node
   name); nodes that inherit (`baseTask`, implicit `X@Y`) and other algorithms are refused. Tested 2026-11-21:
   `OfflineConfirmImpl` 0.98 on the kicked-login popup and 0.25 elsewhere; `StartUp` 0.99 on the home screen.
   Item icons for depot / shop work are in `resource\template\items\<item id>.png` (497 of them).
8. Small digits (counts, levels) are often missed at full screen: read them with `Flow.read_region(box)`
   (enlarged crop), as tower_sweep does for the card counts.
9. Wire it in: call it from `ops/maa/run.ps1` at the right point (after `maa run daily`, before the emulator is
   closed), document it in `ops/maa/README.md` (path, guards, test result) and `arknights/GAME_NOTES.md` (what the
   screens look like), and add a line to the user's manual tab 游戏托管与小工具. Results land in `runs.log` as
   `[<flow>]` lines, which `notify.py` turns into the phone message.

## Engine facts (uiflow.py)
- 960x540 coordinates everywhere (device 1600x900, K = 5/3), the same as `ui.py ocr` prints.
- `Flow(name, SCREENS, ALLOW)`; `expect(screen)` checks ALL signature texts (3 looks), `FORBIDDEN` words
  outside home abort, `tap_text` / `tap_point` refuse taps outside ALLOW or inside NO_TAP, `go_home` uses the back
  key, `read_region` re-reads an area enlarged, `MAX_STEPS` 40 screens, a screenshot per step in
  `state\uiflow\<flow>\`; `uiflow.main(flow, run)` always ends on the home screen and stops the OCR server.
- OCR misses decorative Latin text and sometimes small digits; signatures should be Chinese labels.
