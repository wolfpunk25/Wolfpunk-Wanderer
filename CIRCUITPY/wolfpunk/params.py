# The 9 sound-manipulation parameters behind keys 3-11 (rows 2-4, left to
# right, top to bottom). General-purpose CC choices so this works against
# any synth, not just the Volca FM the CC ideas were partly drawn from.
#
# kind is one of:
#   "cc"        - a plain MIDI Control Change, cc holds the controller number
#   "pitchbend" - the dedicated Pitch Bend message, not a CC at all
#   "transpose" - not sent over MIDI at all; shifts the note bank locally
#                 (see notes.bank_notes' transpose argument)
#
# `step` is tuned so a full turn of this board's encoder covers roughly the
# whole range - measured empirically (MOD WHEEL at the old step of 2 took
# ~3.5 turns bottom to top, i.e. ~18 encoder counts/turn), not read off a
# datasheet. `default` is the centre of the range wherever "centre" makes
# sense, so turning either direction from boot has room to move, and a half
# turn from the default lands near an extreme. TRANSPOSE is the one
# exception left at 1 semitone/detent - it's a discrete musical value, not
# a continuous CC, and 3+ semitone jumps would skip notes you'd want to
# land on exactly.


class Param:
    def __init__(self, name, kind, cc, minv, maxv, default, step, color):
        self.name = name
        self.kind = kind
        self.cc = cc
        self.minv = minv
        self.maxv = maxv
        self.default = default
        self.step = step
        self.color = color  # (r, g, b) at the parameter's max value


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


PARAMS = [
    Param("MOD WHEEL",      "cc",        1,  0,     127,   64,  7,   (0, 150, 255)),
    Param("FILTER CUTOFF",  "cc",        74, 0,     127,   64,  7,   (255, 120, 0)),
    Param("RESONANCE",      "cc",        71, 0,     127,   64,  7,   (255, 0, 150)),
    Param("ATTACK",         "cc",        73, 0,     127,   64,  7,   (0, 255, 100)),
    Param("RELEASE",        "cc",        72, 0,     127,   64,  7,   (100, 255, 0)),
    Param("PORTAMENTO",     "cc",        5,  0,     127,   64,  7,   (150, 0, 255)),
    Param("PITCH BEND",     "pitchbend", None, -8192, 8191, 0,   896, (255, 255, 0)),
    Param("TRANSPOSE",      "transpose", None, -24,  24,   0,   1,   (255, 255, 255)),
    Param("REVERB SEND",    "cc",        91, 0,     127,   64,  7,   (0, 200, 200)),
]


def normalized(param, value):
    """0.0-1.0 position of value within the param's range, for LED brightness."""
    span = param.maxv - param.minv
    if span == 0:
        return 1.0
    return clamp((value - param.minv) / span, 0.0, 1.0)


def step_value(param, value, delta):
    return int(clamp(value + delta * param.step, param.minv, param.maxv))
