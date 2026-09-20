# Wolfpunk Wanderer - a MIDI CC/note manipulator for the Adafruit MacroPad
# RP2040. Top row (keys 0-2) toggles three notes on/off, a sliding window
# over the current scale; the encoder slides that window, or (held) cycles
# the scale; rows 2-4 (keys 3-11) each own one sound-shaping MIDI parameter,
# held and twisted to adjust it live. See README.md for the full control
# reference.

import time
from adafruit_macropad import MacroPad
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
from adafruit_midi.control_change import ControlChange
from adafruit_midi.pitch_bend import PitchBend

from wolfpunk.scales import SCALE_NAMES, NOTE_NAMES
from wolfpunk.notes import bank_notes, clamp_bank_offset
from wolfpunk.params import PARAMS, step_value
import wolfpunk.ui as ui_mod

CHANNEL = 1          # MIDI channel 1
VELOCITY = 100
ALL_NOTES_OFF_CC = 123
ENCODER_LONG_PRESS_S = 5.0  # panic threshold
FLASH_S = 0.35


class App:
    def __init__(self):
        self.macropad = MacroPad(midi_out_channel=CHANNEL)
        self.midi = self.macropad.midi
        self.ui = ui_mod.UI(self.macropad)

        self.root_index = 0  # fixed at C - use TRANSPOSE to repitch
        self.scale_index = 0
        self.bank_offset = 0
        self.transpose = 0

        self.latched = [False, False, False]
        self.sounding_note = [None, None, None]

        self.param_values = [p.default for p in PARAMS]
        self.active_manip = None      # index 0-8 of the key currently owning the encoder
        self.manip_rotated = False    # did a twist happen while active_manip was held?

        self.encoder_switch_held = False
        self.encoder_down_at = None
        self.encoder_rotated_during_hold = False
        self.panic_fired = False

        self._flash_text = ""
        self._flash_until = 0.0
        self._last_render = 0.0

        self._startup_chime()

    # -- startup ------------------------------------------------------
    def _startup_chime(self):
        self.macropad.play_tone(660, 0.07)
        self.macropad.play_tone(330, 0.14)

    # -- MIDI helpers ---------------------------------------------------
    def _send_param(self, param, value):
        if param.kind == "cc":
            self.midi.send(ControlChange(param.cc, value))
        elif param.kind == "pitchbend":
            self.midi.send(PitchBend(value + 8192))
        # "transpose" sends nothing - it's a local note-bank shift only

    def _release_all_notes(self):
        for i in range(3):
            if self.latched[i]:
                self.midi.send(NoteOff(self.sounding_note[i], 0))
                self.latched[i] = False
                self.sounding_note[i] = None

    def _panic(self):
        self._release_all_notes()
        self.midi.send(ControlChange(ALL_NOTES_OFF_CC, 0))
        self._flash("ALL NOTES OFF")

    # -- note keys (0-2) --------------------------------------------------
    def _toggle_note(self, i):
        if self.latched[i]:
            self.midi.send(NoteOff(self.sounding_note[i], 0))
            self.latched[i] = False
            self.sounding_note[i] = None
            return
        notes = self._current_bank()
        note = notes[i]
        self.midi.send(NoteOn(note, VELOCITY))
        self.latched[i] = True
        self.sounding_note[i] = note

    def _current_bank(self):
        scale_name = SCALE_NAMES[self.scale_index]
        return bank_notes(self.root_index, scale_name, self.bank_offset, self.transpose)

    # -- manipulation keys (3-11) -----------------------------------------
    def _manip_key_down(self, idx):
        if self.active_manip is None:
            self.active_manip = idx
            self.manip_rotated = False

    def _manip_key_up(self, idx):
        if idx != self.active_manip:
            return
        if not self.manip_rotated:
            self._reset_param(idx)
        self.active_manip = None
        self.manip_rotated = False

    def _apply_param_value(self, idx, value):
        """Set param idx's value and either mirror it locally (TRANSPOSE)
        or send it out over MIDI - the one place both the reset and the
        live-adjust paths route through, so they can't drift apart."""
        param = PARAMS[idx]
        self.param_values[idx] = value
        if param.kind == "transpose":
            self.transpose = value
        else:
            self._send_param(param, value)

    def _reset_param(self, idx):
        param = PARAMS[idx]
        self._apply_param_value(idx, param.default)
        self._flash(f"{param.name} RESET")

    def _adjust_manip(self, idx, delta):
        param = PARAMS[idx]
        value = self.param_values[idx]
        new_value = step_value(param, value, delta)
        if new_value == value:
            return
        self._apply_param_value(idx, new_value)

    # -- key events -------------------------------------------------------
    def handle_key(self, key_number, pressed):
        if key_number in ui_mod.NOTE_KEYS:
            if pressed:
                self._toggle_note(key_number)
            return
        idx = key_number - 3
        if pressed:
            self._manip_key_down(idx)
        else:
            self._manip_key_up(idx)

    # -- encoder ------------------------------------------------------
    def handle_encoder(self, delta):
        if delta == 0:
            return
        if self.active_manip is not None:
            self._adjust_manip(self.active_manip, delta)
            self.manip_rotated = True
            return
        if self.encoder_switch_held:
            self.scale_index = (self.scale_index + delta) % len(SCALE_NAMES)
            self.encoder_rotated_during_hold = True
            self._flash(SCALE_NAMES[self.scale_index])
            return
        # plain rotate: slide the note bank. Always release whatever's
        # latched first - otherwise a held note could go stale (still
        # sounding a note number that's no longer under any key).
        self._release_all_notes()
        self.bank_offset = clamp_bank_offset(self.bank_offset + delta)

    def handle_encoder_switch_down(self):
        self.encoder_switch_held = True
        self.encoder_down_at = time.monotonic()
        self.encoder_rotated_during_hold = False
        self.panic_fired = False

    def handle_encoder_switch_up(self):
        self.encoder_switch_held = False
        if not self.panic_fired and not self.encoder_rotated_during_hold:
            self._release_all_notes()
            self.bank_offset = 0
            self._flash("BANK RESET")
        self.encoder_down_at = None

    # -- display ----------------------------------------------------
    def _flash(self, text):
        self._flash_text = text
        self._flash_until = time.monotonic() + FLASH_S

    def _render(self):
        flashing = time.monotonic() < self._flash_until
        flash_text = self._flash_text if flashing else ""

        if self.active_manip is not None:
            param = PARAMS[self.active_manip]
            value = self.param_values[self.active_manip]
            self.ui.render_param(param, value)
        else:
            root_name = NOTE_NAMES[self.root_index]
            scale_name = SCALE_NAMES[self.scale_index]
            bank = self._current_bank()
            names = [ui_mod.note_name(n) for n in bank]
            self.ui.render_idle(root_name, scale_name, names, self.latched, CHANNEL, flash_text)

        bank_colors = [ui_mod.degree_color(self.bank_offset + i) for i in range(3)]
        values = [(PARAMS[i], self.param_values[i]) for i in range(9)]
        self.ui.leds(bank_colors, self.latched, values, self.active_manip, flash=flashing)

    # -- main loop --------------------------------------------------
    def run(self):
        macropad = self.macropad
        prev_encoder = macropad.encoder

        while True:
            while True:
                event = macropad.keys.events.get()
                if event is None:
                    break
                self.handle_key(event.key_number, event.pressed)

            enc = macropad.encoder
            if enc != prev_encoder:
                self.handle_encoder(enc - prev_encoder)
                prev_encoder = enc

            macropad.encoder_switch_debounced.update()
            if macropad.encoder_switch_debounced.pressed:
                self.handle_encoder_switch_down()
            if macropad.encoder_switch_debounced.released:
                self.handle_encoder_switch_up()

            if self.encoder_switch_held and not self.panic_fired:
                if time.monotonic() - self.encoder_down_at >= ENCODER_LONG_PRESS_S:
                    self._panic()
                    self.panic_fired = True

            now = time.monotonic()
            if now - self._last_render > 0.05:
                self._last_render = now
                self._render()


App().run()
