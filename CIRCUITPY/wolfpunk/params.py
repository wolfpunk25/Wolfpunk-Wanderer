# The 9 sound-manipulation parameters behind keys 3-11 (rows 2-4, left to
# right, top to bottom). General-purpose CC choices so this works against
# any synth, not just the Volca FM the CC ideas were partly drawn from.
#
# kind is one of:
#   "cc"        - a plain MIDI Control Change, cc holds the controller number
#   "pitchbend" - the dedicated Pitch Bend message, not a CC at all
#   "transpose" - not sent over MIDI at all; shifts the note bank locally
#                 (see notes.bank_notes' transpose argument)


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
    Param("MOD WHEEL",      "cc",        1,  0,     127,   0,   2,   (0, 150, 255)),
    Param("FILTER CUTOFF",  "cc",        74, 0,     127,   64,  2,   (255, 120, 0)),
    Param("RESONANCE",      "cc",        71, 0,     127,   0,   2,   (255, 0, 150)),
    Param("ATTACK",         "cc",        73, 0,     127,   0,   2,   (0, 255, 100)),
    Param("RELEASE",        "cc",        72, 0,     127,   20,  2,   (100, 255, 0)),
    Param("PORTAMENTO",     "cc",        5,  0,     127,   0,   2,   (150, 0, 255)),
    Param("PITCH BEND",     "pitchbend", None, -8192, 8191, 0,   256, (255, 255, 0)),
    Param("TRANSPOSE",      "transpose", None, -24,  24,   0,   1,   (255, 255, 255)),
    Param("REVERB SEND",    "cc",        91, 0,     127,   0,   2,   (0, 200, 200)),
]


def normalized(param, value):
    """0.0-1.0 position of value within the param's range, for LED brightness."""
    span = param.maxv - param.minv
    if span == 0:
        return 1.0
    return clamp((value - param.minv) / span, 0.0, 1.0)


def step_value(param, value, delta):
    return int(clamp(value + delta * param.step, param.minv, param.maxv))
