import digitalio
import microcontroller
import countio
from time import sleep, monotonic

from kmk.keys import Key, KC

# BITC-Pro expansion connector pins (see https://nullbits.co/static/img/bitc_pro_pinout.png)
#
#   ** Note input lines need 3.3/5V voltage bridge
#
#   Wire    Cnxn      GPIO  SPI   UART  I2C   PWM  countio?
#
#   Blue    * I-PHI2   11   TX1   RTS1  SCL1  5B   ok
#   Purple  * I-IRQ    12   RX1   TX0   SDA0  6A
#   Grey    O-SDA      13   CSn1  RX0   SCL0  6B   ok
#   White   O-SCL      14   SCK1  CTS0  SDA1  7A
#   Black   GND        GND
#   Brown   n/c        VCC (3.3V)
#   Red     5V         RAW (5V)

# (1) this is not the same as the 4-pin breakout in various
# places on the BITC-PRO board which has VCC, GND, SDA0 (D4), SCL0 (D5)
# Unfortunately D4/D5 are already mapped in the matrix

# (2) On RP2040, Counter uses the PWM peripheral, and is limited
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

        self.CLK = mcp.GPIO11
        self.IRQ = dio(mcp.GPIO12)
        self.SDA = dio(mcp.GPIO13)    # CB2 serial data
        self.SCL = dio(mcp.GPIO14)    # CB1 ext clock

        self.IRQ.direction = digitalio.Direction.INPUT
        self.IRQ.pull = digitalio.Pull.UP      # IRQB=LOW on interrupt

        self.SDA.direction = digitalio.Direction.OUTPUT
        self.SDA.value = False

        self.SCL.direction = digitalio.Direction.OUTPUT
        self.SCL.value = False

        self.mapKeys()
        self.checkClock()

    def checkClock(self):
        # check if clock is active
        start = monotonic()
        ticks = countio.Counter(self.CLK, edge=countio.Edge.FALL)
        self.debug_leds(slow=True)
        n = ticks.count
        elapsed = (monotonic() - start)

        ticks.deinit()
        self.active = elapsed > 1 and n > 3
        print(f"VIAShifter[active={self.active}]: saw {n} ticks in {elapsed}s")

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
        if not self.active or not hasattr(key, 'code'):
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
            self.debug_leds()
            self.shiftByteOut(v)
        else:
            print(f"VIAShifter: no ascii mapping for {key}")

    def shiftByteOut(self, v: int):
        # NB http://forum.6502.org/viewtopic.php?p=2310#p2310
        # If the edge on CB1 falls within a few nanoseconds of the falling edge of phase 2,
        # the CB1 edge will be ignored, so you lose a bit
        # so even tho 6502 clock cycle is measured on falling edge, we watch rising ones
        with countio.Counter(self.CLK, edge=countio.Edge.RISE) as phi:
            # write the byte from MSB -> LSB
            for _ in range(8):
                self.SDA.value = bool(v & 0x80)     # setup the MSB
                v <<= 1                             # shift for next bit
                phi.reset()
                while not phi.count:
                    continue
                self.SCL.value = True               # pulse external clock just after rising edge
                # need a full 6502 clock cycle (measured on falling edge) to ensure incoming bit latch
                phi.reset()
                while phi.count < 2:
                    pass
                self.SCL.value = False  # stop our clock pulse
        self.SDA.value = False  # not stricly needed but nicer for LED debugging

    def debug_leds(self, slow=False):
        if slow:
            for _ in range(3):
                for p in [self.SDA, self.SCL]:
                    p.value = True
                    sleep(0.2)
                    p.value = False

            for _ in range(3):
                self.SDA.value = True
                self.SCL.value = True
                sleep(0.2)
                self.SDA.value = False
                self.SCL.value = False
                sleep(0.2)
        else:
            self.SDA.value = True
            self.SCL.value = True
            sleep(0.1)
            self.SDA.value = False
            self.SCL.value = False

