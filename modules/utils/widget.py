from typing import Any, Callable, overload

from gi.repository import Gdk, Gtk
from ignis.gobject import IgnisProperty
from ignis.utils import get_monitor
from ignis.widgets import Window

from .signal import weak_connect


@overload
def GProperty(getter: Callable) -> property: ...


@overload
def GProperty(getter: None = None, type: type | None = None, default: Any = None) -> type[property]: ...


def GProperty(
    getter: Callable | None = None, type: type | None = None, default: Any = None
) -> property | type[property]:
    return IgnisProperty(getter, type=type, default=default)  # type: ignore


def get_widget_monitor_id(widget: Gtk.Widget) -> int | None:
    window = widget.get_ancestor(Window)
    if window and isinstance(window, Window):
        return window.get_monitor()


def get_widget_monitor(widget: Gtk.Widget) -> Gdk.Monitor | None:
    monitor_id = get_widget_monitor_id(widget)
    if monitor_id is not None:
        return get_monitor(monitor_id)


def connect_window(widget: Gtk.Widget, signal: str, callback: Callable[..., Any]):
    def on_realize(widget: Gtk.Widget):
        window = widget.get_ancestor(Window)
        if isinstance(window, Window):
            weak_connect(window, signal, callback)

    widget.connect("realize", on_realize)
