# Wolfpunk Wanderer

A MIDI note/CC manipulator for the
[Adafruit MacroPad RP2040](https://www.adafruit.com/product/5128): three
keys each toggle a note into a growing polyphonic pool, the encoder grows
that pool further, and once 2+ notes are active they auto-arpeggiate
instead of holding as a static chord. The other nine keys each own one
live-adjustable MIDI parameter. USB MIDI out, general-purpose enough to
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
 [ N1  ][ N2  ][ N3  ]   <- note pool toggles (degrees 0, 1, 2)
 [MOD W][FILTR][ RES ]
 [ ATK ][ REL ][PORTA]
 [ BEND][TRNSP][REVRB]

        (ENCODER)
```

**Top row (keys 0-2) - note pool toggles.** Each key owns one fixed scale
degree (0, 1, 2 - never moves) and toggles it in/out of the "note pool".
The pool only *grows* until something explicitly empties it - see below.

**Encoder, rotated alone** - grows the pool: turning right adds the next
scale degree above whatever's currently the highest active note; left
adds the next one below. An empty pool seeds at the root either direction.
Nothing already sounding is ever swapped out or interrupted by turning it
- this replaced an earlier "sliding 3-note window" design that killed
whatever was latched every time the encoder moved, which felt wrong in
practice (see Design choices below).

**Encoder, pressed and rotated** - cycles the scale (7 of them: Major,
Minor, Dorian, Byzantine, Lydian, Mixolydian, Harmonic Minor). Existing
pool degrees are recomputed against the new scale immediately, so a scale
change retunes whatever's already playing rather than needing new notes.

**Encoder, quick click (no rotation, not part of a double-click)** - tap
tempo for the arpeggiator: tap it twice in time and the gap between taps
sets the BPM.

**Encoder, double-click** - resets all 9 sound-manipulation parameters
(rows 2-4) back to their defaults. Replaced the earlier "tap a
manipulation key with no rotation resets it" behaviour, which was
resetting things by accident whenever a key was pressed just to check it
without meaning to change anything.

**Encoder, held ~0.8 seconds** - clears the note pool entirely (and sends
MIDI All Notes Off, CC123). This used to be a 5-second hold doing the same
thing under the name "panic" - shortened once it got its own dedicated
gesture instead of being a last-resort safety net.

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
| 11 | Transpose | local only - shifts the note pool, sends nothing |
| 12 | Reverb Send | CC91 |

**Hold one of these and twist the encoder** to adjust its value live -
the screen shows the parameter name and a value bar, and its key LED
brightens with the value. Letting go without turning it does nothing -
the value stays wherever it was. Only one of the nine can be "active" at
a time - whichever you pressed first owns the encoder until you let it
go; pressing a second one while the first is still held does nothing
until the first is released. (To reset a parameter, double-click the
encoder - see above; it resets all nine at once rather than one at a
time, since there's no longer a per-key gesture free to reset just one.)

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

## Arpeggiator

Whatever's in the note pool never sounds as a held chord - as soon as
there's 1 or more notes active, the arpeggiator cycles through them one at
a time (ascending pitch order, wrapping around), retriggering a note the
instant it starts even with just one note active, so nothing plays as a
sustained drone. Rate defaults to 120 BPM at 8th notes (`ArpClock(bpm=120,
steps_per_beat=2)` in `code.py`); tap tempo (quick single clicks of the
encoder) resets it live. Only the ascending pattern exists right now -
`wolfpunk/arp.py`'s `next_up_index()` is the one function to extend for
down/up-down/random patterns later.

Notes added purely via the encoder (beyond the 3 keyed degrees) have no
individual way to remove just that one note - only re-toggling one of
keys 0-2, or a long-press clearing everything, changes the pool. That's a
deliberate tradeoff of the "keys toggle, encoder only grows" model: fine
detail in exchange for never accidentally losing what's already ringing
when you reach for the encoder.

## LEDs

- Note keys: each lit in its own fixed scale-degree colour (key 1's
  colour never changes, unlike the old sliding-window design) - dim when
  its degree isn't in the pool, brighter when it is, full brightness for
  the one instant it's the arpeggiator's current step.
- Manipulation keys: a fixed hue per parameter, brightness tracking its
  current value (always slightly lit, so you can tell keys apart even at
  their minimum) - full brightness while it's the one actively held.
- Any flash (scale change, notes cleared, settings reset, tap-tempo BPM)
  briefly lights all twelve white.

## Screen

Idle: root + scale on line 1, the current note pool (note names, low to
high) on line 2 - "-- no notes --" when empty - BPM and channel (or a
flash message) on line 3. Holding a manipulation key replaces this with
that parameter's name, value, and a bar.

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
    notes.py          the growing note pool - which degree the encoder adds next
    arp.py            the arpeggiator's step pattern and tap-tempo clock
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
its 7 degrees (and wraps correctly on negative degrees), that the note
pool only ever extends outward and seeds at the root, that transpose
shifts a note by exactly the right amount and clamps rather than wraps at
the MIDI extremes, that the arpeggiator's step index cycles correctly
however many notes are active (and never raises if the pool shrinks
between steps), that tap-tempo's interval math clamps to a sane BPM range
instead of exploding on a near-instant double-tap, and that every
manipulation parameter's default, normalization, and step-clamping
behave, including the "hold and twist" responsiveness tuned from a real
measurement (see `wolfpunk/params.py`). Caught a real bug before any
hardware was involved: the scale table borrowed from Wolfpunk Possibility
had a `WholeTone` entry padded to 7 slots by repeating the octave note,
which produced duplicate-pitched degrees near the seam - harmless in
Possibility's triad-picking code, would not have been harmless here.
Swapped for Harmonic Minor, a genuine 7-note scale.

## Design choices worth knowing about

- **Root is fixed at C.** Nothing in the request asked for a way to change
  it independently of Transpose, which already covers repitching the whole
  pool ±24 semitones. Easy to add a `ROOT` control later if wanted.
- **The note pool only grows, never gets rearranged.** An earlier design
  had the encoder slide which 3 notes the top keys represented, releasing
  whatever was latched every time it turned so nothing went stale. In
  practice that felt wrong - turning the encoder while playing shouldn't
  cut off what's sounding. Now keys 0-2 own one fixed degree each forever,
  and the encoder only ever adds - removal is either untoggling one of
  those 3 keys, or a long-press clearing everything. No gesture
  rearranges what's already there out from under you.
- **Arpeggiate always, not as a toggle.** "I'd like some kind of
  arpeggiator rather than continuous notes" read as wanting to replace
  static held chords outright, not add a mode switch for it - so there's
  no separate ARP on/off control, the pool always cycles the moment it's
  non-empty, even with just one note in it (a single repeated pulse
  rather than a sustained tone).
- **Encoder gestures got split up as they accumulated meaning.** What was
  one 5-second "panic" hold is now two separate gestures once there was a
  real distinction to make: a quick double-click for "reset settings"
  (deliberate, not resettable by accident) and a much shorter ~0.8s long
  press for "clear notes" (needs to be fast enough to use mid-performance,
  not just as a last-resort safety net).
