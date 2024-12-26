from kmk.keys import Key, KC, ModifiedKey, ModifierKey, KeyboardKey


# modifier codes form a bitmask (msb) rrrr llll (lsb)
# with each nibble representing CMD/WIN, ALT/OPT, SFT, CTL on rhs (hi) or lhs (lo)
MOD_CTL = 0x11
MOD_SFT = 0x22
MOD_ALT = 0x44
MOD_CMD = 0x88


class AsciiKeyMap:
    def __init__(self, debug=False):
        """Collect a mapping from tuples of (KeyboardKey code and shift state) to ascii codes"""
        self._keymap: dict[tuple[int, bool], int] = {}
        self.debug = debug

        for i in range(32, 127):
            c = chr(i)
            key = KC.get(c)
            if not key:
                if debug:
                    print(f"VIAShifter: No key for chr({i})={c}!")
            else:
                self.add(key, i)

        numpad = {
            '/': 'SLASH',
            '*': 'ASTERISK',
            '-': 'MINUS',
            '+': 'PLUS',
            '\r': 'ENTER',
            '.': 'DOT',
            '=': 'EQUAL',
            ',': 'COMMA',
        }

        for c in list(numpad.keys()) + list('0123456789'):
            key = KC.get('NUMPAD_' + numpad.get(c, c))
            self.add(key, ord(c))

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
            self.add(key, ascii)

        if self.debug:
            print(self._keymap)

    def add(self, key: KeyboardKey | ModifiedKey, ascii: int):
        """
        Shift is complicated since it can modify how a key code is interpreted:
        e.g. code 31 is ascii '2' but the same key code produces '@' when shifted.
        But it can also

        Each KeyboardKey.code maps to a tuple of unshifted and shifted ascii values
        We initially map a key code to the same ascii value for both states
        since sometimes shift doesn't matter.

        >>> KC.get('@')
        ModifiedKey(key=KeyboardKey(code=31), modifier=ModifierKey(code=2))
        >>> KC.get('2')
        KeyboardKey(code=31)

        """
        # each key code maps to a tuple of unshifted and shifted instance
        code = key.code if isinstance(key, KeyboardKey) else key.key.code
        shift = False if isinstance(key, KeyboardKey) else bool(key.modifier.code & MOD_SFT)

        self._keymap[(code, shift)] = ascii

    def convert(self, key: Key, pressed: set[Key]) -> int | None:
        modifiers = 0

        if isinstance(key, ModifiedKey):
            modifiers = key.modifier.code
            key = key.key

        if not isinstance(key, KeyboardKey):
            return

        for k in pressed:
            if k != key and isinstance(k, ModifierKey):
                modifiers |= k.code

        shift = bool(modifiers & MOD_SFT)

        v = self._keymap.get((key.code, shift)) or self._keymap.get((key.code, not shift))
        if not v:
            if self.debug:
                print(f"AsciiKeyMap: no ascii mapping for {key} with modifiers {modifiers} from {pressed}")
            return

        # control clamps to 0-31
        if modifiers & MOD_CTL:
            v &= 0x1f

        # cmd or alt sets high bit
        if modifiers & (MOD_CMD | MOD_ALT):
            v |= 0x80

        if self.debug:
            print(f"AsciiKeyMap: mapped {key} with modifiers {modifiers} from {pressed} => ${v:02x} '{chr(v)}'")

        return v

