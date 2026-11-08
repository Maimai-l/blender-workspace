# Awakening -- soundtrack (`audio/`)

A 56-second stereo soundtrack for the short anime film about a giant ancient robot
awakening in a misty forest at sunrise. Everything is synthesized in Python
(numpy + scipy): shaped noise, FM/additive/subtractive oscillators, granular bursts,
envelopes and convolution reverb from synthetic impulse responses. No speech, no
samples, no borrowed music.

## Files

| file | what |
|---|---|
| `make_audio.py` | the generator (deterministic, `SEED = 20261108`); one function per cue |
| `mix.wav` | the result: 56.000 s, 48 kHz, 16-bit PCM stereo, 10.75 MB |
| `README.md` | this cue sheet |

Run `python3 make_audio.py` (about 11 s on 4 cores). It rewrites `mix.wav`, prints a
per-second level table and, if `ffmpeg` is on the path, an EBU R128 summary
(`ffmpeg -i mix.wav -af ebur128=peak=true -f null -`). `--no-ffmpeg` skips that pass.
Two consecutive runs produce bit-identical files (numpy 2.5.3 / scipy 1.18.1; other
library versions may change the noise sequences slightly).

## Measured result

| | |
|---|---|
| integrated loudness | **-18.0 LUFS** (own BS.1770 meter and ffmpeg agree) |
| true peak | **-1.4 dBTP** (sample peak -1.5 dBFS; ceiling -1.5 dBFS, 4x oversampled check) |
| loudness range (ffmpeg) | 9.9 LU, LRA low -22.6 / high -12.7 LUFS |
| master | compressor max 3.8 dB (1.8:1 above -22 dBFS RMS), limiter max 5.6 dB at the 47.4 s blast, master gain +11.0 dB |
| fade | hard cosine fade 55.0-56.0 s, last sample exactly 0 |

Dynamic shape, mean RMS per section (dBFS, both channels):

| section | time | RMS | peak |
|---|---|---|---|
| dawn, little bird | 0-23 | -25.9 | -6.9 |
| tremor + flock | 23-28 | -20.1 | -4.0 |
| eyes / pause | 28-29.8 | -25.7 | -11.6 |
| robot rises | 29.8-37.6 | -17.2 | -1.5 |
| standing, servo | 37.6-43 | -22.8 | -3.0 |
| tension + ignition | 43-47.4 | -17.3 | -1.5 |
| launch | 47.4-49.3 | -13.2 | -1.5 |
| aftermath | 49.3-55 | -19.8 | -1.5 |
| fade | 55-56 | -30.8 | -13.0 |

Momentary loudness per second (K-weighted, LUFS), 0 s to 55 s:

```
-25 -23 -20 -18 -21 -25 -26 -23 -24 -25 | -20 -20 -18 -22 -25 -20 -23 -20 -19 -23
-24 -25 -20 -23 -23 -15 -15 -19 -22 -23 | -17 -16 -16 -17 -13 -18 -19 -15 -21 -22
-20 -19 -23 -23 -19 -14 -13 -11 -11 -14 | -17 -19 -19 -20 -21 -27
```

The quiet dawn bed sits at about -30 dBFS RMS per channel (-25 LUFS) with gusts to
-18; the tremor/flock peak at -15; the rise at -16 with the footfall at -13; a lull at
-20..-23 while the robot stands; the ignition ramps -19 -> -13; the launch peaks at
-10.7 LUFS momentary and recedes to -19 by 52 s; everything fades to silence at 56.0.

## Signal path

- `Bus`: stereo float bus with constant-power panning (scalar or time-varying pan) and
  two reverb sends. `far` = long dark forest reverb (RT60 2.8 s, 30 ms pre-delay,
  highs decay 3x faster), `near` = short close reverb (RT60 1.1 s, 12 ms). Both IRs are
  band-split exponentially decaying noise plus seven early reflections, normalised to
  unit energy and convolved with `scipy.signal.fftconvolve`.
- Master: 18 Hz high-pass, cosine fade 55-56 s, RMS compressor (1 ms detector frames,
  20 ms attack / 300 ms release, soft knee), gain calibration to -18 LUFS through the
  limiter (4 iterations), look-ahead peak limiter (running-minimum gain over +-40 ms,
  Hann-smoothed over +-4 ms so it can never exceed the required gain, 150 ms release),
  true-peak check at 4x oversampling, TPDF dither to 16 bit.

## Cue sheet (seconds; all placements are sample-accurate, slow swells are intended)

