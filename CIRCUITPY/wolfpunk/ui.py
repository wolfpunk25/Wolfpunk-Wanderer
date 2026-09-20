# OLED (128x64) and NeoPixel rendering. code.py works out what everything
# should say/show; this just draws it.

import displayio
import terminalio
from adafruit_display_text import label

from wolfpunk.scales import NOTE_NAMES
from wolfpunk.params import normalized

# key layout on the 3x4 grid (row-major, keys 0-11)
NOTE_KEYS = (0, 1, 2)          # top row - note toggles
MANIP_KEYS = tuple(range(3, 12))  # rows 2-4 - sound manipulation

_DEGREE_HUE_STEP = 255 // 7


def _wheel(pos):
    pos = pos % 255
    if pos < 85:
        return (255 - pos * 3, pos * 3, 0)
    if pos < 170:
        pos -= 85
        return (0, 255 - pos * 3, pos * 3)
    pos -= 170
    return (pos * 3, 0, 255 - pos * 3)


def _scale_rgb(rgb, factor):
    return tuple(int(c * factor) for c in rgb)


def note_name(midi_note):
    return f"{NOTE_NAMES[midi_note % 12]}{midi_note // 12 - 1}"


def degree_color(degree):
    return _wheel((degree % 7) * _DEGREE_HUE_STEP)


class UI:
    def __init__(self, macropad):
        self.macropad = macropad
        macropad.pixels.brightness = 0.25

        self.group = displayio.Group()
        self.line1 = label.Label(terminalio.FONT, text="", color=0xFFFFFF, x=2, y=6)
        self.line2 = label.Label(terminalio.FONT, text="", color=0xFFFFFF, x=2, y=30)
        self.line3 = label.Label(terminalio.FONT, text="", color=0xFFFFFF, x=2, y=58)
        for l in (self.line1, self.line2, self.line3):
            self.group.append(l)

        # a value bar for whichever manip param is currently held
        self.bar_bitmap = displayio.Bitmap(124, 10, 2)
        self.bar_palette = displayio.Palette(2)
        self.bar_palette[0] = 0x000000
        self.bar_palette[1] = 0xFFFFFF
        self.bar_tile = displayio.TileGrid(
            self.bar_bitmap, pixel_shader=self.bar_palette, x=2, y=42
        )
        self.group.append(self.bar_tile)

        macropad.display.root_group = self.group

    def _draw_bar(self, fraction):
        bmp = self.bar_bitmap
        filled = int(fraction * bmp.width)
        for x in range(bmp.width):
            for y in range(bmp.height):
                border = y == 0 or y == bmp.height - 1
                bmp[x, y] = 1 if (border or x < filled) else 0

    def render_idle(self, root_name, scale_name, bank_note_names, latched, channel, flash=""):
        self.line1.text = f"{root_name} {scale_name}"[:21]
        notes_text = " ".join(
            f"*{n}*" if on else n for n, on in zip(bank_note_names, latched)
        )
        self.line2.text = notes_text[:21]
        self.line3.text = (flash if flash else f"ch{channel}")[:21]
        self._draw_bar(0.0)
        self.bar_tile.hidden = True

    def render_param(self, param, value):
        self.line1.text = param.name[:21]
        if param.kind in ("pitchbend", "transpose"):
            self.line2.text = f"{value:+d}"
        else:
            self.line2.text = f"{value}"
        self.line3.text = f"CC{param.cc}" if param.kind == "cc" else param.kind
        self.bar_tile.hidden = False
        self._draw_bar(normalized(param, value))

    def leds(self, bank_colors, latched, values, held_manip_idx, flash=False):
        px = self.macropad.pixels
        if flash:
            for i in range(12):
                px[i] = (255, 255, 255)
            px.show()
            return

        for i, key in enumerate(NOTE_KEYS):
            base = bank_colors[i]
            px[key] = base if latched[i] else _scale_rgb(base, 0.12)

        for i, key in enumerate(MANIP_KEYS):
            param, value = values[i]
            frac = normalized(param, value)
            brightness = 0.15 + 0.85 * frac
            color = _scale_rgb(param.color, brightness)
            if held_manip_idx == i:
                color = param.color  # full brightness while actively being adjusted
            px[key] = color

        px.show()
