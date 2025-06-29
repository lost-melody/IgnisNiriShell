import dataclasses
import enum
import os
from typing import Any
from gi.repository import GLib
from loguru import logger
from ignis.base_service import BaseService
from ignis.dbus import DBusProxy, DBusService
from ignis.gobject import IgnisGObject, IgnisProperty
from ignis.utils import load_interface_xml, Poll, thread


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

    class KIMPanel(IgnisGObject):
        class SignalName(enum.Enum):
            Enable = "Enable"
            ExecDialog = "ExecDialog"
            ExecMenu = "ExecMenu"
            RegisterProperties = "RegisterProperties"
            RemoveProperty = "RemoveProperty"
            ShowAux = "ShowAux"
            ShowLookupTable = "ShowLookupTable"
            ShowPreedit = "ShowPreedit"
            UpdateAux = "UpdateAux"
            UpdateLookupTableCursor = "UpdateLookupTableCursor"
            UpdatePreeditCaret = "UpdatePreeditCaret"
            UpdatePreeditText = "UpdatePreeditText"
            UpdateProperty = "UpdateProperty"
            UpdateScreen = "UpdateScreen"
            UpdateSpotLocation = "UpdateSpotLocation"

        @dataclasses.dataclass
        class Property:
            key: str = ""
            label: str = ""
            icon: str = ""
            text: str = ""
            hint: list[str] = dataclasses.field(default_factory=list)

        @dataclasses.dataclass
        class Rect:
            x: int = 0
            y: int = 0
            w: int = 0
            h: int = 0

        def __init__(self):
            super().__init__()

            self._enabled = False
            self._show_aux = False
            self._show_lookup = False
            self._show_preedit = False
            self._aux = ""
            self._preedit = ""
            self._fcitx_im = self.Property(key="/Fcitx/im")
            self._spot = self.Rect()

            self.impanel = DBusService(
                name="org.kde.impanel",
                object_path="/org/kde/impanel",
                info=load_interface_xml(
                    path=os.path.join(FcitxStateService.current_dir, "dbus", "org.kde.impanel.xml")
                ),
                on_name_acquired=self.__on_impanel_acquired,
            )

            self.impanel2 = DBusService(
                name="org.kde.impanel",
                object_path="/org/kde/impanel",
                info=load_interface_xml(
                    path=os.path.join(FcitxStateService.current_dir, "dbus", "org.kde.impanel2.xml")
                ),
                on_name_acquired=self.__on_impanel2_acquired,
            )
            self.__register_methods2(self.impanel2)

            self.proxy = DBusProxy.new(
                name="org.fcitx.Fcitx5",
                object_path="/kimpanel",
                interface_name="org.kde.kimpanel.inputmethod",
                info=load_interface_xml(
                    path=os.path.join(FcitxStateService.current_dir, "dbus", "org.kde.impanel.inputmethod.xml")
                ),
                bus_type="session",
            )
            self.__subscribe_signals(self.proxy)

        @IgnisProperty
        def enabled(self) -> bool:
            return self._enabled

        @IgnisProperty
        def show_aux(self) -> bool:
            return self._show_aux

        @IgnisProperty
        def show_lookup(self) -> bool:
            return self._show_lookup

        @IgnisProperty
        def show_preedit(self) -> bool:
            return self._show_preedit

        @IgnisProperty
        def aux(self) -> str:
            return self._aux

        @IgnisProperty
        def preedit(self) -> str:
            return self._preedit

        @IgnisProperty
        def fcitx_im(self) -> Property:
            return self._fcitx_im

        @IgnisProperty
        def spot(self) -> Rect:
            return self._spot

        def signal_trigger_property(self, key: str):
            self.impanel.emit_signal("TriggerProperty", GLib.Variant.new_tuple(GLib.Variant.new_string(key)))

        def signal_exit(self):
            self.impanel.emit_signal("Exit")

        def signal_reload_config(self):
            self.impanel.emit_signal("ReloadConfig")

        def signal_configure(self):
            self.impanel.emit_signal("Configure")

        def __on_impanel_acquired(self, *_):
            self.impanel.emit_signal("PanelCreated")

        def __on_impanel2_acquired(self, *_):
            self.impanel.emit_signal("PanelCreated2")

        def __register_methods2(self, dbus: DBusService):
            dbus.register_dbus_method("SetSpotRect", self.__dbus_set_spot_rect)
            dbus.register_dbus_method("SetLookupTable", self.__dbus_set_lookup_table)

        def __subscribe_signals(self, proxy: DBusProxy):
            for signal in self.SignalName:
                proxy.signal_subscribe(signal.value, self.__on_signal)

        def __dbus_set_spot_rect(self, _, x: int, y: int, w: int, h: int):
            self._spot = self.Rect(x, y, w, h)
            self.notify("spot")

        def __dbus_set_lookup_table(
            self,
            _,
            label: list[str],
            text: list[str],
            attr: list[str],
            hasPrev: bool,
            hasNext: bool,
            cursor: int,
            layout: int,
        ):
            pass

        def __on_signal(self, _, __, ___, ____, signal: str, param: GLib.Variant):
            match self.SignalName(signal):
                case self.SignalName.Enable:
                    # input method enabled
                    self._enabled = param.get_child_value(0).get_boolean()
                    self.notify("enabled")
                case self.SignalName.ExecMenu:
                    # show menu: list[str]
                    pass
                case self.SignalName.RegisterProperties:
                    # register properties
                    pass
                case self.SignalName.ShowAux:
                    # show and hide aux tooltip
                    self._show_aux = param.get_child_value(0).get_boolean()
                    self.notify("show-aux")
                case self.SignalName.ShowLookupTable:
                    # show and hide lookup table
                    self._show_lookup = param.get_child_value(0).get_boolean()
                    self.notify("show-lookup")
                case self.SignalName.ShowPreedit:
                    # show and hide preedit text
                    self._show_preedit = param.get_child_value(0).get_boolean()
                    self.notify("show-preedit")
                case self.SignalName.UpdateAux:
                    # update aux tooltip
                    self._aux = param.get_child_value(0).get_string()
                    self.notify("aux")
                case self.SignalName.UpdatePreeditText:
                    # update preedit text
                    self._preedit = param.get_child_value(0).get_string()
                    self.notify("preedit")
                case self.SignalName.UpdateProperty:
                    # update property
                    self._fcitx_im = self.__parse_property(param.get_child_value(0).get_string())
                    self.notify("fcitx-im")
                case self.SignalName.UpdateSpotLocation:
                    # update spot location: x, y
                    x = param.get_child_value(0).get_int32()
                    y = param.get_child_value(0).get_int32()
                    self._spot = self.Rect(x, y, self.spot.w, self.spot.h)
                    self.notify("spot")

        def __parse_property(self, property: str) -> Property:
            [key, label, icon, text, hint] = property.split(":")
            hint = hint.split(",")
            for h in hint:
                if h.startswith("label="):
                    label = h.lstrip("lable=")
                    icon = ""
                    break
            return self.Property(key, label, icon, text, hint)

    def __init__(self):
        super().__init__()

        self._label: str = ""
        self._text: str = ""
        self._icon: str = ""

        self._kimpanel = self.KIMPanel()
        self._kimpanel.connect("notify::fcitx-im", self.__on_fcitx_im_changed)

    @IgnisProperty
    def kimpanel(self) -> KIMPanel:
        return self._kimpanel

    @IgnisProperty
    def label(self) -> str:
        return self._label

    @IgnisProperty
    def text(self) -> str:
        return self._text

    @IgnisProperty
    def icon(self) -> str:
        return self._icon

    async def is_active(self, proxy: DBusProxy | None = None) -> bool:
        proxy = proxy or await self.__fcitx_proxy()
        state = await proxy.StateAsync("()")
        return state[0] == 2

    async def toggle_activate(self):
        proxy = await self.__fcitx_proxy()
        if await self.is_active(proxy):
            await proxy.DeactivateAsync("()")
        else:
            await proxy.ActivateAsync("()")

    def __on_fcitx_im_changed(self, *_):
        prop = self._kimpanel.fcitx_im
        # "Keyboard - French - French (AZERTY, AFNOR)"
        text = prop.text.split("-")[-1].strip(" ")
        if self.label != prop.label:
            self._label = prop.label
            self.notify("label")
        if self.text != text:
            self._text = text
            self.notify("text")
        if self.icon != prop.icon:
            self._icon = prop.icon
            self.notify("icon")

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
