import asyncio
import os
from typing import Any
from gi.repository import Gio, GLib
from loguru import logger
from ignis.base_service import BaseService
from ignis.dbus import DBusProxy
from ignis.gobject import IgnisProperty
from ignis.utils import file_monitor, load_interface_xml, Poll, thread


try:
    import libevdev as _

    libevdev_available = True
except:
    libevdev_available = False


class CpuLoadService(BaseService):
    def __init__(self):
        super().__init__()
        self._cpu_count = self.__read_cpu_count()
        self._idle_time: int = 0
        self._total_time: int = 0
        self.__cpu_times = self.__read_cpu_times()
        self.__poll = Poll(timeout=1000, callback=self.__update_times)

    @classmethod
    def __read_cpu_count(cls) -> int:
        with open("/proc/cpuinfo") as cpuinfo:
            count = 0
            for line in cpuinfo.readlines():
                if line.startswith("processor"):
                    count += 1
            return count

    @classmethod
    def __read_cpu_times(cls) -> list[int]:
        with open("/proc/stat") as stat:
            line = stat.readline().split()[1:]
            return list(map(int, line[: min(7, len(line))]))

    @IgnisProperty
    def cpu_count(self) -> int:
        return self._cpu_count

    @IgnisProperty
    def idle_time(self) -> int:
        """
        idle cpu time during last polling interval
        """
        return self._idle_time

    @IgnisProperty
    def total_time(self) -> int:
        """
        total cpu time during last polling interval
        """
        return self._total_time

    @IgnisProperty
    def interval(self) -> int:
        """
        sample interval in milliseconds
        """
        return self.__poll.timeout

    @interval.setter
    def interval(self, ms: int):
        self.__poll.timeout = ms

    def __update_times(self, *_):
        """
        updates (idle, total) since last called
        """
        times = self.__read_cpu_times()
        deltas = [times[i] - self.__cpu_times[i] for i in range(len(times))]
        self._total_time = sum(deltas)
        self.notify("total_time")
        self._idle_time = deltas[3]
        self.notify("idle_time")
        self.__cpu_times = times


class FcitxStateService(BaseService):
    current_dir = os.path.dirname(os.path.abspath(__file__))

    def __init__(self):
        super().__init__()

        self._is_active: bool = False
        self._current_input_method: str = ""
        self._current_schema: str = ""
        self._is_ascii_mode: str = ""

        run_dir = os.getenv("XDG_RUNTIME_DIR")
        if run_dir:
            fm = file_monitor.FileMonitor(
                path=os.path.join(run_dir, "fcitx-ignis-signal"), callback=self.__on_fcitx_signal
            )
            if isinstance(fm._monitor, Gio.FileMonitor):
                fm._monitor.set_rate_limit(50)

    @IgnisProperty
    def is_active(self) -> bool:
        return self._is_active

    @IgnisProperty
    def current_input_method(self) -> str:
        return self._current_input_method

    @IgnisProperty
    def current_schema(self) -> str:
        return self._current_schema

    @IgnisProperty
    def is_ascii_mode(self) -> str:
        return self._is_ascii_mode

    def __on_fcitx_signal(self, *_):
        asyncio.create_task(self.sync_state_async())

    async def __fcitx_proxy(self):
        return await DBusProxy.new_async(
            name="org.fcitx.Fcitx5",
            object_path="/controller",
            interface_name="org.fcitx.Fcitx.Controller1",
            info=load_interface_xml(path=os.path.join(self.current_dir, "dbus", "org.fcitx.Fcitx5.controller.xml")),
            bus_type="session",
        )

    async def __rime_proxy(self):
        return await DBusProxy.new_async(
            name="org.fcitx.Fcitx5",
            object_path="/rime",
            interface_name="org.fcitx.Fcitx.Rime1",
            info=load_interface_xml(path=os.path.join(self.current_dir, "dbus", "org.fcitx.Fcitx5.rime.xml")),
            bus_type="session",
        )


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

    @IgnisProperty
    def numlock(self) -> bool | None:
        return self._numlock

    @IgnisProperty
    def capslock(self) -> bool | None:
        return self._capslock

    @IgnisProperty
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
            except:
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
        except:
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
