#!/usr/bin/env python3
"""Host-side tests for the pure-Python core (scales/notes/params) - no
board needed. Run before ever flashing, same pattern as Wolfpunk
Possibility: catch logic bugs in plain python3, save the hardware loop for
what can only be verified live."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "CIRCUITPY"))

from wolfpunk.scales import SCALE_NAMES, midi_note
from wolfpunk.notes import bank_notes, clamp_bank_offset, BANK_MIN, BANK_MAX
from wolfpunk.params import PARAMS, normalized, step_value, clamp

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

# -- notes: a sliding bank window always yields 3 ascending-or-equal notes -
for name in SCALE_NAMES:
    for offset in range(BANK_MIN, BANK_MAX - 1):
        notes = bank_notes(0, name, offset)
        check(
            f"{name} bank@{offset} strictly ascending",
            notes[0] < notes[1] < notes[2],
        )

# -- notes: bank window never leaves the 0-127 MIDI range ------------------
for name in SCALE_NAMES:
    for offset in (BANK_MIN, BANK_MAX):
        for n in bank_notes(0, name, offset):
            check(f"{name} bank@{offset} note {n} in range", 0 <= n <= 127)

# -- notes: transpose shifts the whole window by exactly that many semitones
base = bank_notes(0, "Major", 0, transpose=0)
shifted = bank_notes(0, "Major", 0, transpose=5)
check(
    "transpose shifts all 3 notes by +5",
    all(s - b == 5 for b, s in zip(base, shifted)),
)

# -- notes: transpose clamps into range rather than wrapping/crashing ------
extreme = bank_notes(0, "Major", BANK_MAX, transpose=999)
check("transpose clamps at the top", all(n == 127 for n in extreme))
extreme = bank_notes(0, "Major", BANK_MIN, transpose=-999)
check("transpose clamps at the bottom", all(n == 0 for n in extreme))

# -- notes: bank offset clamp never escapes its own declared range ---------
check("bank offset clamps above", clamp_bank_offset(999) == BANK_MAX)
check("bank offset clamps below", clamp_bank_offset(-999) == BANK_MIN)

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

if failures:
    print(f"\n{len(failures)} check(s) failed")
    sys.exit(1)
print("All checks passed")
