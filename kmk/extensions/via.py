from digitalio import DigitalInOut, Direction
import countio
from microcontroller import Pin
import bitbangio

from kmk.extensions import Extension
from kmk.keys import Key
from kmk.ascii import AsciiKeyMap


"""
        ____________________     _____
RDY ___|                    |___|       high indicates key ready, falling edge on shift complete
    _______       ________
CS         |____//                      falling edge requests shift out (zero if not RDY)
                ___
SDA ___________|   |___ ...             keyboard drives data out and clock
               _   _
SCL __________| |_| |_| ...             mode 0 samples in on rising edge (n/a), shifted out on falling edge

BITC-Pro expansion connector pins (see https://nullbits.co/static/img/bitc_pro_pinout.png)

  ** Note input lines need 3.3/5V voltage bridge

  Wire    Cnxn      GPIO  SPI   UART  I2C   PWM  countio?

  Blue    I-CS       11   TX1   RTS1  SCL1  5B   ok  - note 3.3V input, use resistor bridge
  Purple  O-RDY      12   RX1   TX0   SDA0  6A
  Grey    O-SDA      13   CSn1  RX0   SCL0  6B   ok
  White   O-SCL      14   SCK1  CTS0  SDA1  7A
  Black   GND        GND
  Brown   n/c        VCC (3.3V)
  Red     5V         RAW (5V)

(1) this is not the same as the 4-pin breakout in various
places on the BITC-PRO board which has VCC, GND, SDA0 (D4), SCL0 (D5)
Unfortunately D4/D5 are already mapped in the matrix
(2) On RP2040, countio.Counter uses the PWM peripheral, and is limited
to PWM channel B pins due to hardware restrictions
"""

class VIAShifter(Extension):
    def __init__(self, CS_: Pin, RDY: Pin, SDA: Pin, SCL: Pin, debug=False):
        self.debug = debug

        # remember pins but can't setup/drive SPI until requested
        self.spi_pins = dict(clock=SCL, MISO=None, MOSI=SDA)

        self.buffer = bytearray()       # buffer of ascii keys
        self._pressed: set[Key] = set() # current keys pressed

        self.cs_fall_count = countio.Counter(CS_, edge = countio.Edge.FALL)

        self.RDY = DigitalInOut(RDY)      # True flags key ready
        self.RDY.direction = Direction.OUTPUT
        self.RDY.value = False

        # generate a mapping from KMK Key objects to ascii codes
        self.keymap = AsciiKeyMap(debug)

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
            v = self.keymap.convert(key, self._pressed)
            if v is not None:
                self.buffer.append(v)
                if self.debug:
                    print(f"key buffer: {self.buffer}")

        if self.buffer:
            self.RDY.value = True   # flag key ready to CPU, generating a rising edge

        # if requested send one key per scan cycle
        if self.cs_fall_count.count:
            self.cs_fall_count.reset()

            # drive SPI channel to report a key, releasing pins to float afterwards
            with bitbangio.SPI(**self.spi_pins) as spi:
                if not spi.try_lock():
                    print("Failed to acquire SPI lock")
                # drive CB1 clock as SPI mode 2 since it's inverted
                # the ~1us delay shouldn't matter
                spi.configure(baudrate=100000, polarity=1, phase=0, bits=8)
                if not self.buffer:
                    # send a zero if buffer is empty
                    self.buffer.append(0)
                spi.write(self.buffer, end=1)
                self.buffer = self.buffer[1:]

            self.RDY.value = False      # generate a falling edge

    def on_powersave_enable(self, keyboard):
        return

    def on_powersave_disable(self, keyboard):
        return

    def deinit(self, keyboard):
        return
