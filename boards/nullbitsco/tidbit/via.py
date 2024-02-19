import digitalio
import microcontroller
from time import sleep

from kmk.keys import Key, KC

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

MOD_CTL = 0x11
MOD_SFT = 0x22
MOD_ALT = 0x33
MOD_CMD = 0x44


def modifierFlags(key: Key):
    """
    modifier codes form a bitmask (msb) rrrr llll (lsb)
    with each nibble representing CMD/WIN, ALT/OPT, SFT, CTL on rhs (hi) or lhs (lo)
    """
    flags = 0
    if key.has_modifiers:
        for mod in key.has_modifiers:
            flags |= mod
    return flags


def isShifted(key: Key):
    return 1 if (modifierFlags(key) & MOD_SFT) else 0


class VIAShifter:

    def __init__(self):
        mcp = microcontroller.pin
        dio = digitalio.DigitalInOut

        self.RDY = dio(mcp.GPIO12)    # SR RCLK / handshake
        self.SDA = dio(mcp.GPIO13)    # SR serial data
        self.SCL = dio(mcp.GPIO14)    # SR shift clock

        for p in (self.RDY, self.SDA, self.SCL):
            p.direction = digitalio.Direction.OUTPUT
            p.value = False

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
        if not hasattr(key, 'code'):
            return

        vs = self.keymap.get(key.code)

        if vs:
            v = vs[isShifted(key)]
            flags = modifierFlags(key)
            if (flags & MOD_CTL) and (v & 0b11000000 == 0b01000000):
                v &= 0x1F       # control key clamps to low 32 chrs
            if flags & (MOD_CMD | MOD_ALT):
                v |= 0x80       # cmd or alt sets high bit
            print(f"VIAShifter: sending {key} as ${v:02x} {chr(v)}")
            self.debugMorse('-')
            self.shiftByteOut(v)
        else:
            print(f"VIAShifter: no ascii mapping for {key}")

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
