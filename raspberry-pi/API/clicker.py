from evdev import InputDevice, ecodes


class Clicker:
    def __init__(self, capture_controller):
        self.capture_controller = capture_controller

    def listen(self):
        device = InputDevice("/dev/input/by-id/usb-HAS_HAS_HS304-event-kbd")

        for event in device.read_loop():
            if event.type != ecodes.EV_KEY:
                continue

            if event.code not in (ecodes.KEY_PAGEUP, ecodes.KEY_PAGEDOWN):
                continue

            if event.value != 1:
                continue

            self.capture_controller.trigger()