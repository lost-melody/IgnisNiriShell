from gi.repository import Gtk
from ignis.app import IgnisApp
from ignis.widgets import Box, Icon, Window
from ignis.window_manager import WindowManager

from ..constants import WindowName
from ..utils import set_on_click
from ..variables import caffeine_state

app = IgnisApp.get_initialized()
wm = WindowManager.get_default()


class CaffeineIndicator(Box):
    __gtype_name__ = "IgnisCaffeineIndicator"

    def __init__(self):
        self.__state = caffeine_state
        self.__cookie: int = 0
        super().__init__(
            css_classes=["hover", "px-1", "rounded"],
            tooltip_text="Caffeine enabled",
            visible=False,
            child=[Icon(image="my-caffeine-on-symbolic")],
        )
        self.__state.connect("notify::value", self.__on_changed)
        set_on_click(self, left=self.__on_clicked, right=self.__on_right_clicked)

    def __on_changed(self, *_):
        enabled = True if self.__state.value else False
        self.set_visible(enabled)

        if enabled:
            window = self.get_ancestor(Window)
            if isinstance(window, Window):
                self.__cookie = app.inhibit(
                    window=window, flags=Gtk.ApplicationInhibitFlags.IDLE, reason="Caffeine Mode Enabled"
                )
        else:
            if self.__cookie != 0:
                app.uninhibit(self.__cookie)

    def __on_clicked(self, *_):
        self.__state.value = not self.__state.value

    def __on_right_clicked(self, *_):
        wm.toggle_window(WindowName.control_center.value)
