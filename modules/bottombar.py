from gi.repository import Gtk
from ignis.widgets import Widget
from .constants import WindowName
from .modules import *
from .template import gtk_template


class BottomBar(Widget.Window):
    __gtype_name__ = "IgnisBottomBar"

    @gtk_template("bottombar")
    class View(Gtk.CenterBox):
        __gtype_name__ = "BottomBarView"

    def __init__(self, monitor: int = 0):
        super().__init__(
            namespace=f"{WindowName.bottom_bar.value}-{monitor}",
            monitor=monitor,
            exclusivity="exclusive",
            anchor=["bottom", "left", "right"],
            css_classes=["bottombar"],
        )

        self.__view = self.View()
        self.set_child(self.__view)
