import digitalio
import microcontroller
import storage


mcp = microcontroller.pin
dio = digitalio.DigitalInOut

#anodes
rows = dio(mcp.GPIO22),dio(mcp.GPIO20),dio(mcp.GPIO23),dio(mcp.GPIO21),dio(mcp.GPIO4)
#cathode multiplex
mux_cols = dio(mcp.GPIO29),dio(mcp.GPIO28),dio(mcp.GPIO27),dio(mcp.GPIO26)

for p in rows:
    p.direction = digitalio.Direction.INPUT
    p.pull = digitalio.Pull.UP

for p in mux_cols:
    p.direction = digitalio.Direction.OUTPUT
    p.value = False

# disable USB drive if encoder (R1, C0) is pressed
# i.e. mux_cols = (0,0,0,0) and rows[1].value is False
if not rows[1].value:
    storage.disable_usb_drive()