**0.0-56.0 dawn forest bed** (`cue_ambience`, `cue_distant_birds`)
- Wind: pink noise through a time-varying band-pass (centre 140 Hz x (1 + 2.4 wind),
  Q 0.7) plus a white-noise "hiss" band (700 Hz x (1 + 2.5 wind), Q 1.4) that only
  emerges in gusts, plus a leaf texture (2.5-7.5 kHz noise gated by a 14 Hz random
  flutter). Gusts are asymmetric bumps (1.2-2.2 s rise, 2.5-4.5 s fall) at 1.2, 9.3,
  16.5, 24.4, 30.9, 38.5, 44.6 and 51.8 s; natural gusts are reduced while the robot
  acts, replaced by a scripted rise over 44.6-49.5 and gentle at the end. Two
  decorrelated channels share 35 % of a common noise for a stable image.
- Distant birds: five synthetic species (slow up-sweeps, a trill, a vibrato warbler, a
  low dove, a long flute note) built from sine sweeps with small vibrato and a weak
  second harmonic, low-passed at 5.5 kHz and sent mostly to the far reverb. One phrase
  every 2-4 s from 0.6 to 24.3 s, a few hesitant ones 38.5-42.6, returning from 53.5.
- Insects: two faint 6.5-9.5 kHz bands with irregular 9-11 Hz amplitude modulation,
  about -48 dBFS, thinned 43-54 s.

**8.3-10.3 little bird flies in** (`cue_little_bird`): wing flutter = band-passed noise
puffs (1-5 kHz, 50 ms, 11 ms decay) at 9.5 Hz with alternating down/up-stroke weight,
plus a small low "thrum" per flap; approaches (pan 0.55 -> -0.15) and fades as it lands.
**10.3** tiny scuffle (four to six 4-14 ms high-passed ticks and a soft thump).
**10.6, 12.2, 15.0, 18.5, 22.0** close chirps: 2-3 up-swept notes at 3.3-5.6 kHz with
60 Hz vibrato and a strong second harmonic, drier (near reverb only), panned slightly
left, peaking around -13 dBFS. **25.7** flies off, pan -0.15 -> 0.85, low-passed as it
goes.

**13.0-18.0 sun on the robot's face** (`cue_sun`): E6 G#6 B6 E7 B7 sine partials, three
chorused voices each, slow flicker, 2.8 s raised-cosine swell / 2.6 s release. Peaks
at -36 dBFS before master gain, i.e. 2-3 dB under the bed, in a band the bed leaves
empty: barely audible, as asked.

**19.3-22.4 chest lamp** (`cue_lamp`, `cue_hum`): 55 Hz hum with six harmonics and a
band-passed sawtooth "electrical" edge, gated on for 50-140 ms at 19.3, 19.5, 20.3,
20.55, 20.8, 21.0, 21.4, 21.7 (6 ms / 12 ms fades) with a 3-7 click crackle at each
flicker; from 22.4 a continuous very quiet hum (-41 dB law) that persists until the
launch (gone by 50 s).

**23.5-27.8 ground tremor** (`cue_tremor`): 20-60 Hz band-passed noise, a 40 Hz sine
with 1.3 Hz pitch wobble and 6.3 Hz tremolo, and a little 90-260 Hz body for small
speakers; envelope from nothing at 23.5 to full at 26.5, settled by 27.8. Pebble
patter 24.0-27.5: Poisson-timed resonant noise ticks (1.5-6.5 kHz, 6-30 ms) whose
rate follows the tremor, spread across the stereo field.

**24.6-28.0 the flock** (`cue_flock`): 18 birds, each a 1.5-3 s flutter at 6.5-9.5 Hz in
its own 350-700 / 1800-3800 Hz band, starting mostly in 24.6-25.2 (peak density at
25.3), each fading and low-passing as it moves off toward a random side. Seven alarm
calls: 7-12 Hz repeated 45 ms down-swept chirps with amplitude roughness, drifting
outward and fading. All gone by 28.0.

**26.4-28.0 the eyes wake** (`cue_eyes`): two sine partials gliding up a sixth over
1 s (G3 -> E4 and D4 -> B4, exponential glide), soft attack, then handing over to the
warm hum (A2 + E3 triangle-like partials, chorused) that settles in from 27.0 and
stays with the robot.

**29.8-37.6 the robot rises** (`cue_rise`, `cue_debris`)
- Metal groans at 29.8 (2.2 s, 55 Hz, bend +12 %), 31.2 (1.6 s, 73 Hz, -8 %), 32.6
  (2.6 s, 62 Hz, +20 %), 34.2 (1.4 s, 82 Hz, -10 %), 36.0 (2.4 s, 55 Hz, +6 %): three
  detuned band-limited sawtooths with a slow pitch bend, stick-slip amplitude grit
  (70 Hz random), four metal-body resonances (160/390/870/1900 Hz), soft clipping.
