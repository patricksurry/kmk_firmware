from kb import KMKKeyboard

from kmk.keys import KC
from kmk.extensions.rgb import RGB, AnimationModes
from kmk.extensions.via import VIAShifter

from microcontroller import pin

# add active_encoders=[0, 2] to constructor if first and third encoders installed
landscape = True

keyboard = KMKKeyboard(landscape_layout=landscape)

rgb = RGB(
    pixel_pin=keyboard.pixel_pin,
    num_pixels=8,
    animation_mode=AnimationModes.BREATHING,
    animation_speed=3,
    breathe_center=2,
)
keyboard.extensions.append(rgb)
keyboard.extensions.append(VIAShifter(CS_=pin.GPIO11, RDY=pin.GPIO12, SDA=pin.GPIO13, SCL=pin.GPIO14, debug=True))

XXXXX = KC.NO

# fmt:off
if landscape:
    keyboard.keymap = [
        [
            KC.N7,  KC.N8,   KC.N9,   XXXXX,  XXXXX,
            KC.N4,  KC.N5,   KC.N6,   KC.PPLS, KC.PMNS,
            KC.N1,  KC.N2,   KC.N3,   KC.PSLS, KC.PAST,
            KC.LSFT,  KC.N0, KC.PENT, KC.T, KC.Y #TODO KC.PDOT, KC.BKSP,
        ]
    ]
else:
    keyboard.keymap = [
        [
            XXXXX,  KC.PSLS, KC.PAST, KC.PMNS,
            KC.P7,  KC.P8,   KC.P9,   KC.PPLS,
            KC.P4,  KC.P5,   KC.P6,   KC.PPLS,
            KC.P1,  KC.P2,   KC.P3,   KC.PENT,
            KC.P0,  KC.P0,   KC.PDOT, KC.PENT,
        ]
    ]

# fmt:on

if __name__ == '__main__':
    keyboard.go()
