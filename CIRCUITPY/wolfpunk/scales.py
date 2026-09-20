# Seven-degree scales, adapted from the Wolfpunk Possibility sister project
# (same board, same MacroPad key-color wheel) - `midi_note()`'s degree-wrap/
# octave-carry handles negative degrees too (Python's `%`/`//` are
# floor-based), which is exactly what a sliding note-bank window needs.
#
# Every scale here must have 7 genuinely distinct, strictly-ascending
# offsets (checked in tests/test_logic.py). Possibility's WholeTone table
# padded a fundamentally 6-note scale out to 7 slots by repeating the
# octave (offset 12 == offset 0 of the next octave) - harmless there since
# it only ever picks non-adjacent triad degrees, but a sliding 3-note
# window straddling that seam produced two identical notes. Swapped for
# Harmonic Minor, which has 7 real degrees.

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SCALES = {
    "Major":          [0, 2, 4, 5, 7, 9, 11],
    "Minor":          [0, 2, 3, 5, 7, 8, 10],
    "Dorian":         [0, 2, 3, 5, 7, 9, 10],
    "Byzantine":      [0, 1, 4, 5, 7, 8, 10],  # Phrygian dominant
    "Lydian":         [0, 2, 4, 6, 7, 9, 11],
    "Mixolydian":     [0, 2, 4, 5, 7, 9, 10],
    "HarmonicMinor":  [0, 2, 3, 5, 7, 8, 11],
}

SCALE_NAMES = list(SCALES.keys())

BASE_MIDI = 48  # C3 - root note when ROOT index is 0 (C) and octave offset is 0


def midi_note(root_index, scale_name, degree, octave=0):
    offsets = SCALES[scale_name]
    degree_wrapped = degree % 7
    octave_carry = degree // 7  # degree can run past 6 (or negative) and carries into the octave
    offset = offsets[degree_wrapped]
    return BASE_MIDI + root_index + offset + 12 * (octave + octave_carry)
