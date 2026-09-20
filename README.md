# Wolfpunk Wanderer

A MIDI note/CC manipulator for the
[Adafruit MacroPad RP2040](https://www.adafruit.com/product/5128): three
keys sound a sliding window of notes from a scale, the other nine each own
one live-adjustable MIDI parameter, and the encoder either slides the note
window or (held) changes scale. USB MIDI out, general-purpose enough to
drive any synth - not tied to one instrument's CC map.

Third instrument on this board, after
[Wolfpunk Foam](https://github.com/wolfpunk25/Wolfpunk-Foam) (a groovebox)
and [Wolfpunk Possibility](https://github.com/wolfpunk25/Wolfpunk-Possibility)
(a generative sequencer, which this replaces). Separate repo on purpose, same
reason as that pivot: Possibility stays intact and re-flashable, only the
board itself moves on. This one doesn't touch the onboard speaker for sound
generation - no `synthio` voice, just USB MIDI out - so none of the
retrigger/filter gotchas documented in the other two repos apply here. It
does use the speaker once, for a two-tone startup chime.

## Controls

```
 [ N1  ][ N2  ][ N3  ]   <- note toggles, sliding scale window
 [MOD W][FILTR][ RES ]
 [ ATK ][ REL ][PORTA]
 [ BEND][TRNSP][REVRB]

        (ENCODER)
```

**Top row (keys 0-2) - note toggles.** Each press latches a note on;
press again to release it. Together they always sound three *consecutive*
scale degrees - not three independent notes you pick freely.

**Encoder, rotated alone** - slides that three-note window up or down the
scale one degree at a time ("rotating selects three more notes"). Any
notes currently latched are released first, so a bank change can never
leave a note stuck sounding a pitch no key still represents - re-press to
sound the new window.

**Encoder, pressed and rotated** - cycles the scale (7 of them: Major,
Minor, Dorian, Byzantine, Lydian, Mixolydian, Harmonic Minor).

**Encoder, quick press with no rotation** - recenters the note window back
to the root (a bonus "home" gesture, not part of the original spec - easy
to repurpose in `handle_encoder_switch_up()` in `code.py` if you'd rather
it did nothing).

**Encoder, held 5 seconds** - panic: releases every latched note and sends
MIDI All Notes Off (CC123), independent of whether you're also rotating it.

**Rows 2-4 (keys 3-11) - sound manipulation, one MIDI parameter each:**

| Key | Parameter | MIDI |
|---|---|---|
| 4 | Mod Wheel | CC1 |
| 5 | Filter Cutoff | CC74 |
| 6 | Resonance | CC71 |
| 7 | Attack | CC73 |
| 8 | Release | CC72 |
| 9 | Portamento | CC5 |
| 10 | Pitch Bend | dedicated Pitch Bend message |
| 11 | Transpose | local only - shifts the note window, sends nothing |
| 12 | Reverb Send | CC91 |

**Hold one of these and twist the encoder** to adjust its value live -
the screen shows the parameter name and a value bar, and its key LED
brightens with the value. **A quick tap with no rotation resets it** to
its default and sends that. Only one of the nine can be "active" at a
time - whichever you pressed first owns the encoder until you let it go;
pressing a second one while the first is still held does nothing until
the first is released.

All seven CC parameters (everything but Transpose) **start centred at 64**
rather than at 0, and a full turn of the encoder covers roughly the whole
0-127 range - half a turn from the default gets you close to either
extreme, a full turn reaches it outright. Pitch Bend follows the same
feel, centred at 0 across its -8192..8191 range. This was tuned from a
measurement, not a spec sheet (see `wolfpunk/params.py`'s comment), so if
it's still too twitchy or too slow, `step` there is the one number to
adjust. Transpose is the one exception kept at 1 semitone per detent -
it's a discrete musical value, and coarser stepping would skip notes you'd
want to land on exactly.

Pitch Bend and Transpose behave like the other seven (settable and
sticky, not spring-back-to-center) rather than simulating a real pitch
wheel, so all nine parameters share one consistent gesture. If you'd
rather Pitch Bend snapped back to center on release, that's a small change
in `_manip_key_up()`.

## LEDs

- Note keys: lit in a scale-degree colour when latched, dim when not.
- Manipulation keys: a fixed hue per parameter, brightness tracking its
  current value (always slightly lit, so you can tell keys apart even at
  their minimum) - full brightness while it's the one actively held.
- Any flash (scale change, bank reset, panic, parameter reset) briefly
  lights all twelve white.

## Screen

Idle: root + scale on line 1, the three current note names on line 2
(the sounding ones marked with `*`), channel (or a flash message) on line
3. Holding a manipulation key replaces this with that parameter's name,
value, and a bar.

## Startup

A two-tone beep-bloop through the onboard speaker (`macropad.play_tone`),
nothing more - no synth voice runs on this board for this project.

## Layout

```
CIRCUITPY/
  boot.py            does nothing - keeps CIRCUITPY mounted as a drive
  code.py            main loop: keys, encoder, MIDI, display/LED refresh
  wolfpunk/
    scales.py         7 scales, degree->MIDI note (handles negative degrees)
    notes.py          the sliding 3-note bank window over a scale
    params.py         the 9 manipulation-key parameter definitions
    ui.py             OLED + NeoPixel rendering
tools/install.sh      rsync CIRCUITPY/ onto the mounted board
tests/                host-side tests for scales/notes/params, no board needed
```

## Installing it

Board mounts as `CIRCUITPY`. Needed libraries (already on this board from
the earlier projects; see the Wolfpunk Foam README if starting fresh -
`circup` doesn't run under this Mac's system Python, there's a manual
bundle-zip fallback documented there): `adafruit_macropad`,
`adafruit_midi`, `adafruit_debouncer`, `neopixel`, `adafruit_display_text`,
`adafruit_pixelbuf`.

```bash
./tools/install.sh
```

Then plug into a DAW/synth over USB and it shows up as a MIDI device
called "MacroPad" (or similar, USB-MIDI descriptor default) - no BLE
pairing needed, this one's wired.

## Tests

```bash
./tests/run.sh
```

Pure-Python, no board needed - checks every scale rises strictly across
its 7 degrees (and wraps correctly on negative degrees), that a sliding
3-note bank window always ascends and stays in 0-127 even at its
clamped extremes, that transpose shifts the window by exactly the right
amount and clamps rather than wraps, and that every parameter's default,
normalization, and step-clamping behave. This caught a real bug before any
hardware was involved: the scale table borrowed from Wolfpunk Possibility
had a `WholeTone` entry padded to 7 slots by repeating the octave note,
which produced two identical notes wherever a sliding window crossed that
seam - harmless in Possibility's triad-picking code, not harmless here.
Swapped for Harmonic Minor, a genuine 7-note scale. Also checks that half
a turn of the encoder from each CC/Pitch Bend parameter's centred default
lands within 10% of an extreme and a full turn reaches it outright - the
"hold and twist" responsiveness tuned from a real measurement (see
`wolfpunk/params.py`).

## Design choices worth knowing about

- **Root is fixed at C.** Nothing in the request asked for a way to change
  it independently of Transpose, which already covers repitching the whole
  window ±24 semitones. Easy to add a `ROOT` control later if wanted.
- **Bank slides one degree at a time**, not in non-overlapping jumps of
  three. "Rotating the encoder selects three more notes" was read as a
  moving window rather than swapping to an unrelated triad - it's finer
  control and every adjacent window overlaps the last by two notes.
- **A bank change always releases whatever's latched**, rather than trying
  to keep already-sounding notes ringing while the keys under them start
  meaning something else. Simpler, and avoids the stuck-note class of bug
  the sister LydianToggle box's diff-based sync exists to prevent.
