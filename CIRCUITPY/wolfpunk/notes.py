# The sliding "note bank" behind the top-row keys: keys 0-2 always sound
# three *consecutive* scale degrees, and the encoder slides that window of
# three up or down the scale (a "bank" isn't a jump to an unrelated triad,
# it's the same three-note window moving by one degree at a time).

from wolfpunk.scales import midi_note

BANK_MIN = -14  # two octaves below the root's degree
BANK_MAX = 14   # two octaves above


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def clamp_bank_offset(offset):
    return clamp(offset, BANK_MIN, BANK_MAX)


def bank_notes(root_index, scale_name, bank_offset, transpose=0):
    """The 3 MIDI notes currently under keys 0, 1, 2."""
    notes = []
    for i in range(3):
        n = midi_note(root_index, scale_name, bank_offset + i) + transpose
        notes.append(int(clamp(n, 0, 127)))
    return notes
