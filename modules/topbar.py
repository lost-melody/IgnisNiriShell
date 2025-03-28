from gi.repository import Gtk
from ignis.widgets import Widget
from ignis.app import IgnisApp
from .constants import WindowName
from .modules import *
from .template import gtk_template


app = IgnisApp.get_default()


class Topbar(Widget.Window):
    __gtype_name__ = "Topbar"

    @gtk_template("topbar")
    class View(Gtk.CenterBox):
        __gtype_name__ = "TopbarView"

    def __init__(self, monitor: int = 0):
        super().__init__(
            namespace=f"{WindowName.top_bar.value}-{monitor}",
            monitor=monitor,
            exclusivity="exclusive",
            anchor=["top", "left", "right"],
            css_classes=["topbar"],
        )

        self.__view = self.View()
        self.set_child(self.__view)
