import dataclasses
import enum
import os

from gi.repository import GLib
from ignis.base_service import BaseService
from ignis.dbus import DBusProxy, DBusService
from ignis.gobject import IgnisGObject, IgnisSignal
from ignis.utils import load_interface_xml
from ignis.variable import Variable

from ..useroptions import user_options
from ..utils import GProperty, dbus_info_file


class FcitxStateService(BaseService):
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

        @dataclasses.dataclass
        class Lookup:
            layout: int = 0
            cursor: int = 0
            label: list[str] = dataclasses.field(default_factory=list)
            text: list[str] = dataclasses.field(default_factory=list)
            attr: list[str] = dataclasses.field(default_factory=list)

        def __init__(self):
            super().__init__()

            self._enabled = False
            self._show_aux = False
            self._show_lookup = False
            self._show_preedit = False
            self._aux = ""
            self._preedit = ""
            self._fcitx_im = self.Property(key="/Fcitx/im")
            self._properties: list[FcitxStateService.KIMPanel.Property] = []
            self._spot = self.Rect()
            self._lookup = self.Lookup()

            # whther fcitx KIM panel is enabled
            options = user_options and user_options.fcitx_kimpanel
            if options and not options.enabled:
                return

            self.impanel = DBusService(
                name="org.kde.impanel",
                object_path="/org/kde/impanel",
                info=load_interface_xml(path=dbus_info_file("org.kde.impanel.xml")),
                on_name_acquired=self.__on_impanel_acquired,
            )

            self.impanel2 = DBusService(
                name="org.kde.impanel",
                object_path="/org/kde/impanel",
                info=load_interface_xml(path=dbus_info_file("org.kde.impanel2.xml")),
                on_name_acquired=self.__on_impanel2_acquired,
            )
            self.__register_methods2(self.impanel2)

            self.proxy = DBusProxy.new(
                name="org.kde.kimpanel.inputmethod",
                object_path="/kimpanel",
                interface_name="org.kde.kimpanel.inputmethod",
                info=load_interface_xml(path=dbus_info_file("org.kde.impanel.inputmethod.xml")),
                bus_type="session",
            )
            self.__subscribe_signals(self.proxy)

        @IgnisSignal
        def exec_menu(self, properties: Variable):
            return

        @GProperty
        def enabled(self) -> bool:
            return self._enabled

        @GProperty
        def show_aux(self) -> bool:
            return self._show_aux

        @GProperty
        def show_lookup(self) -> bool:
            return self._show_lookup

        @GProperty
        def show_preedit(self) -> bool:
            return self._show_preedit

        @GProperty
        def aux(self) -> str:
            return self._aux

        @GProperty
        def preedit(self) -> str:
            return self._preedit

        @GProperty
        def fcitx_im(self) -> Property:
            return self._fcitx_im

        @GProperty
        def fcitx_properties(self) -> list[Property]:
            return self._properties

        @GProperty
        def spot(self) -> Rect:
            return self._spot

        @GProperty
        def lookup(self) -> Lookup:
            return self._lookup

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
            self._lookup = self.Lookup(label=label, text=text, attr=attr, cursor=cursor, layout=layout)
            self.notify("lookup")

        def __on_signal(self, _, __, ___, ____, signal: str, param: GLib.Variant):
            match self.SignalName(signal):
                case self.SignalName.Enable:
                    # input method enabled
                    self._enabled = param.get_child_value(0).get_boolean()
                    self.notify("enabled")
                case self.SignalName.ExecMenu:
                    # show menu: list[str]
                    properties = [self.__parse_property(p) for p in param.get_child_value(0).unpack()]
                    self.emit("exec-menu", Variable(value=properties))
                case self.SignalName.RegisterProperties:
                    # register properties
                    self._properties = [self.__parse_property(p) for p in param.get_child_value(0).unpack()]
                    self.notify("fcitx-properties")
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
                    self._fcitx_im.text = self.fcitx_im.text.split(" - ")[-1]
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

        self._kimpanel = self.KIMPanel()

    @GProperty
    def kimpanel(self) -> KIMPanel:
        return self._kimpanel

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

    async def __fcitx_proxy(self):
        return await DBusProxy.new_async(
            name="org.fcitx.Fcitx5",
            object_path="/controller",
            interface_name="org.fcitx.Fcitx.Controller1",
            info=load_interface_xml(path=os.path.join(self.current_dir, "dbus", "org.fcitx.Fcitx5.controller.xml")),
            bus_type="session",
        )
