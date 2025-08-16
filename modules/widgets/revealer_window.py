from typing import Any

from gi.repository import Gtk
from ignis.widgets import Window

from ..utils import gproperty


class RevealerWindow(Window):
    __gtype_name__ = "MyRevealerWindow"

    def __init__(self, revealer: Gtk.Revealer, **kwargs):
        self._revealer = revealer
        super().__init__(**kwargs)

        def on_child_revealed(revealer: Gtk.Revealer, *_):
            if not revealer.get_reveal_child():
                window = revealer.get_ancestor(Gtk.Window)
                if isinstance(window, Gtk.Window):
                    window.set_visible(False)

        self._revealer.connect("notify::child-revealed", on_child_revealed)

    def set_property(self, property_name: str, value: Any):
        if property_name == "visible":
            if value or not self._revealer.get_reveal_child():
                # set True from outside, or set False from on_child_revealed
                super().set_property(property_name, value)
            if value != self._revealer.get_reveal_child():
                self._revealer.set_reveal_child(value)
                self.notify("visible")
        else:
            super().set_property(property_name, value)

    @gproperty(type=bool, default=False)
    def visible(self) -> bool:
        return self._revealer.get_reveal_child()

    @visible.setter
    def visible(self, visible: bool):
        super().set_visible(visible)
