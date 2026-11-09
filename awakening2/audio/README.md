# Awakening II: soundtrack (`audio/`)

This folder holds the complete soundtrack (score, sound effects and ambience) for the 75-second short. Everything is synthesized in Python with numpy, scipy and numba: oscillators, filtered noise, modal resonators, stick-slip friction models, and convolution with synthetic impulse responses. It uses no samples, no recordings, no AI models and no speech.

Every time in the soundtrack is read from `cues.json` (currently version 1, with the retimed rise). To retime the film, edit that file and run the script again.

## Files

| file | what it is |
|---|---|
| `make_audio.py` | Entry point. It validates the cues, renders the music and the effects in two worker processes, then mixes, masters, checks and reports. |
| `aw2_core.py` | Shared core: cue loader, seeded generators (one per named cue), envelopes, filters, the numba kernels (band-limited saw, time-varying state-variable filter, damped-mode bank, dynamic-spectrum additive oscillator), the stereo bus with reverb sends, the synthetic reverbs, and the launch held-breath window. |
| `aw2_instruments.py` | The orchestra: flute, the five string sections, pizzicato, horns, trombones, tuba, felt piano, music box, celesta, glockenspiel, harp, timpani (strokes and rolls), taiko, bass drum, cymbals (crash, swell, reverse) and tam-tam. |
| `aw2_score.py` | The theme and the score, composed against the cue sheet section by section. |
| `aw2_fx.py` | Sound effects (one handler per event name) and the ambience. |
| `aw2_analysis.py` | BS.1770 loudness (integrated, momentary and short-term), EBU loudness range, 4× true peak, per-second tables, onset and click scans, and the spectrogram PNG. |
| `mix.wav` | The result: 75.000 s, 48 kHz, 24-bit PCM stereo. |
| `music.wav`, `fx.wav`, `amb.wav` | Stems, after the same master gain curve as the mix, so music + fx + amb equals the mix before dither. |
| `spectrogram.png` | Mix and stems (log frequency), with the momentary loudness curve and every cue marked. |
| `cues.json` | The timing, owned by the picture. I added no fields: every default is derived from the events. |

The first film's generator (`awakening/audio/make_audio.py`) was the starting point. Its filters, bus, impulse-response design, BS.1770 meter, compressor and limiter live on, extended, in these modules.

## Re-running

```
python3 make_audio.py               # about 55 s; writes the 4 WAVs and spectrogram.png, prints all checks, cross-checks with ffmpeg
python3 make_audio.py --no-ffmpeg   # skip the ffmpeg ebur128 cross-check
python3 make_audio.py --workers 1   # one process instead of two (about 65 s), same output bit for bit
python3 make_audio.py --cues other.json --out some/dir
```

- **Time.** The music renders in one process (about 30 s) and the effects and ambience in the other (about 12 s). Mastering, the checks and the PNG then take about 20 s, and ffmpeg about 3 s. Wall time is about 54 s on this 4-core sandbox, which other jobs share. The script uses at most 2 processes, each single-threaded.
- **First run.** The numba kernels compile once (a few seconds) and are cached in `__pycache__/`, which git ignores.
- **Safe to read during a render.** Output files are written atomically (a temp file, then a rename), so a reader never sees a half-written WAV.
- **Repeatable.** Runs are deterministic: `SEED` in `aw2_core.py`, plus `zlib.crc32` of each cue's name. Moving one event changes only that event's sounds, not the noise of the others. One process and two processes give bit-identical files.

## Everything is timed from `cues.json`

The script reads:

- `duration`: the output length, exact to the sample.
- `fps`: used for the frame column in the event report.
- `shots`: each second's row in the report is labelled with its shot.
- `events`: every sound effect. The order in the file does not matter.
- `music.sections`: the score.

### Events