- Creaks at 30.1, 32.9, 34.4, 36.3: jittered 0.7-1.5 kHz tone with harmonics and
  stick-slip AM, quiet.
- Hydraulic hisses at 30.6, 32.8, 35.0: noise through a band-pass sweeping 3.8 kHz ->
  0.8 kHz with exponential decay.
- Soil and debris 30.0-35.5, heaviest 32.5-34.5: three Poisson grain clouds -- soil
  rumble grains (45-90 to 170-330 Hz noise, 80-240 ms), patter (resonant 0.4-2.5 kHz
  ticks) and pebbles, random pans.
- Footfall 34.6: sine pitch drop 95 -> 34 Hz with 0.35 s decay, low rumble, short click,
  followed by a burst of debris patter.
- 37.4 settling clank: five inharmonic metal modes (412-3620 Hz) in slowly beating
  pairs, a noise transient and a low body; a second softer weight-settling thump; the
  hum steps up 30 %.

**40.8-41.6 head lifts** (`cue_servo`): band-limited saw motor sweeping 180 -> 460 ->
300 Hz, thin band-pass, faint gear whine, a little noise; a gentle stop at 41.6 (520 Hz
+ 1480 Hz damped tock with a 3 ms click).

**43.0-47.0 tension**: the hum deepens (E1 41 Hz sub-hum fades in 43-46.5, warm hum up
25 %), insects and leaf texture thin to 40 %, the wind bed rises from 44.6.

**44.2-47.4 ignition** (`cue_ignition`): sputters at 44.35, 44.8, 45.4 = sine pitch
drop 120 -> 38 Hz plus a low-passed noise tail and a short mid burst, growing 3 dB
each; roar build 45.4-47.4 = white noise through a resonant low-pass (Q 3.5) rising
150 -> 900 Hz plus a 42 -> 58 Hz sub tone; wind ring 44.6-47.2 = broadband whoosh
whose band-pass centre sweeps 250 -> 1800 -> 600 Hz while its energy moves left to
right, with a granular leaf-rattle layer.

**47.4 LAUNCH** (`cue_launch`): blast = sine impact 140 -> 32 Hz (0.6 s decay), 60-400 Hz
body, 200-2500 Hz roar burst, high crack; roar ramps to full by 48.0 then recedes
48.0-52.0 with a Doppler-like fall (sawtooth engine tone 68 Hz and the noise resonance
1400 Hz both drop to 55 %, volume -4 -> -32 dB), a dark low-passed copy with growing
far-reverb share takes over as it leaves (distant rumble by 53, inaudible by 54);
second, larger whoosh 47.5-49.5 sweeping right to left (180 -> 2600 -> 350 Hz).

**49.3-56.0 aftermath** (`cue_aftermath`): the wind settles (scripted bed), falling
leaves = sparse soft 2.5-8.5 kHz grain flutters thinning from 14/s to 1.5/s over
49.5-55, ambience and distant birds return from 53.5, and a pad of A2 E3 C#4 G#4 B4 D#5
(A lydian) triangle-like partials with three chorused voices per note rises from
48.5, peaks 51-53 (about -20 LUFS) and fades out by 56. Hard fade 55.0-56.0.

## Frank notes (by analysis, not by ear -- nothing here has been listened to)

Most likely to convince: the overall dynamic arc (it is exactly the shape in the
table); the tremor, blast and Doppler roar (sub/noise synthesis is what this toolkit
does best); the lamp flicker and ignition sputters (simple, well-defined mechanical
gestures); the footfall; the pad and the eye glide (pure, consonant, in key with the
A hum); the wind bed's gust structure and the two whooshes.

Least convincing, probably: the birds. Sine/FM sweeps with smooth envelopes read as
"whistly synth birds" rather than real species, and the close little bird is the most
exposed; the alarm calls may sound electronic. The wing flutters are the classic
noise-puff approximation and the flock may come across as a generic rustle or
applause-like texture. The metal groans are detuned saws through formant resonators,
which can land nearer to a synth bass or a didgeridoo than to stressed steel; the
creaks are the weakest "metal" element. The clank's inharmonic modes are plausible but
generic. The insect shimmer is nearly inaudible by design.

Trade-off to know about: -18 LUFS integrated with a true peak under -1 dBTP and a
genuinely quiet opening forces the limiter to take about 5.6 dB off the launch blast
transient (the compressor takes up to 3.8 dB before it). The blast will sound dense
rather than cracking. If a less restrictive target is acceptable (-20 LUFS integrated,
or -2 dB on the climax), lower `TARGET_LUFS` or the `blast()`/`roar` gains in
`cue_launch` and the limiter will barely work.
