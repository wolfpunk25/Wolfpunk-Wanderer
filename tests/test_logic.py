#!/usr/bin/env python3
"""Host-side tests for the pure-Python core (scales/notes/params) - no
board needed. Run before ever flashing, same pattern as Wolfpunk
Possibility: catch logic bugs in plain python3, save the hardware loop for
what can only be verified live."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "CIRCUITPY"))

from wolfpunk.scales import SCALE_NAMES, midi_note
from wolfpunk.notes import degree_to_midi, next_degree_to_add
from wolfpunk.params import PARAMS, normalized, step_value, clamp
from wolfpunk.arp import bpm_from_tap_interval, step_interval_s, next_up_index

failures = []


def check(label, cond):
    if not cond:
        failures.append(label)
        print(f"FAIL: {label}")


# -- scales: every scale must rise strictly across its 7 degrees ----------
for name in SCALE_NAMES:
    notes = [midi_note(0, name, d) for d in range(7)]
    check(f"{name} rises strictly", all(b > a for a, b in zip(notes, notes[1:])))

# -- scales: negative degrees must wrap into the octave below, not crash --
for name in SCALE_NAMES:
    n_minus1 = midi_note(0, name, -1)
    n_6 = midi_note(0, name, 6)
    check(f"{name} degree -1 == degree 6 minus an octave", n_minus1 == n_6 - 12)

# -- notes: degree_to_midi never leaves the 0-127 MIDI range, however far
# the pool has grown ---------------------------------------------------
for name in SCALE_NAMES:
    for degree in (-40, -14, -1, 0, 1, 14, 40):
        n = degree_to_midi(0, name, degree)
        check(f"{name} degree {degree} in range", 0 <= n <= 127)

# -- notes: transpose shifts a note by exactly that many semitones, and
# clamps rather than wraps at the extremes ---------------------------------
base = degree_to_midi(0, "Major", 0, transpose=0)
shifted = degree_to_midi(0, "Major", 0, transpose=5)
check("transpose shifts a note by +5", shifted - base == 5)
check("transpose clamps at the top", degree_to_midi(0, "Major", 40, transpose=999) == 127)
check("transpose clamps at the bottom", degree_to_midi(0, "Major", -40, transpose=-999) == 0)

# -- notes: the growing pool only ever extends outward, seeds at the root,
# and never revisits/removes a degree on its own -----------------------
check("empty pool seeds at the root going up", next_degree_to_add(set(), 1) == 0)
check("empty pool seeds at the root going down", next_degree_to_add(set(), -1) == 0)
pool = set()
for _ in range(5):
    pool.add(next_degree_to_add(pool, 1))
check("growing up 5 times reaches degree 4", pool == {0, 1, 2, 3, 4})
pool = set()
for _ in range(5):
    pool.add(next_degree_to_add(pool, -1))
check("growing down 5 times reaches degree -4", pool == {0, -1, -2, -3, -4})
pool = {0, 1, 2}
check("growing up from {0,1,2} adds 3, not a duplicate", next_degree_to_add(pool, 1) == 3)
check("growing down from {0,1,2} adds -1, not a duplicate", next_degree_to_add(pool, -1) == -1)

# -- arp: tap-tempo interval math -------------------------------------------
check("bpm_from_tap_interval(0.5s) == 120", bpm_from_tap_interval(0.5) == 120.0)
check("bpm_from_tap_interval(1.0s) == 60", bpm_from_tap_interval(1.0) == 60.0)
check("bpm_from_tap_interval clamps absurdly fast taps", bpm_from_tap_interval(0.01) == 300)
check("bpm_from_tap_interval clamps absurdly slow taps", bpm_from_tap_interval(10.0) == 20)
check("bpm_from_tap_interval(0) is None (no divide-by-zero)", bpm_from_tap_interval(0) is None)
check("step_interval_s(120bpm, 2 steps/beat) == 0.25s", step_interval_s(120, 2) == 0.25)

# -- arp: next_up_index cycles through however many notes are active right
# now, and never raises even if the pool shrank between steps --------------
check("next_up_index wraps at the end", next_up_index(2, 3) == 0)
check("next_up_index advances by one", next_up_index(0, 3) == 1)
check("next_up_index handles length 0 without raising", next_up_index(5, 0) == 0)
idx = -1
seen = []
for _ in range(6):
    idx = next_up_index(idx, 3)
    seen.append(idx)
check("next_up_index cycles 0,1,2,0,1,2 from -1", seen == [0, 1, 2, 0, 1, 2])

# -- params: exactly 9 of them, one per manipulation key --------------------
check("exactly 9 params", len(PARAMS) == 9)
check("unique CC numbers among cc-kind params", len({p.cc for p in PARAMS if p.kind == "cc"}) == sum(1 for p in PARAMS if p.kind == "cc"))

# -- params: normalized() always in [0, 1] and step_value() always clamps --
for p in PARAMS:
    check(f"{p.name} default is in range", p.minv <= p.default <= p.maxv)
    check(f"{p.name} normalized(default) in [0,1]", 0.0 <= normalized(p, p.default) <= 1.0)
    check(f"{p.name} normalized(min)==0", normalized(p, p.minv) == 0.0)
    check(f"{p.name} normalized(max)==1", normalized(p, p.maxv) == 1.0)
    check(
        f"{p.name} step_value clamps at max",
        step_value(p, p.maxv, 999) == p.maxv,
    )
    check(
        f"{p.name} step_value clamps at min",
        step_value(p, p.minv, -999) == p.minv,
    )

check("clamp() basic sanity", clamp(5, 0, 10) == 5 and clamp(-1, 0, 10) == 0 and clamp(11, 0, 10) == 10)

# -- params: half a turn from the centered default should land within 10%
# of an extreme, and a full turn should reach it outright (the requested
# "hold and twist" responsiveness fix - previously MOD WHEEL needed ~3.5
# turns for the full range). ~18 encoder counts/turn measured on this
# board, so half a turn is ~9 counts. TRANSPOSE is deliberately excluded -
# it keeps 1-semitone-precise stepping instead of a fast sweep.
HALF_TURN_DETENTS = 9
FULL_TURN_DETENTS = HALF_TURN_DETENTS * 2
for p in PARAMS:
    if p.kind == "transpose":
        continue
    span = p.maxv - p.minv
    tolerance = span * 0.1
    lo_half = step_value(p, p.default, -HALF_TURN_DETENTS)
    hi_half = step_value(p, p.default, HALF_TURN_DETENTS)
    check(f"{p.name}: half turn down nears the bottom", lo_half - p.minv <= tolerance)
    check(f"{p.name}: half turn up nears the top", p.maxv - hi_half <= tolerance)
    check(f"{p.name}: full turn down reaches the bottom", step_value(p, p.default, -FULL_TURN_DETENTS) == p.minv)
    check(f"{p.name}: full turn up reaches the top", step_value(p, p.default, FULL_TURN_DETENTS) == p.maxv)

if failures:
    print(f"\n{len(failures)} check(s) failed")
    sys.exit(1)
print("All checks passed")
