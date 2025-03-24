import json
from asyncio import create_task
from typing import Any, Callable
from gi.repository import Gdk, Gtk
from ignis.widgets import Widget
from ignis.services.niri import NiriService
from ignis.utils.shell import exec_sh_async
from ignis.utils.monitor import get_monitor


ScrollFlags = Gtk.EventControllerScrollFlags


def niri_action(action: str, args: Any = {}):
    cmd = json.dumps({"Action": {action: args}})
    return NiriService.get_default().send_command(cmd + "\n")


def run_cmd_async(cmd: str):
    return create_task(exec_sh_async(cmd))


def get_widget_monitor_id(widget: Gtk.Widget) -> int | None:
    window = widget.get_ancestor(Widget.Window)
    if window and isinstance(window, Widget.Window):
        return window.get_monitor()


def get_widget_monitor(widget: Gtk.Widget) -> Gdk.Monitor | None:
    monitor_id = get_widget_monitor_id(widget)
    if monitor_id is not None:
        return get_monitor(monitor_id)


def connect_window(widget: Gtk.Widget, signal: str, callback: Callable[..., Any]):
    def on_realize(widget: Gtk.Widget):
        window = widget.get_ancestor(Widget.Window)
        if window is not None:
            window.connect(signal, callback)

    widget.connect("realize", on_realize)


def set_on_click[Widget: Gtk.Widget](
    widget: Widget,
    left: Callable[[Widget], Any] | None = None,
    middle: Callable[[Widget], Any] | None = None,
    right: Callable[[Widget], Any] | None = None,
) -> Widget:
    def on_released(callback: Callable[[Widget], Any]):
        def handler(gesture_click: Gtk.GestureClick, n_press: int, x: int, y: int):
            if widget.contains(x, y):
                gesture_click.set_state(Gtk.EventSequenceState.CLAIMED)
                callback(widget)

        return handler

    def set_controller(widget: Gtk.Widget, button: int, callback: Callable[[Widget], Any] | None):
        if callback:
            controller = Gtk.GestureClick(button=button)
            widget.add_controller(controller)
            controller.connect("released", on_released(callback))

    for button, callback in [(Gdk.BUTTON_PRIMARY, left), (Gdk.BUTTON_MIDDLE, middle), (Gdk.BUTTON_SECONDARY, right)]:
        set_controller(widget, button, callback)

    return widget


def set_on_scroll[Widget: Gtk.Widget](
    widget: Widget,
    callback: Callable[[Widget, float, float], Any] | None = None,
    flags: ScrollFlags = ScrollFlags.BOTH_AXES | ScrollFlags.DISCRETE,
) -> Widget:
    if callback:

        def on_scroll(controller: Gtk.EventControllerScroll, dx: float, dy: float):
            callback(widget, dx, dy)

        controller = Gtk.EventControllerScroll(flags=flags)
        widget.add_controller(controller)
        controller.connect("scroll", on_scroll)

    return widget
