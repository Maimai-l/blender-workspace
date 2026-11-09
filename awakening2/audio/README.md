# Awakening II: soundtrack (`audio/`)

This folder holds the complete soundtrack (score, sound effects and ambience) for the short, now 79.5 s with cue sheet version 2. Everything is synthesized in Python with numpy, scipy and numba: oscillators, filtered noise, modal resonators, stick-slip friction models, and convolution with synthetic impulse responses. It uses no samples, no recordings, no AI models and no speech.

Every time in the soundtrack is read from `cues.json`. To retime or restructure the film, edit that file and run the script again.

## Files

| file | what it is |
|---|---|
| `make_audio.py` | Entry point. It validates the cues, renders the music and the effects in two worker processes, then mixes, masters, checks and reports. |
| `aw2_core.py` | Shared core: cue loader and cue-derived helpers (the sky split, the spark, the vista, the launch held breath), seeded generators (one per named cue), envelopes, filters, the numba kernels (band-limited saw, time-varying state-variable filter, damped-mode bank, dynamic-spectrum additive oscillator), the stereo bus with reverb sends, and the synthetic reverbs. |
| `aw2_instruments.py` | The orchestra: flute, the five string sections (each with a synthetic body), pizzicato, horns, trombones, tuba, felt piano, music box, celesta, glockenspiel, harp, timpani (strokes and rolls), taiko, bass drum, cymbals (crash, swell, reverse) and tam-tam. |
| `aw2_score.py` | The theme and the score, composed against the cue sheet section by section. |
| `aw2_fx.py` | Sound effects (one handler per event name) and the ambience. |
| `aw2_analysis.py` | BS.1770 loudness (integrated, momentary and short-term), EBU loudness range, 4× true peak, per-second tables, onset and click scans, and the spectrogram PNG. |
| `mix.wav` | The result: 79.500 s, 48 kHz, 24-bit PCM stereo. |
| `music.wav`, `fx.wav`, `amb.wav` | Stems, after the same master gain curve as the mix, so music + fx + amb equals the mix before dither. |
| `spectrogram.png` | Mix and stems (log frequency), with the momentary loudness curve and every cue marked. |
| `cues.json` | The timing, owned by the picture. I added no fields. |

The first film's generator (`awakening/audio/make_audio.py`) was the starting point. Its filters, bus, impulse-response design, BS.1770 meter, compressor and limiter live on, extended, in these modules.

## Re-running

```
python3 make_audio.py               # about 55-70 s; writes the 4 WAVs and spectrogram.png, prints all checks, cross-checks with ffmpeg
python3 make_audio.py --no-ffmpeg   # skip the ffmpeg ebur128 cross-check
python3 make_audio.py --workers 1   # one process instead of two, same output bit for bit
python3 make_audio.py --cues other.json --out some/dir
```

- **Time.** The music renders in one process (about 31 s) and the effects and ambience in the other (about 13 s). Mastering, the checks and the PNG then take about 20 s. The 4-core sandbox is shared, so the wall time varies between about 55 and 70 s. The script uses at most 2 processes, each single-threaded.
- **First run.** The numba kernels compile once (a few seconds) and are cached in `__pycache__/`, which git ignores.
- **Safe to read during a render.** Output files are written atomically (a temp file, then a rename), so a reader never sees a half-written WAV.
- **Repeatable.** Runs are deterministic: `SEED` in `aw2_core.py`, plus `zlib.crc32` of each cue's name. Moving one event changes only that event's sounds.

## Everything is timed from `cues.json`

The script reads:

- `duration`: the output length, exact to the sample.
- `fps`: used for the frame column in the event report.
- `shots`: their cut times shape the vista and the two sky shots; each second's row in the report is labelled with its shot.
- `events`: every sound effect. The order in the file does not matter.
- `music.sections`: the score.

### Events