- **Name matching.** Each event goes to the handler registered under its base name, which is the name with any trailing `_<number>` removed. So `rise_groan_3`, `core_flicker_4`, a third `core_heartbeat` or an extra `bird_chirp` simply work. The `k`-th occurrence of a name gets its own seed and small variations.
- **Unknown names.** These are reported once (`WARNING: cues.json: unknown event name ...`) and ignored. An event outside 0..duration, or an `end` that differs from `duration`, is also reported.
- **Sounds that last.** These run until the next relevant event after their own cue, never to a fixed time:

  | sound | starts at | runs until |
  |---|---|---|
  | core hum | `core_glow_steady` | `engine_ignite` |
  | tremor | `tremor_start` | `hand_presses_ground` |
  | soil pour | `hand_presses_ground` | `stands_full_thud` |
  | each rise groan | its `rise_groan` | the next groan or the stand |
  | head-lift creak | `head_lift_creak` | `eyes_resolve` |
  | engine spool and wind ring | their cues | the held breath before the launch |
  | launch roar | `impact_frame` | `trail_fades` |
  | trail shimmer | `sky_reveal` | `trail_fades` |

  Inside these spans, the events that fall within them shape the sound: heartbeats swell the hum, the birds' burst peaks the tremor, and every groan, tear and curtain thickens the soil pour.
- **The held breath before the launch** (`launch_silence()` in `aw2_core.py`). It ends at `launch_smear` and lasts 15 % of the `wind_ring` → `launch_smear` build-up, clamped to 0.3–0.7 s. With the current cues that is 54.72–55.20 s (480 ms). The music's crescendo, the engine spool and the wind ring all stop at its start. The master then gates every stem to true digital silence inside it, reverb tails included. A short suck from `launch_smear` whips into `impact_frame`.
- **Fades.** `fade_in_start` (1.6 s cosine) and `fade_out_start` → `end` are applied in the master.
- **Ambience scenes.** These are derived from events:
  - dawn forest until `impact_frame`;
  - sky wind from `sky_reveal` to `trail_fades`;
  - the forest returns, gentler, for the coda.

  The distant birds stop at `birds_burst` and return in the coda; the crickets fade out after `sun_ray_reaches_face`.

### Music

Each section function reads its section's in and out times plus anchor events. It fits bar lengths to the spans between anchors, inside tempo limits; if a retime pushes a span outside them, it clamps the tempo and prints a warning. The anchors are:

| section | anchors |
|---|---|
| dawn | Bar 3 of the flute's phrase (the warm Gmaj7) lands on `sun_ray_reaches_face`. The tempo stays near ♩ = 72, limited so the phrase starts after `bird_crosses_far` and ends by `core_flicker`. The music box fits between the fade-in and the bird. |
| tremor | The pulse starts at the core's heartbeat interval (from the `core_heartbeat` times) and accelerates to `eye_lids_open`. The stab lands on `birds_burst` and the shimmer on `eyes_ignite`. A dominant anacrusis leads into `hand_presses_ground`. |
| rise | The theme runs from `hand_presses_ground` to `stands_full_thud`. If two 4/4 bars would go faster than about 72 BPM, it switches to the same two bars in a broad 3/4 (6 beats), so the giant never hurries. With cues v1 that gives 65 BPM. The stand, the climb during `head_lift_creak`, and the major resolve on `eyes_resolve`. |
| ignition | A held harmonic from the section start to `engine_ignite`. Then a crescendo (C, then D) and a scale run to the start of the held breath. Silence until `launch_smear`. |
| flight | Phrase b fills `impact_frame` → `sky_reveal`, broadening slightly. Its peak note sits exactly on `sky_reveal`. The cadence ends before `trail_fades`. |
| coda | The piano's open third arrives just after `bird_returns`, and the final chord before `fade_out_start`. |

### Retime tests

Both test sheets were derived from cue sheet version 0 and re-run with the current code.

| variant | result |
|---|---|
| uniform 8 % stretch (81.0 s), plus `rise_groan_3`, `core_flicker_3`, a third `core_heartbeat`, an extra `bird_chirp` and an unknown `mystery_event` | All 30 transient cues land within one frame. The theme peak is on `sky_reveal` (+0 ms). The held-breath silence lasts 518 ms; the rise theme runs at 58 BPM. The unknown event is warned about and skipped. |
| non-uniform edit (dawn 2 s shorter, 0.6 s more held breath, sky reveal 0.9 s sooner; 72.7 s) | 26 / 26 cues, peak +0 ms, silence 570 ms, rise at 63 BPM. |

The lead's own retime of the rise (cues v1) needed no code change for timing. The two changes below were improvements the lead asked for.

## The score

**Key plan.**

| part | key |
|---|---|
| dawn and tremor | D major |
| rise | D minor, turning to D major when the eyes resolve |
| canopy gap | a D Lydian glow (E major over D), which foreshadows the flight key |
| flight and coda | E major, a whole tone up |

