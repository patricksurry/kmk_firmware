import digitalio
import microcontroller
from time import sleep

from kmk.extensions import Extension
from kmk.keys import Key, KC, FIRST_KMK_INTERNAL_KEY, ModifierKey

# BITC-Pro expansion connector pins (see https://nullbits.co/static/img/bitc_pro_pinout.png)
#
#   ** Note input lines need 3.3/5V voltage bridge
#
#   Wire    Cnxn      GPIO  SPI   UART  I2C   PWM  countio?
#
#   Blue    nc         11   TX1   RTS1  SCL1  5B   ok
#   Purple  O-RDY      12   RX1   TX0   SDA0  6A
#   Grey    O-SDA      13   CSn1  RX0   SCL0  6B   ok
#   White   O-SCL      14   SCK1  CTS0  SDA1  7A
#   Black   GND        GND
#   Brown   n/c        VCC (3.3V)
#   Red     5V         RAW (5V)

# (1) this is not the same as the 4-pin breakout in various
# places on the BITC-PRO board which has VCC, GND, SDA0 (D4), SCL0 (D5)
# Unfortunately D4/D5 are already mapped in the matrix

# (2) On RP2040, countio.Counter uses the PWM peripheral, and is limited
# to PWM channel B pins due to hardware restrictions

# modifier codes form a bitmask (msb) rrrr llll (lsb)
# with each nibble representing CMD/WIN, ALT/OPT, SFT, CTL on rhs (hi) or lhs (lo)
MOD_CTL = 0x11
MOD_SFT = 0x22
MOD_ALT = 0x44
MOD_CMD = 0x88


def isShifted(key: Key):
    return any(MOD_SFT & mod for mod in (key.has_modifiers or []))


class VIAShifter(Extension):
    def __init__(self):
        mcp = microcontroller.pin
        dio = digitalio.DigitalInOut

        self.RDY = dio(mcp.GPIO12)    # SR RCLK / handshake
        self.SDA = dio(mcp.GPIO13)    # SR serial data
        self.SCL = dio(mcp.GPIO14)    # SR shift clock

        for p in (self.RDY, self.SDA, self.SCL):
            p.direction = digitalio.Direction.OUTPUT
            p.value = False

        self._pressed: set[Key] = set()

        self.mapKeys()
        self.debugMorse('---   -.-')

    def mapKey(self, key: Key, ascii: int):
        # each key code maaps to a tuple of unshifted and shifted instance
        # e.g. code 31 is 2 but also (shifted) @
        # when we see a code for the first time, map it in both places
        # in case we don't care about shift status
        if key.code not in self.keymap:
            self.keymap[key.code] = (ascii, ascii)
        else:
            (_, _) = self.keymap[key.code]
            self.keymap[key.code] = (_, ascii) if isShifted(key) else (ascii, _)

    def mapKeys(self):
        """Map Key.code to non-shift/shift ascii bytes"""
        self.keymap: dict[int, tuple[int, int]] = {}

        for i in range(32, 127):
            c = chr(i)
            key = KC.get(c)
            if not key:
                print(f"VIAShifter: No key for chr({i})={c}!")
            else:
                self.mapKey(key, i)

        numpad = {
            '/': 'SLASH',
            '*': 'ASTERISK',
            '-': 'MINUS',
            '+': 'PLUS',
            '\r': 'ENTER',
            '.': 'DOT',
            '=': 'COMMA'
        }

        for c in list(numpad.keys()) + list('0123456789'):
            key = KC.get('NUMPAD_' + numpad.get(c, c))
            self.mapKey(key, ord(c))

        # some specials map to control characters
        for (key, ascii) in [
                (KC.BKSP,   0x08),
                (KC.TAB,    0x09),
                (KC.ENTER,  0x0D),
                (KC.ESC,    0x1B),
                (KC.DEL,    0x7F),

                # https://www.applefritter.com/content/how-diy-changing-apple-title
                (KC.LEFT,   0x08),    # CTRL-H
                (KC.DOWN,   0x0A),    # CTRL-J
                (KC.UP,     0x0B),    # CTRL-K
                (KC.RIGHT,  0x15),    # CTRL-U
            ]:
            self.mapKey(key, ascii)

    def sendKey(self, key: Key):
        if not hasattr(key, 'code') or key.code >= FIRST_KMK_INTERNAL_KEY or isinstance(key, ModifierKey):
            return

        # check all pressed keys for modifiers
        modifiers = 0
        for k in self._pressed:
            is_modifier = isinstance(k, ModifierKey)
            if k != key and not is_modifier:
                continue
            if k.has_modifiers:
                for mod in k.has_modifiers:
                    modifiers |= mod
            elif is_modifier and k.code != ModifierKey.FAKE_CODE:
                modifiers |= k.code

        vs = self.keymap.get(key.code)
        if not vs:
            print(f"VIAShifter: no ascii mapping for {key}")
            return

        print(f"VIAShifter: got mapping {vs}, {modifiers}, {modifiers & MOD_SFT}")

        # choose shifted or unshifted chr
        v = vs[1 if (modifiers & MOD_SFT) else 0]

        # control clamps to 0-31
        if modifiers & MOD_CTL:
            v &= 0x1f

        # cmd or alt sets high bit
        if modifiers & (MOD_CMD | MOD_ALT):
            v |= 0x80

        print(f"VIAShifter: sending {key}/{modifiers} as ${v:02x} '{chr(v)}'")
#        self.debugMorse('-')       # the sleep here limits throughput
        self.shiftByteOut(v)

    def shiftByteOut(self, v: int):
        # The '595 shift register shifts SDA in on SCLK rising edge
        # and latches data to register on RCLK (our 'ready' handshake)

        # write the byte from MSB -> LSB
        for _ in range(8):
            self.SDA.value = bool(v & 0x80)     # setup the MSB
            v <<= 1                             # shift for next bit
            self.SCL.value = True               # pulse external clock
            self.SCL.value = False              # stop our clock pulse

        self.SDA.value = False                  # clear SDA for LED debugging

        # pulse the handshake to latch data and handshake VIA (on falling/negative edge)
        self.RDY.value = True
        self.RDY.value = False

    def debugMorse(self, morse='---   -.-', dit=0.1):
        # flash data pin with morse chars '-', '.', ' '
        # note this isn't clocked so shouldn't be recognized as input
        # separate letters by one space leading to 3 dit better letters
        # separate words by three space leading to 7 dit between words
        p = self.SDA
        for c in morse:
            if c == ' ':
                p.value = False
                sleep(dit)            # 1 + 1 + 1 dit between letters
            else:
                p.value = True
                sleep(dit*(3 if c == '-' else 1))
                p.value = False
            sleep(dit)              # 1 dit between intra-letter dit/dah
        p.value = False

    # Extension overload

    def on_runtime_enable(self, keyboard):
        return

    def on_runtime_disable(self, keyboard):
        return

    def during_bootup(self, keyboard):
        # here we get the actual keyboard, not the sandbox
        self._kbd = keyboard

    def before_matrix_scan(self, keyboard):
        return

    def after_matrix_scan(self, keyboard):
        return

    def before_hid_send(self, keyboard):
        return

    def after_hid_send(self, keyboard):
        if len(self._kbd.keys_pressed) > len(self._pressed):
            key = list(self._kbd.keys_pressed - self._pressed)[0]
        else:
            key = None
        self._pressed = set(self._kbd.keys_pressed)
        if key:
            self.sendKey(key)

    def on_powersave_enable(self, keyboard):
        return

    def on_powersave_disable(self, keyboard):
        return

    def deinit(self, keyboard):
        return