- **Name matching.** Each event goes to the handler registered under its base name, which is the name with any trailing `_<number>` removed. So `rise_groan_3`, `core_flicker_4`, a third `core_heartbeat` or an extra `bird_chirp` simply work.
- **Unknown names.** These are reported once and ignored. An event outside 0..duration, or an `end` that differs from `duration`, is also reported.
- **Sounds that last.** These run until the next relevant event after their own cue:

  | sound | starts at | runs until |
  |---|---|---|
  | core hum | `core_glow_steady` | `engine_ignite` |
  | tremor | `tremor_start` | `hand_presses_ground` |
  | soil pour | `hand_presses_ground` | `stands_full_thud` |
  | each rise groan | its `rise_groan` | the next groan or the stand |
  | head-lift creak | `head_lift_creak` | `eyes_resolve` |
  | engine spool and wind ring | their cues | the held breath |
  | the roars | `impact_frame` | `trail_fades` |
  | trail shimmer | (see below) | `trail_fades` |

- **`bird_crosses_far` comes in two kinds.** If a `bird_wings_flare` or `bird_touchdown` follows within 5 s, it is the little bird arriving. Otherwise it is a few birds crossing the vista (cues v2: 2.0 s).

### Derived moments (no event needed)

| moment | how it is found | cues v2 |
|---|---|---|
| **vista** | The first shot is seen from above the canopy, so the opening plays high open wind there and holds the forest floor back. The two crossfade over 2.5 s after the first cut. | 0–4.5 s |
| **sky split** | If a shot cut falls between `sky_reveal` and the end of the flight, the sky is two shots. The first is the camera flying with the robot: rushing wind, the engines close and steady (no Doppler), debris fluttering past. The second is the wide shot: the roar flies away from us (Doppler), the trail shimmers, and the spark. Without such a cut there is a single sky shot with the trail. | 64.0–67.0 and 67.0–72.0 |
| **spark** | The robot crossing the sun gets a bright E-major chime and is where the theme resolves. An explicit `sun_spark` event wins (add `{"t": 71.5, "name": "sun_spark"}` to move it); otherwise it falls 0.5 s before the flight section ends. | 71.5 s |
| **held breath before the launch** | It ends at `launch_smear` and lasts 15 % of the `wind_ring` → `launch_smear` build-up, clamped to 0.3–0.7 s. The music, spool and wind ring stop at its start; the master gates every stem to digital silence inside it, tails included. | 59.22–59.70 s (480 ms) |

The picture fades are applied in the master: `fade_in_start` (1.6 s cosine), and `fade_out_start` → `end`.

### Music anchors

| section | anchors |
|---|---|
| dawn (one song) | Phrase a starts 1 s after `fade_in_start`, on the music box (the flute takes over at bar 3). Phrase b follows with its peak (B5 over Gmaj7) on `sun_ray_reaches_face` and its resolution on the first `core_flicker`. Both phrases are fitted to about 80 BPM, followed by the near-silence before `tremor_start`. |
| tremor | The pulse starts at the heartbeat interval and accelerates to `eye_lids_open`. The stab lands on `birds_burst` and the shimmer on `eyes_ignite`. A dominant anacrusis leads into `hand_presses_ground`. |
| rise | The low theme runs from `hand_presses_ground` to `stands_full_thud`, in a broad 3/4 when two bars of 4 would be faster than about 72 BPM (65 BPM now). The climb follows `head_lift_creak`, and the major resolve lands on `eyes_resolve`. |
| ignition | A held harmonic to `engine_ignite`. Then a crescendo (C, then D) and a scale run to the held breath. |
| flight | Phrase b's opening fills `impact_frame` → `sky_reveal`. The full statement lands on `sky_reveal`: violins in octaves, flute and glockenspiel on the peak C#6, with two horns singing the theme's head under it. It carries broadly through both sky shots and resolves on the spark. The ostinato drives through the tracking shot and stops on the cut to the wide shot. |
| coda | The piano's open third arrives just after `bird_returns`, and the final chord before `fade_out_start`. |

**Retime tests.**
- Version-0-based test sheets: a uniform 8 % stretch with extra and unknown events, and a non-uniform edit. Every transient cue landed within one frame and the peak landed on `sky_reveal`; the silence (518 / 570 ms) and the rise tempo (58 / 63 BPM) adapted.
- The lead's v1 (rise) and v2 (vista and split sky) restructures ran with no timing code changes. The derived moments above were added to serve the new shots.

## The score

**Key plan.**

