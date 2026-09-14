from evdev import InputDevice, ecodes

device = InputDevice("/dev/input/by-id/usb-HAS_HAS_HS304-event-kbd")

print(f"Listening to {device.name}")

for event in device.read_loop():
    if event.type != ecodes.EV_KEY:
        continue

    if event.code not in (ecodes.KEY_PAGEUP, ecodes.KEY_PAGEDOWN):
        continue

    button = "UP" if event.code == ecodes.KEY_PAGEUP else "DOWN"

    if event.value == 1:
        print(f"{button}: pressed")
    elif event.value == 0:
        print(f"{button}: released")
