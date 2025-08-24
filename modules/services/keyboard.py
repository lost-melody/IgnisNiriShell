import os
from typing import Any

from gi.repository import GLib
from ignis.base_service import BaseService
from ignis.utils import thread
from loguru import logger

from ..utils import GProperty

try:
    import libevdev

    del libevdev
    libevdev_available = True
except ModuleNotFoundError:
    libevdev_available = False


class KeyboardLedsService(BaseService):
    DEV_PATH = "/dev/input"

    if libevdev_available:
        import libevdev

        EV_LED = libevdev.EV_LED  # type: ignore
        LED_NUML = libevdev.EV_LED.LED_NUML  # type: ignore
        LED_CAPSL = libevdev.EV_LED.LED_CAPSL  # type: ignore
        LED_SCROLLL = libevdev.EV_LED.LED_SCROLLL  # type: ignore
    else:
        EV_LED = None
        LED_NUML = None
        LED_CAPSL = None
        LED_SCROLLL = None

    def __init__(self):
        super().__init__()

        self._numlock: bool | None = None
        self._capslock: bool | None = None
        self._scrolllock: bool | None = None

        self.__sync_devices()

    @GProperty
    def numlock(self) -> bool | None:
        return self._numlock

    @GProperty
    def capslock(self) -> bool | None:
        return self._capslock

    @GProperty
    def scrolllock(self) -> bool | None:
        return self._scrolllock

    def __sync_devices(self):
        if not libevdev_available:
            logger.warning("Install `libevdev` to display capslock state in OSD")
            return
        import libevdev

        for file in os.listdir(self.DEV_PATH):
            if not file.startswith("event"):
                continue

            fd = open(f"{self.DEV_PATH}/{file}", "rb")
            try:
                device = libevdev.Device(fd)
                if self.__device_support_leds(device):
                    thread(target=lambda d=device: self.__listen_to_events(d))
            except Exception:
                logger.warning("User should be a member of the `input` group to display capslock state in OSD")
                break

    @classmethod
    def __device_support_leds(cls, d: Any) -> bool:
        import libevdev

        device: libevdev.Device = d
        if not device.has(cls.EV_LED):
            return False

        for led in [cls.LED_NUML, cls.LED_CAPSL, cls.LED_SCROLLL]:
            if device.has(led):
                return True

        return False

    def __listen_to_events(self, d: Any):
        import libevdev

        device: libevdev.Device = d
        try:
            while True:
                for event in device.events():
                    if not event.type == self.EV_LED:
                        continue

                    GLib.idle_add(lambda c=event.code, s=event.value: self.__on_led_changed(c, s))
        except Exception:
            pass

    def __on_led_changed(self, code: Any, state: Any):
        enabled = state != 0
        match code:
            case self.LED_NUML:
                if self._numlock != enabled:
                    self._numlock = enabled
                    self.notify("numlock")
            case self.LED_CAPSL:
                if self._capslock != enabled:
                    self._capslock = enabled
                    self.notify("capslock")
            case self.LED_SCROLLL:
                if self._scrolllock != enabled:
                    self._scrolllock = enabled
                    self.notify("scrolllock")