| part | key |
|---|---|
| dawn and tremor | D major |
| rise | D minor, turning to D major on the resolve |
| canopy gap | a D Lydian glow (E over D) |
| flight and coda | E major, a whole tone up |

The core hum is A, the dominant.

**The theme** ("the old dream") is original: a 9-bar sentence in 4/4, written here in D. The rhythm per bar is: q q q. e | h q. e | h q q | w ‖ q q q. e | h q. e | h. e e | h. e e | w.

```
a  | F#4  A4  D5.  E5 | F#5 --  E5.  D5 | D5 --  C#5  B4 | A4 -- -- -- |
     D(add9)            Bm7               Gmaj7             Asus4 -> A
b  | G4  B4  E5.  F#5 | G5 --  F#5.  E5 | B5 -- --  A5 F#5 | E5 -- -- F#5 E5 | D5 |
     Em7                A7sus4             Gmaj7  (peak)       Asus4 -> A         D
```

Phrase b repeats phrase a's opening a step higher, then leaps a fifth to its peak.

**How the theme appears (cues v2):**

| time | instrument | material |
|---|---|---|
| 1.0 s | music box | Phrase a, bars 1–2, with soft dyads, as the vista fades in. |
| 7.1 s | flute | Bars 3–4, then phrase b (from 13.5 s): the peak B5 on the sun ray (19.5, with a harp unfolding Gmaj9), the resolution on D as the core flickers (25.5). Felt piano and string pad support it. |
| 40.1 s | horns and cellos | Phrase a in D minor, low, in a broad 3/4, over low brass and timpani: Dm(add9) → Bbmaj7(#11) → Gm7 (the stand) → Asus4 → A7. |
| 49.7 s | horns | The head motif in major on the resolve. |
| 59.9 s | violins (octaves) and horns | Phrase b's opening in E (A4 C#5 F#5. G#5 \| A5 G#5. F#5) over a driving ostinato. |
| 64.0 s (sky_reveal) | full orchestra | The peak, C#6 over Amaj7, carried at about 64 BPM through G#m7 → B7sus4 to E at the spark (71.5). Horns sing G#3 B3 E4. F#4 \| G#4 under it. |
| 72.35 s | piano alone | The head motif in E, ending on the open third over IV → I. One music-box echo at the end. |

## Instruments (all synthesized)

- **Flute.** A legato line with a dynamic spectrum, delayed vibrato, pitched breath noise and a tongued "chiff".
- **Strings.** Detuned PolyBLEP saw players, each with its own vibrato, timing and glide. A low-pass that follows the dynamics, body resonances plus a synthetic per-section body impulse response (about 90 damped modes, a jagged wood-like response), and bow noise. Articulations: sustained, tremolo, harmonics, spiccato; pizzicato is modal.
- **Brass.** Additive tone whose spectrum opens with loudness, with a lip scoop and breath blat.
- **Felt piano.** Inharmonic partials, unison-string beating, double decay, felt thump.
- **Music box, celesta, glockenspiel and harp.** Modal partials.
- **Percussion.** Timpani (gliding membrane modes, rolls), taiko, bass drum, cymbals (modal), and a tam-tam with bloom.
- **No truncation clicks.** Every modal note fades over the last part of its buffer, and plucked or struck onsets get a ramp of under 1 ms.

## Sound effects (cue sheet, cues v2)

| cue | time | what is placed |
|---|---|---|
| (vista) | 0–4.5 | high open wind over the canopy, distant birdsong |
| bird_crosses_far | 2.0 | three birds crossing the vista far away, a far call |
| bird_crosses_far | 11.3 | the little bird approaching (bounding wingbeats, a tsip) |
| bird_wings_flare / touchdown / hop / chirp | 14.1 / 14.6 / 15.4 / 16.7 | braking flaps; claw ticks, moss scuffle, wing fold; a hop; a close tsip call |
| sun_ray_reaches_face | 19.5 | old metal warming: thermal "tinks" |
| core_flicker | 25.5, 26.0 | gated buzz with an arcing edge, crackle, relay |
| core_glow_steady | 26.9 | the core hum (A1), shaped by the heartbeats, eyes, stand and resolve |
| core_heartbeat | 27.9, 28.9 | lub-dub with a muffled body and a metal ring |
| tremor_start | 29.5 | first jolt and pebbles jumping; rumble shaped by the burst and the eyes; crackle; pebble rattle; a far tree creak |
| birds_burst | 32.0 | 36 birds (wing claps, flutter, flying off), canopy rustle, alarm calls |
| eye_lids_open / eyes_ignite | 35.7 / 36.3 | lid servo, scrape, stop; electric zap, in-key glide, lens ping |
| small_bird_flees | 37.1 | alarm calls and a fast take-off |
| rise_groan | 39.4, 43.5 | load tick; long deep stick-slip metal groan (3–4.8 s, structural low mode, big space); two long creaks; overtone groan; servo; hydraulic hiss; clunks |
| hand_presses_ground | 40.1 | heavy sub thud (72→31 Hz), soil crunch, roots strain, servo; the soil pour until standing |
| roots_tear / soil_curtain | 41.0 / 44.5 | ripping, snaps, creak, vine whips; a 3.2 s soil cascade |
| stands_full_thud | 45.6 | heavy sub thud (84→30 Hz), frame and settle clanks, settle groan, debris |
| head_lift_creak / eyes_resolve | 48.0 / 49.7 | neck unlocks, long deep creak, squeal, servo, stop, dust; focusing tone, lens ping |
| back_plates_open / crouch / sputter | 53.7 / 54.9 / 55.4 | latches, sliding plates, vent hiss, moss tearing; joints compress; coughs, failing spool, sparks |
| engine_ignite / wind_ring | 56.0 / 56.5 | WHOOMPH, flame bloom, spool-up to the held breath; pressure wave and the ring whoosh (centre → wide), debris, trees bending |
| launch_smear / impact_frame | 59.7 / 59.9 | out of 480 ms of silence a suck into the LAUNCH: thump, blast, debris; the roar climbs away (Doppler from the ground) until the sky cut |
| canopy_burst | 61.4 | branch snaps, leaves exploding, the pass-through |
| sky_reveal (tracking) | 64.0–67.0 | rushing wind (deep roar, buffeting, armour whistles, mids kept light for the orchestra), engines close and steady (no Doppler), debris fluttering past |
| (wide) | 67.0–72.0 | the roar flies away from us (Doppler: 90 m → about 1.2 km), the trail shimmer, a **spark chime at 71.5** (bright E-major bell partials and glitter) |
| trail_fades | 70.5 | the trail dissolves |
| bird_returns | 75.0 | flutter in, lands on the cue, moss scuffle, a happy twitter |

**Ambience:**

- the vista's high wind;
- the forest floor: gusty wind in leaves, a leaf-crinkle texture, crickets fading at sunrise, a distant stream;
- a sparse dawn chorus of six synthetic species, stopped by the burst and returning in the coda;
- sky wind;
- leaves tumbling in the coda.

## Mix and master

1. **Stem preparation.** Each stem gets a 28 Hz high-pass and mono bass below 120 Hz. The effects stem also gets a −4 dB shelf under 50 Hz.
2. **Stem gains.** Music 0, effects +8, ambience +9 dB. Per-section music trims are in `SECTION_TRIM`, and each effect's gain is the `g=` of its `ctx.add` call.
3. **Rides from the cues.** The music dips 3.5 dB under the launch blast, the ambience ducks under the launch, and the held-breath gate silences everything.
4. **Master.**
   - Cue fades.
   - Normalization to −20 LUFS.
   - A gentle stereo-linked RMS compressor (−20 dBFS, 1.7:1).
   - Calibration to −17 LUFS through a true-peak limiter (4× oversampled, ceiling −1.35 dBTP, 3 ms look-ahead).
   - 24-bit TPDF dither.

   The master is one gain curve, applied to the mix and to each stem.

## Measurements (this render, cues v2)

**Overall:**

| measure | value |
|---|---|
| integrated loudness | **−17.0 LUFS** (own meter and ffmpeg agree) |
| true peak | **−1.35 dBTP** (ffmpeg −1.3); sample peak −1.36 dBFS; no samples at full scale |
| loudness range | 15.0 LU (−27.2 .. −12.2) |
| stems (integrated) | music −19.1, effects −18.9, ambience −34.7 LUFS |
| master | compressor at most 3.8 dB; limiter at most 3.9 dB, only on the launch transient (59.93 s) |
| sub-bass (below 60 Hz) | −8.0 dB of the energy over the film; −2.3 dB in the requested thud seconds |
| stereo | correlation 0.63 overall (per second: minimum 0.21, median 0.71); a mono fold-down changes loudness by −1.2 dB |
| integrity | 3,816,000 samples (79.500 s); DC about 2e-6; last sample 0 |
| click scan | music 0, ambience 0. Effects: 1 marginal flag (z 13 against a threshold of 12, −32 dBFS, 25.575 s) where the designed core crackle meets the buzz. Each sound scanned alone is clean. |
| events | 26 / 26 transient cues start within one frame |
| sync | Theme peaks on `sky_reveal` (+0 ms) and the dawn peak on the sun ray. The dawn resolves on the flicker and the flight on the spark. |
| silences | The near-silence before the tremor is −44 dBFS music (dawn average −28). The held breath is digital silence. |

**Mean momentary loudness by section** (LUFS):

| dawn | tremor | rise | ignition | flight | coda |
|---|---|---|---|---|---|
| −24.9 | −20.4 | −16.5 | −16.4 | −12.7 | −22.3 |

**Momentary loudness per second** (mix, LUFS):

```
 0- 9   -38  -27  -26  -27  -27  -27  -28  -26  -27  -27     vista: high wind, birds, music box; tilt down, flute
10-19   -26  -27  -29  -29  -27  -26  -22  -24  -25  -23     the little bird arrives and sings; phrase b
20-29   -20  -20  -22  -23  -25  -25  -26  -27  -27  -27     the sun-ray peak; core flicker, hum, heartbeats, near-silence
30-39   -23  -19  -16  -18  -23  -23  -23  -22  -24  -19     tremor, the flock (32); eyes; the sink groan (39.4)
40-49   -14  -16  -16  -15  -14  -13  -16  -20  -18  -17     hand plant (40.1), roots, groans, curtain, the stand (45.6); head lift
50-59   -18  -19  -24  -24  -22  -22  -16  -16  -12  -14     canopy gap; held breath; plates, sputter, ignition, wind ring; silence
60-69   -11  -12  -14  -14  -11  -12  -12  -14  -14  -14     LAUNCH (59.9); canopy; flying with it (64-67); the wide sky
70-79   -14  -13  -16  -21  -28  -27  -30  -32  -40  -63     the spark (71.5); coda: piano, the bird returns, fade
```

## Self-checks printed on every run

- **Cue validation.**
- **Loudness summary, per-second table and section summary.**
- **Sub-bass, stereo, clipping and DC.**
- **Click scan.**
- **Event check.** For every cue: what was placed, where its main sound starts in ms and frames, and the onset heard in the effects stem.
- **Music sync.** The theme peak against `sky_reveal`; the dawn peak and resolution; the sky split and the spark; the rise tempo; the near-silence, the held breath and the launch silence.
- **`spectrogram.png`** and the ffmpeg cross-check.

## Honest weaknesses

No one has listened to this render; it was judged by analysis (spectra, levels, onsets, a dump of every note). The likely weak spots:

- **Instruments.** The strings and brass are good synth instruments, not a recorded orchestra. The flute and piano lack a player's micro-variation.
- **Birds.** The close little bird may still read as synthetic, and the flock is a texture.
- **Metal and engines.** The groans may suggest a ship or a door more than a 13 m machine. The engine and roar sources are generic, though their perspective (Doppler, distance) is physical.
- **The tracking shot.** The rushing wind sits about 4 LU under the theme so the melody carries. If the picture wants the wind to dominate, raise `g=` of "rushing wind" in `h_sky`.
- **The launch.** It is dense rather than cracking: up to 4 dB of limiting on the blast, which comes straight out of silence.
- **Quiet passages.** The LRA of 15 LU is cinematic; the vista and the coda are quiet on small speakers.
- **Extreme retimes.** For very large changes the score clamps the tempo and warns, and its anchored downbeats can then drift.
- **Originality.** The theme was compared by ear-memory with well-known Hisaishi themes; no automated check exists.
