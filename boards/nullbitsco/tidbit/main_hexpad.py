from kb import KMKKeyboard
from kmk.keys import KC, make_key
from kmk.modules.holdtap import HoldTap
from kmk.modules.layers import Layers
from kmk.modules.hex_compose import HexCompose
from kmk.modules.tapdance import TapDance
from kmk.modules.oneshot import OneShot
from kmk.extensions.rgb import RGB, AnimationModes
from kmk.consts import UnicodeMode

from kmk.handlers.sequences import unicode_string_sequence

keyboard = KMKKeyboard(active_encoders=[0], landscape_layout=True)

keyboard.unicode_mode = UnicodeMode.RALT

keyboard.modules += [
    Layers(),
    OneShot(),
    HoldTap(),
    TapDance(),
    HexCompose(encoding='utf8')
]

rgb = RGB(
    pixel_pin=keyboard.pixel_pin,
    num_pixels=8,
    animation_mode=AnimationModes.BREATHING,
    animation_speed=3,
    breathe_center=2,
)
keyboard.extensions.append(rgb)


def set_backlight(hsv):
    rgb.hue, rgb.sat, rgb.val = hsv

# layer list, must match keymap below
L_NUM, L_NUM2, L_AZ, L_AZ2, L_SYM, L_SYM2, L_HEX, L_HEX2,  = list(range(8))

XXXXX       = KC.NO
_____       = KC.TRANSPARENT

SPC_ENTER   = KC.HT(KC.SPACE, KC.ENTER)
SHFT_CTL    = KC.TD(KC.LSHIFT, KC.LCTL)

OS_NUM      = KC.OS(KC.MO(L_NUM), tap_time=None)
OS_AZ       = KC.OS(KC.MO(L_AZ),  tap_time=None)
OS_SYM      = KC.OS(KC.MO(L_SYM), tap_time=None)

TO_HEX = KC.TO(L_HEX)
TO_NUM = KC.TO(L_NUM)
TO_AZ  = KC.TO(L_AZ)

colors = dict(
    hex=(180,255,50),
    num=(265,255,50),
    az=(95,255,50)
)
set_backlight(colors['hex'])
TO_HEX.after_press_handler(lambda *_: set_backlight(colors['hex']))
TO_NUM.after_press_handler(lambda *_: set_backlight(colors['num']))
TO_AZ.after_press_handler( lambda *_: set_backlight(colors['az']))

# encoder direction does left/right or up/down with alt
keyboard.encoders.map = [
    [(KC.LEFT, KC.RIGHT, XXXXX)],
    [(KC.UP,   KC.DOWN,  XXXXX)],
] * 4

# KC.LT(layer, kc)  momentarily activates layer if held, sends kc if tapped
keyboard.keymap = [
    # -----------------------------------------------------------
    # numpad
    [
        KC.N7,      KC.N8,      KC.N9,      TO_AZ,      XXXXX,
        KC.N4,      KC.N5,      KC.N6,      KC.A,       KC.B,
        KC.N1,      KC.N2,      KC.N3,      KC.C,       KC.D,
        KC.LT(L_NUM2, OS_SYM),  # hold for NUM2 shift, tap for one-shot SYM
                    KC.N0,      SPC_ENTER,  KC.E,       KC.F,
    ],
    # numpad alt
    [
        KC.HOME,    KC.UP,      KC.ESC,     XXXXX,      XXXXX,
        KC.LEFT,    KC.ASTR,    KC.RIGHT,   KC.R,       KC.MINUS,
        KC.END,     KC.DOWN,    KC.BSPC,    KC.COLN,    KC.PLUS,
        XXXXX,      KC.SLSH,    KC.TAB,     KC.COMM,    KC.DOT,
    ],
    # -----------------------------------------------------------
    # alpha (az)
    [
        KC.S,       KC.T,       KC.U,       TO_HEX,     XXXXX,
        KC.I,       KC.L,       KC.N,       KC.O,       KC.R,
        KC.A,       KC.C,       KC.D,       KC.E,       KC.H,
        KC.LT(L_AZ2, OS_SYM),   # hold for AZ2 shift, tap for one-shot SYM
                    SHFT_CTL,   SPC_ENTER,  KC.COMM,    KC.BSPC,
    ],
    # alpha (az) alt
    [
        KC.X,       KC.Y,       KC.Z,       XXXXX,      XXXXX,
        KC.M,       KC.P,       KC.Q,       KC.V,       KC.W,
        KC.B,       KC.F,       KC.G,       KC.J,       KC.K,
        XXXXX,      OS_NUM,     KC.TAB,     KC.DOT,     KC.ESC,
    ],
    # -----------------------------------------------------------
    # symbols
    [
        KC.QUOT,    KC.LPRN,    KC.RPRN,    XXXXX,      XXXXX,
        KC.DLR,     KC.PERC,    KC.AMPR,    KC.LBRC,    KC.RBRC,
        KC.EXLM,    KC.DQT,     KC.HASH,    KC.SCLN,    KC.EQUAL,
        KC.MO(L_SYM2),      # sym shift
                    KC.SLSH,    SPC_ENTER,  KC.COMM,    KC.DOT,
    ],
    # symbols alt
    [
        KC.GRV,     KC.ASTR,    KC.UNDS,    XXXXX,      XXXXX,
        KC.BSLS,    KC.PIPE,    KC.CIRC,    KC.LCBR,    KC.RCBR,
        KC.TILD,    KC.AT,      KC.MINUS,   KC.COLN,    KC.PLUS,
        XXXXX,      KC.QUES,    KC.TAB,     KC.LABK,    KC.RABK,
    ],
    # -----------------------------------------------------------
    # hex
    [
        KC.HEX7,    KC.HEX8,    KC.HEX9,    TO_NUM,     XXXXX,
        KC.HEX4,    KC.HEX5,    KC.HEX6,    KC.HEXA,    KC.HEXB,
        KC.HEX1,    KC.HEX2,    KC.HEX3,    KC.HEXC,    KC.HEXD,
        KC.LT(L_HEX2, OS_SYM),  # hold for HEX2 shift, tap for one shot sym
                    KC.HEX0,    SPC_ENTER,  KC.HEXE,    KC.HEXF,
    ],
    # hex alt
    [
        XXXXX,      XXXXX,      XXXXX,      XXXXX,      XXXXX,
        XXXXX,      XXXXX,      XXXXX,      OS_AZ,      XXXXX,
        XXXXX,      XXXXX,      XXXXX,      XXXXX,      XXXXX,
        XXXXX,      OS_NUM,     XXXXX,      XXXXX,      KC.BSPC
    ],
]

if __name__ == '__main__':
    keyboard.go()
