from ignis.widgets import Box, Revealer
from ignis.window_manager import WindowManager
from ignis.variable import Variable
from .constants import WindowName
from .utils import set_on_click
from .widgets import RevealerWindow


wm = WindowManager.get_default()


class OverlayWindow(Variable):
    def __init__(self, value=None):
        super().__init__(value)

    def get_window(self) -> str | None:
        return self.value

    def update_window_visible(self, name: str, visible: bool):
        if visible:
            self.set_window(name)
        else:
            self.unset_window(name)

    def set_window(self, name: str):
        previous = self.value
        if previous != name:
            if previous is not None:
                wm.close_window(previous)
            self.value = name

    def unset_window(self, name: str):
        if self.value == name:
            self.value = None


overlay_window = OverlayWindow()


class OverlayBackdrop(RevealerWindow):
    __gtype_name__ = "IgnisBackdrop"

    def __init__(self, monitor: int):
        self.__revealer = Revealer(
            hexpand=True,
            vexpand=True,
            transition_type="crossfade",
            child=Box(hexpand=True, vexpand=True, css_classes=["backdrop"]),
        )
        self.__view = Box(hexpand=True, vexpand=True, child=[self.__revealer])

        super().__init__(
            namespace=f"{WindowName.backdrop.value}-{monitor}",
            monitor=monitor,
            exclusivity="ignore",
            anchor=["top", "right", "bottom", "left"],
            layer="overlay",
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
            wm.close_window(window_name)
