from ignis.app import IgnisApp
from ignis.widgets import Widget
from ignis.variable import Variable
from .constants import WindowName
from .utils import set_on_click


app = IgnisApp.get_default()


class OverlayWindow(Variable):
    def __init__(self, value=None):
        super().__init__(value)

    def get_window(self) -> str | None:
        return self.get_value()

    def set_window(self, name: str):
        previous = self.get_value()
        if previous != name:
            if previous is not None:
                app.close_window(previous)
            self.set_value(name)

    def unset_window(self, name: str):
        if self.get_value() == name:
            self.set_value(None)


overlay_window = OverlayWindow()


class OverlayBackdrop(Widget.RevealerWindow):
    __gtype_name__ = "IgnisBackdrop"

    def __init__(self, monitor: int):
        self.__revealer = Widget.Revealer(
            hexpand=True,
            vexpand=True,
            transition_type="crossfade",
            child=Widget.Box(hexpand=True, vexpand=True, css_classes=["backdrop"]),
        )
        self.__view = Widget.Box(hexpand=True, vexpand=True, child=[self.__revealer])

        super().__init__(
            namespace=f"{WindowName.backdrop.value}-{monitor}",
            monitor=monitor,
            exclusivity="ignore",
            anchor=["top", "right", "bottom", "left"],
            visible=False,
            css_classes=["transparent"],
            child=self.__view,
            revealer=self.__revealer,
        )

        overlay_window.connect("notify::value", self.__on_overlay_window_changed)
        set_on_click(
            self.__view,
            left=self.__on_backdrop_clicked,
            middle=self.__on_backdrop_clicked,
            right=self.__on_backdrop_clicked,
        )

    def __on_overlay_window_changed(self, *_):
        window_name = overlay_window.get_window()
        self.set_visible(window_name is not None)

    def __on_backdrop_clicked(self, *_):
        window_name = overlay_window.get_window()
        if window_name is not None:
            app.close_window(window_name)
