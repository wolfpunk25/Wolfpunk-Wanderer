# The auto-arpeggiator: once notes are active they always cycle one at a
# time rather than sounding together as a held chord. Step selection is
# pure and host-testable; ArpClock's due() uses time.monotonic() and is
# only meaningfully exercised on hardware.

import time


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def bpm_from_tap_interval(interval_s):
    """Tap-tempo: BPM from the seconds between two taps of the encoder."""
    if interval_s <= 0:
        return None
    return clamp(60.0 / interval_s, 20, 300)


def step_interval_s(bpm, steps_per_beat):
    return 60.0 / bpm / steps_per_beat


def next_up_index(index, length):
    """"up" pattern: cycle ascending through however many notes are
    active right now. `length` can change between calls (notes added or
    cleared between steps) without this ever raising."""
    if length <= 0:
        return 0
    return (index + 1) % length


class ArpClock:
    def __init__(self, bpm=120, steps_per_beat=2):
        self.bpm = bpm
        self.steps_per_beat = steps_per_beat
        self._interval = step_interval_s(bpm, steps_per_beat)
        self._next_at = time.monotonic()

    def set_bpm(self, bpm):
        self.bpm = clamp(bpm, 20, 300)
        self._interval = step_interval_s(self.bpm, self.steps_per_beat)

    def due(self):
        now = time.monotonic()
        if now < self._next_at:
            return False
        self._next_at += self._interval
        if self._next_at < now:  # fell far behind (e.g. a long stall) - resync
            self._next_at = now + self._interval
        return True
