from ignis.services.network import Ethernet, NetworkService, Wifi
from ignis.widgets import Box, Icon
from ignis.window_manager import WindowManager

from ..constants import WindowName
from ..utils import set_on_click

wm = WindowManager.get_default()


class Network(Box):
    __gtype_name__ = "IgnisNetwork"

    class NetworkEthernet(Box):
        __gtype_name__ = "IgnisNetworkEthernet"

        def __init__(self, ethernet: Ethernet):
            self.__ethernet = ethernet
            super().__init__(css_classes=["px-1"], child=[Icon(image=ethernet.bind("icon_name"))])
            ethernet.connect("notify::is-connected", self.__on_change)
            self.__on_change()
            set_on_click(self, left=self.__class__.__on_clicked, right=self.__class__.__on_clicked)

        def __on_change(self, *_):
            connected = self.__ethernet.is_connected
            self.set_tooltip_text("Connected" if connected else "Disconnected")

        def __on_clicked(self, *_):
            wm.toggle_window(WindowName.control_center.value)

    class NetworkWifi(Box):
        __gtype_name__ = "IgnisNetworkWifi"

        def __init__(self, wifi: Wifi):
            self.__wifi = wifi
            super().__init__(css_classes=["px-1"], child=[Icon(image=wifi.bind("icon_name"))])
            wifi.connect("notify::enabled", self.__on_change)
            wifi.connect("notify::is-connected", self.__on_change)
            self.__on_change()
            set_on_click(
                self,
                left=self.__class__.__on_clicked,
                right=lambda _: wm.toggle_window(WindowName.control_center.value),
            )

        def __on_change(self, *_):
            enabled = self.__wifi.enabled
            connected = self.__wifi.is_connected
            self.set_tooltip_text("Disabled" if not enabled else "Connected" if connected else "Disconnected")

        def __on_clicked(self, *_):
            self.__wifi.enabled = not self.__wifi.enabled

    def __init__(self):
        self.__service = NetworkService.get_default()
        super().__init__(
            css_classes=["hover", "rounded"],
            child=[self.NetworkEthernet(self.__service.ethernet), self.NetworkWifi(self.__service.wifi)],
        )
