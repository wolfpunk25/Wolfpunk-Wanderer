# The note pool: a set of scale degrees that only grows (via the encoder
# or keys 0-2) until something explicitly empties it (a key toggling its
# own degree off, or a long-press clear). Replaces an earlier sliding
# "3-note window" design that swapped notes out from under a held chord
# every time the encoder turned - see README.md's Design choices.

from wolfpunk.scales import midi_note

KEY_DEGREES = (0, 1, 2)  # fixed scale degrees keys 0, 1, 2 each toggle


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def degree_to_midi(root_index, scale_name, degree, transpose=0):
    n = midi_note(root_index, scale_name, degree) + transpose
    return int(clamp(n, 0, 127))


def next_degree_to_add(active_degrees, direction):
    """Which degree the encoder should add next, growing the pool
    outward: right extends above the current highest note, left extends
    below the current lowest. An empty pool seeds at the root (degree 0)
    regardless of direction, so there's always a predictable starting
    point."""
    if not active_degrees:
        return 0
    if direction > 0:
        return max(active_degrees) + 1
    return min(active_degrees) - 1
