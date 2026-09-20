# Wolfpunk Wanderer - a MIDI CC/note manipulator for the Adafruit MacroPad
# RP2040. Keys 0-2 each toggle one fixed scale degree in/out of a note
# pool; the encoder grows that pool further out (never swaps it out from
# under you); once 2+ notes are in the pool they auto-arpeggiate instead
# of holding as a static chord. Encoder held+twisted cycles the scale,
# double-clicked resets the 9 sound parameters, long-pressed clears the
# note pool. Rows 2-4 (keys 3-11) each own one sound-shaping MIDI
# parameter, held and twisted to adjust it live. See README.md for the
# full control reference.

import time
from adafruit_macropad import MacroPad
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
from adafruit_midi.control_change import ControlChange
from adafruit_midi.pitch_bend import PitchBend

from wolfpunk.scales import SCALE_NAMES, NOTE_NAMES
from wolfpunk.notes import KEY_DEGREES, degree_to_midi, next_degree_to_add
from wolfpunk.params import PARAMS, step_value
from wolfpunk.arp import ArpClock, bpm_from_tap_interval, next_up_index
import wolfpunk.ui as ui_mod

CHANNEL = 1          # MIDI channel 1
VELOCITY = 100
ALL_NOTES_OFF_CC = 123
LONG_PRESS_S = 0.8       # encoder held this long -> clear notes
DOUBLE_CLICK_S = 0.35    # two clicks within this -> reset settings
TAP_TEMPO_TIMEOUT_S = 2.0
FLASH_S = 0.35


class App:
    def __init__(self):
        self.macropad = MacroPad(midi_out_channel=CHANNEL)
        self.midi = self.macropad.midi
        self.ui = ui_mod.UI(self.macropad)

        self.root_index = 0  # fixed at C - use TRANSPOSE to repitch
        self.scale_index = 0
        self.transpose = 0

        self.active_degrees = set()   # the note pool - only grows until cleared
        self.arp_clock = ArpClock(bpm=120, steps_per_beat=2)
        self.arp_index = -1           # index last played, in sorted(active_degrees); -1 = none yet
        self.arp_sounding_note = None
        self.arp_playing_degree = None

        self.param_values = [p.default for p in PARAMS]
        self.active_manip = None      # index 0-8 of the key currently owning the encoder

        self.encoder_switch_held = False
        self.encoder_down_at = None
        self.encoder_rotated_during_hold = False
        self.long_press_fired = False
        self._last_click_at = None    # for double-click detection
        self._last_tap_at = None      # for tap-tempo interval measurement

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
        # "transpose" sends nothing - it's a local note-pool shift only

    def _degree_midi(self, degree):
        scale_name = SCALE_NAMES[self.scale_index]
        return degree_to_midi(self.root_index, scale_name, degree, self.transpose)

    # -- note pool (keys 0-2 + encoder) ------------------------------------
    def _toggle_degree_key(self, i):
        degree = KEY_DEGREES[i]
        if degree in self.active_degrees:
            self.active_degrees.discard(degree)
        else:
            self.active_degrees.add(degree)
        self._sync_arp_after_pool_change()

    def _grow_pool(self, direction):
        degree = next_degree_to_add(self.active_degrees, direction)
        self.active_degrees.add(degree)

    def _clear_notes(self):
        self.active_degrees.clear()
        self._sync_arp_after_pool_change()
        self.midi.send(ControlChange(ALL_NOTES_OFF_CC, 0))
        self._flash("NOTES CLEARED")

    def _sync_arp_after_pool_change(self):
        if not self.active_degrees and self.arp_sounding_note is not None:
            self.midi.send(NoteOff(self.arp_sounding_note, 0))
            self.arp_sounding_note = None
            self.arp_playing_degree = None
            self.arp_index = -1

    def _arp_step(self):
        if not self.active_degrees:
            return
        degrees_sorted = sorted(self.active_degrees)
        self.arp_index = next_up_index(self.arp_index, len(degrees_sorted))
        degree = degrees_sorted[self.arp_index]
        note = self._degree_midi(degree)
        if self.arp_sounding_note is not None:
            self.midi.send(NoteOff(self.arp_sounding_note, 0))
        self.midi.send(NoteOn(note, VELOCITY))
        self.arp_sounding_note = note
        self.arp_playing_degree = degree

    # -- manipulation keys (3-11) -----------------------------------------
    def _manip_key_down(self, idx):
        if self.active_manip is None:
            self.active_manip = idx

    def _manip_key_up(self, idx):
        if idx == self.active_manip:
            self.active_manip = None

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

    def _reset_all_params(self):
        for idx, param in enumerate(PARAMS):
            self._apply_param_value(idx, param.default)
        self._last_tap_at = None  # don't let this click's timestamp leak into tap-tempo
        self._flash("SETTINGS RESET")

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
                self._toggle_degree_key(key_number)
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
            return
        if self.encoder_switch_held:
            self.scale_index = (self.scale_index + delta) % len(SCALE_NAMES)
            self.encoder_rotated_during_hold = True
            self._flash(SCALE_NAMES[self.scale_index])
            return
        direction = 1 if delta > 0 else -1
        for _ in range(abs(delta)):
            self._grow_pool(direction)

    def _tap_tempo(self):
        now = time.monotonic()
        if self._last_tap_at is not None and (now - self._last_tap_at) < TAP_TEMPO_TIMEOUT_S:
            bpm = bpm_from_tap_interval(now - self._last_tap_at)
            if bpm is not None:
                self.arp_clock.set_bpm(bpm)
                self._flash(f"{int(self.arp_clock.bpm)} BPM")
        self._last_tap_at = now

    def handle_encoder_switch_down(self):
        self.encoder_switch_held = True
        self.encoder_down_at = time.monotonic()
        self.encoder_rotated_during_hold = False
        self.long_press_fired = False

    def handle_encoder_switch_up(self):
        self.encoder_switch_held = False
        if not self.encoder_rotated_during_hold and not self.long_press_fired:
            now = time.monotonic()
            if self._last_click_at is not None and (now - self._last_click_at) <= DOUBLE_CLICK_S:
                self._reset_all_params()
                self._last_click_at = None
            else:
                self._tap_tempo()
                self._last_click_at = now
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
            names = [ui_mod.note_name(self._degree_midi(d)) for d in sorted(self.active_degrees)]
            self.ui.render_idle(root_name, scale_name, names, self.arp_clock.bpm, CHANNEL, flash_text)

        key_active = [KEY_DEGREES[i] in self.active_degrees for i in range(3)]
        key_playing = [KEY_DEGREES[i] == self.arp_playing_degree for i in range(3)]
        values = [(PARAMS[i], self.param_values[i]) for i in range(9)]
        self.ui.leds(key_active, key_playing, values, self.active_manip, flash=flashing)

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

            if self.encoder_switch_held and not self.encoder_rotated_during_hold and not self.long_press_fired:
                if time.monotonic() - self.encoder_down_at >= LONG_PRESS_S:
                    self._clear_notes()
                    self.long_press_fired = True

            if self.active_degrees and self.arp_clock.due():
                self._arp_step()

            now = time.monotonic()
            if now - self._last_render > 0.05:
                self._last_render = now
                self._render()


App().run()
