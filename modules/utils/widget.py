from typing import Any, Callable

from gi.repository import Gdk, GObject, Gtk
from ignis.utils import get_monitor
from ignis.widgets import Window

gproperty: Callable[..., type[property]] = GObject.Property  # type: ignore


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
            window.connect(signal, callback)

    widget.connect("realize", on_realize)
