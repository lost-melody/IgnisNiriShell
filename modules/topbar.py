from gi.repository import Gtk
from ignis.widgets import Window
from ignis.app import IgnisApp
from .constants import WindowName
from .template import gtk_template
from .useroptions import user_options
from .utils import connect_option


app = IgnisApp.get_default()


class Topbar(Window):
    __gtype_name__ = "Topbar"

    @gtk_template("topbar")
    class View(Gtk.CenterBox):
        __gtype_name__ = "TopbarView"

    def __init__(self, monitor: int = 0):
        self.__options = user_options and user_options.topbar
        super().__init__(
            namespace=f"{WindowName.top_bar.value}-{monitor}",
            monitor=monitor,
            anchor=["top", "left", "right"],
            css_classes=["topbar"],
        )

        self.__view = self.View()
        self.set_child(self.__view)

        if self.__options:
            connect_option(self.__options, "exclusive", self.__on_exclusive_changed)
            connect_option(self.__options, "focusable", self.__on_focusable_changed)
            self.__on_exclusive_changed()

    def __on_exclusive_changed(self, *_):
        if not self.__options:
            return

        self.set_exclusivity("exclusive" if self.__options.exclusive else "normal")

    def __on_focusable_changed(self, *_):
        if not self.__options:
            return

        self.set_exclusivity("on_demand" if self.__options.focusable else "none")