The robot's core hum is A (55 Hz), the dominant of D, so the hum is consonant with the dawn and the rise. At the end of the dawn, the flute's final A dissolves into it.

**The theme** ("the old dream") is original: composed for this film and checked against the best-known Hisaishi melodies.

It is a 9-bar sentence in 4/4, written here in D. The rhythm per bar is: q q q. e | h q. e | h q q | w ‖ q q q. e | h q. e | h. e e | h. e e | w.

```
a  | F#4  A4  D5.  E5 | F#5 --  E5.  D5 | D5 --  C#5  B4 | A4 -- -- -- |
     D(add9)            Bm7               Gmaj7             Asus4 -> A
b  | G4  B4  E5.  F#5 | G5 --  F#5.  E5 | B5 -- --  A5 F#5 | E5 -- -- F#5 E5 | D5 |
     Em7                A7sus4             Gmaj7  (peak)       Asus4 -> A         D
```

Phrase a rises through the tonic arpeggio, reaches up a step (the "longing" ninth) and falls gently to a half cadence. Phrase b repeats that opening a step higher, then leaps a fifth to its peak: B5, the third of the IV chord.

**How the theme appears:**

| time | instrument | material |
|---|---|---|
| 2.4 s | music box | The opening motif an octave up (F#5 A5 D6 E6 F#6), slowing like a winding-down box. |
| 8.3 s | flute | Phrase a, over felt piano and a string pad. A harp unfolds Gmaj9 on the sun ray. |
| 35.6 s | horns and cellos | Phrase a in D minor, low, as a broad 3/4: F3 A3 D4. E4 \| F4 — E4 D4 \| D4 on the stand. Under it, low brass and timpani: Dm(add9) → Bbmaj7(#11) → Gm7 (the stand) → Asus4 → A7. The violins climb E5 F5 G5 A5 with the head. |
| 45.2 s | horns | On the resolve, F natural becomes F# and the horns sing the head motif in major. |
| 55.4 s | violins (octaves) and horns | Phrase b in E over a driving spiccato ostinato: A4 C#5 F#5. G#5 \| A5 G#5. F#5, over F#m7 → D (bVII). |
| 59.5 s (sky_reveal) | violins in octaves, flute, glockenspiel | The peak, C#6 over Amaj7. Horns and low brass carry the harmony: G#m7 → B7sus4 → E. |
| 67.9 s | piano alone | The head motif in E (G#4 B4 E5. F#5 → G#5), ending on the open third over IV → I. One soft music-box echo at the end. |

**Breathing with the picture:**

| moment | measured |
|---|---|
| near-silence before the tremor | music −41.6 dBFS RMS over 24–25 s, against a dawn average of −27.3 |
| held breath 48.5–51.5 s | music −38.7 dBFS (the crescendo after it is −21.9) |
| held-breath silence before the launch | true silence from 54.72 to 55.20 s: the mix peak inside it is −240 dBFS, i.e. digital zero |
| the peak on the sky reveal | 59.500 s, +0 ms |

## Instruments (all synthesized)

- **Flute.** A monophonic legato line. A harmonic oscillator whose spectrum brightens with loudness, quick fingered pitch transitions, and a delayed 5 Hz vibrato (mostly amplitude). Breath noise is partly modulated by the tone (pitched breath), and tongued notes get a short "chiff".
- **Strings** (vln1, vln2, vla, vc, cb):
  - Each section is 4–8 PolyBLEP saw players. Each player has its own detune (about 7 cents), timing offset (about 14 ms), glide, delayed vibrato (4.3–6.4 Hz) and slow drift.
  - A low-pass filter that follows the dynamics, and broad body resonances.
  - A per-section synthetic body impulse response: about 90 damped modes giving a dense, jagged, wood-like response (±9–10 dB). Vibrato moves the harmonics across it, which gives the shimmer of real strings. Each section keeps the same body all film long.
  - Bow noise.
  - Articulations: sustained/legato, unmeasured tremolo, flautando harmonics and spiccato. Pizzicato is modal.
- **Horns, trombones and tuba.** Per-player additive tone whose spectrum opens with loudness and lags the amplitude (the brass "bwah"). A lip scoop on attacks, a breath "blat" on loud onsets, and formant equalization.
- **Felt piano.** Inharmonic partials (stiffness coefficient by register), 1–3 detuned unison strings (beating), a prompt and an aftersound decay, partials that decay faster the higher they are, a soft felt thump, and damper release.
- **Music box, celesta and glockenspiel.** Modal tine and bar partials. The music box is slightly out of tune, like the real thing.
- **Harp.** Plucked harmonic partials with a pluck-position comb.
- **Timpani.** Membrane modes. The principal pitch glides down from a slightly sharp strike, with a mallet thump; rolls are alternating strokes.
- **Taiko, bass drum, crash, suspended-cymbal swell, reverse cymbal and tam-tam.** Taiko and bass drum use a pitch-dropped head; the cymbals use 120–160 random inharmonic modes per side; the tam-tam has a slow "bloom" of its upper modes.
- **Reverb.** The orchestra plays in a synthetic hall: 2.3 s, with early reflections, and the highs decay faster.

## Sound effects (the cue sheet, cues v1)

| cue | time | what is placed |
|---|---|---|
| bird_crosses_far | 6.8 | small bird far away: bounding wingbeats from 0.6 s before, right to left, distance-filtered; a far "tsip" |
| bird_wings_flare | 9.6 | braking flaps (11.5 Hz, weakening), panned in |
| bird_touchdown | 10.1 | two claw ticks, a moss scuffle, the wing fold |
| bird_hop | 10.9 | a wing flick on the cue, a light landing |
| bird_chirp | 12.2 | close call: a fast down-chip and a thin high note (twitters on odd occurrences) |
| sun_ray_reaches_face | 15.0 | old metal warming: tiny thermal "tinks" until the core wakes |
| core_flicker | 21.0, 21.5 | gated A1/A2 buzz with an arcing edge, crackle, relay click |
| core_glow_steady | 22.4 | the core hum spins up (power-up breath). It swells on each heartbeat, brightens with the eyes, steps up on standing and on the resolve, and fades as the engines ignite. |
| core_heartbeat | 23.4, 24.4 | lub-dub (100→60 Hz and 112→68 Hz) with a muffled body and a low metal ring |
| tremor_start | 25.0 | first jolt and pebbles jumping on the cue; then a rumble that peaks at the burst, eases while the eyes open and swells into the hand press; soil-stress crackle; pebble rattle; a far tree creak |
| birds_burst | 27.5 | 36 birds within about 1 s (8 large with wing claps, 6 medium, 22 small), each flying off to a side and darkening; canopy rustle; 7 alarm calls |
| eye_lids_open | 31.2 | lid servo, scrape, stop clunk, dust |
| eyes_ignite | 31.8 | electric zap on the cue, an in-key glide (A3+E4 → E4+A4), a lens ping |
| small_bird_flees | 32.6 | alarm "tchk"s and a fast take-off flying off right |
| rise_groan | 34.9 (the anticipation sink), 39.0 | a load tick; then a long, deep stick-slip metal groan (3–4.8 s, slip rate drifting 36→47 or 44→33 Hz, 16 high-Q structure modes plus a 46/63 Hz structural mode) in a big space. Two long metal creaks (up to 3 s, left and right), an overtone groan, servo whine, hydraulic hiss, joint clunks. |
| hand_presses_ground | 35.6 | a heavy sub thud (72→31 Hz, long decay), soil crunch, roots straining, arm servo; starts the soil pour (sand, clods, pebbles) that thickens with every later rise event until standing |
| roots_tear | 36.5 | fibrous ripping, four snaps, a woody creak, three vine whips with slaps |
| soil_curtain | 40.0 | a 3.2 s cascade (rushing body, dense sand, clods) |
| stands_full_thud | 41.1 | the weight lands: a heavy sub thud (84→30 Hz, long decay), frame and settle clanks, settle groan, debris shaking off |
| head_lift_creak | 43.5 | neck unlocks, a long deep metal creak (120→82 Hz) until the resolve, squeal, servo, end stop, dust |
| eyes_resolve | 45.2 | a focusing tone (D4+A4+D5), a lens ping |
| back_plates_open | 49.2 | four latch clunks, plates sliding, vent hiss, moss tearing |
| crouch_anticipation | 50.4 | joints compress, hydraulic squeeze, feet dig in |
| engine_sputter | 50.9 | 4–5 coughs with flame puffs, a failing spool, sparks |
| engine_ignite | 51.5 | WHOOMPH and flame bloom; then the spool-up (turbine whine, roar opening, rumble, crackle) building until the held breath |
| wind_ring | 52.0 | a pressure wave, then the ring whoosh. It starts centred and spreads wide (mid/side, never a delayed copy, so it stays mono-safe), with leaf and twig rattle, debris and trees bending, ending at the held breath. |
| launch_smear | 55.2 | out of the silence: a 0.2 s rising suck into the impact |
| impact_frame | 55.4 | LAUNCH: sonic thump, blast (body, roar and crack), debris shower. The roar recedes upward through a physical Doppler model: a variable propagation delay r(t)/c as the robot climbs, 1/r level, and air absorption. |
| canopy_burst | 56.9 | branch snaps, leaves exploding, the pass-through whoosh |
| sky_reveal | 59.5 | the trail: airy sweeping noise with faint E-major partials, in a long sky reverb |
| trail_fades | 66.0 | the trail dissolves |
| bird_returns | 70.5 | flutter in, lands on the cue, moss scuffle, a happy twitter |

**Ambience:**

- wind in leaves (gusts, quieter while the robot acts);
- a leaf-crinkle texture that follows the wind;
- crickets fading at sunrise;
- a distant stream in the valley;
- a sparse dawn chorus of six synthetic species, built from fast-FM syllables (chips, trills, warbles, whistles, coos), with no species twice in a row;
- high-altitude wind for the sky;
- leaves tumbling in the coda.

**Reverbs.** Effects use "near" (0.9 s), "far" (the forest: 2.7 s, dark) and "sky" (4.5 s, airy) synthetic impulse responses.

**Grains.** Every grain has a shaped onset and tail, and friction slips are 0.3 ms pulses rather than single samples, which avoids clicks.

## Mix and master

1. **Stem preparation.** Each stem gets a 28 Hz 4th-order high-pass and is folded to mono below 120 Hz (the side channel is high-passed). The effects stem also gets a −4 dB shelf below 50 Hz.
2. **Stem gains.** Music 0, effects +8, ambience +9 dB. Per-section music trims are in `SECTION_TRIM` (`aw2_score.py`), and every effect's gain is the `g=` of its `ctx.add` call.
3. **Rides from the cues.**
   - The music dips 3.5 dB under the launch blast and recovers by `canopy_burst`.
   - The ambience ducks 6 dB under the launch.
   - The held-breath gate silences all stems.
4. **Master.**
   - Cue fades.
   - Normalization to −20 LUFS.
   - A gentle stereo-linked RMS compressor (−20 dBFS, 1.7:1, 8 dB knee, 25 ms attack / 350 ms release).
   - Calibration to −17 LUFS through a true-peak limiter (4× oversampled detector, ceiling −1.35 dBTP, 3 ms look-ahead, 30 ms hold, 180 ms release).
   - A final true-peak check, then 24-bit TPDF dither.

   The master is one gain curve, applied to the mix and to each stem.

## Measurements (this render, cues v1)

**Overall:**

| measure | value |
|---|---|
| integrated loudness | **−17.0 LUFS** (own meter and ffmpeg `ebur128` agree) |
| true peak | **−1.35 dBTP** (ffmpeg: −1.3); sample peak −1.36 dBFS; no samples at full scale |
| loudness range | 16.2 LU (low −28.8 / high −12.6 LUFS); a cinema-style range with a quiet opening |
| stems (integrated) | music −18.9, effects −19.1, ambience −35.2 LUFS |
| master | compressor at most 4.0 dB; limiter at most 4.0 dB, only on the launch transient (55.44 s) |
| sub-bass (below 60 Hz) | −7.6 dB of the full-band energy over the film. The heaviest seconds are the requested hand-plant and stand thuds (worst −2.0 dB). Everything else is well below. |
| stereo | L/R correlation 0.65 overall (per second: minimum 0.29, median 0.69); a mono fold-down changes integrated loudness by only −1.2 dB, so nothing is phasey |
| integrity | 3,600,000 samples (75.000 s); DC about 2e-6; last sample 0 |
| click scan | 0 in music and ambience. 1 marginal flag in effects (z 13 against a threshold of 12, at −31 dBFS, 21.075 s), where the designed core crackle overlaps the buzz. Every generated sound scanned on its own is clean. |
| events | all 26 transient cues have their main sound starting within one frame (most at +0–3 ms). Long swells (sun ray, glow, sky reveal, smear) start softly by design. |

**Mean momentary loudness by section** (LUFS):

| dawn | tremor | rise | ignition | flight | coda |
|---|---|---|---|---|---|
| −25.0 | −20.2 | −16.2 | −16.6 | −13.5 | −26.6 |

**Momentary loudness per second** (mix, LUFS):

```
 0- 9   -44  -33  -30  -30  -29  -28  -29  -29  -27  -26     dawn: wind, crickets, music box, flute enters
10-19   -26  -25  -22  -26  -25  -21  -20  -21  -22  -24     bird lands; the sun-ray swell (15-16)
20-29   -26  -27  -30  -26  -27  -26  -20  -17  -17  -20     core flicker, hum, heartbeats; tremor; the flock (27-28)
30-39   -23  -24  -21  -23  -23  -14  -15  -16  -15  -15     eyes; the sink groan (34.9) and hand plant (35.6); groans, roots
40-49   -14  -13  -18  -19  -18  -17  -18  -21  -25  -21     soil curtain, the stand (41.1); head lift; canopy gap; held breath
50-59   -23  -18  -16  -15  -12  -12  -12  -12  -15  -12     sputter, ignition, wind ring, crescendo, silence, LAUNCH (55.4), the peak (59.5)
60-69   -12  -14  -14  -15  -15  -16  -17  -20  -25  -30     the theme soars and resolves; trail fades
70-74   -31  -27  -32  -34  -50                              coda: piano, the bird returns, fade
```

The printout also gives each second's RMS, peak, correlation, side/mid ratio and per-stem loudness.

## Self-checks printed on every run

- **Cue validation.** Unknown names, events out of range, `end` ≠ duration.
- **Loudness summary.** Integrated loudness, true peak, sample peak, LRA, stem loudness, compressor and limiter work.
- **Per-second table and section summary.** Loudness and stem balance for every second.
- **Sub-bass, stereo, clipping and DC.**
- **Click scan.** Second-difference spikes that stand far above their ±2 ms surroundings.
- **Event check.** For every cue: what its handler placed, where the main ("sync") sound's energy actually starts relative to the cue, in ms and frames, and the nearest spectral-flux onset heard in the effects stem.
- **Music sync.** The theme peak against `sky_reveal`, the flute's warm chord against the sun ray, the rise tempo, the near-silence, the held breath, the launch silence and the cut.
- **`spectrogram.png`** and the ffmpeg `ebur128` cross-check.

## Honest weaknesses

No one has listened to this render; it was judged by analysis (spectra, levels, onsets, a dump of every note). The likely weak spots:

- **Instruments.** The strings are well-built synth strings (detuned saws through body filters and a synthetic body response), not a recorded orchestra; legato and tremolo are the most convincing, fast spiccato the least. The brass is clean and slightly organ-like at soft dynamics. The flute and felt piano are plausible but lack a real player's micro-variation; the piano's low register is simpler than a real soundboard.
- **Birds.** Syllable-based birds (fast FM sweeps) are a clear step up from the first film's slow whistles, but the close little bird may still read as synthetic. The flock is a dense wing texture rather than individual birds.
- **Metal and engines.** The stick-slip groans and creaks sound metallic and frictional, but may suggest a ship or a door more than a 13 m machine. The engine and roar sources are generic filtered noise with a low saw tone; the Doppler recession is physical, the source is not.
- **The launch.** It is dense rather than cracking, because the limiter takes up to 4 dB off the blast (it now comes straight out of digital silence) to keep −1 dBTP at −17 LUFS.
- **Sub-bass.** The requested heavy thuds carry a lot of sub energy for a second each. On small speakers they read mostly through their 80–300 Hz body; on a big system they are big.
- **Quiet passages.** The LRA of 16 LU is cinematic; on small speakers the dawn (around −28 LUFS momentary) and the coda are quiet.
- **Extreme retimes.** For very large changes (a span needing a tempo outside about 60–160 BPM, or a melody span cut below half), the score clamps the tempo and warns. Its anchored downbeats can then drift, so watch the warnings.
- **Originality.** The theme was written for this film and compared by ear-memory with well-known Hisaishi themes (no automated plagiarism check exists here).
