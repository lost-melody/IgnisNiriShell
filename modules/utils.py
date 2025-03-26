import json
from asyncio import create_task
from typing import Any, Callable
from gi.repository import Gdk, GObject, Gtk
from ignis.widgets import Widget
from ignis.services.niri import NiriService
from ignis.options_manager import OptionsGroup
from ignis.utils.shell import exec_sh_async
from ignis.utils.monitor import get_monitor


ScrollFlags = Gtk.EventControllerScrollFlags


def niri_action(action: str, args: Any = {}):
    niri = NiriService.get_default()
    if niri.is_available:
        return niri.send_command({"Action": {action: args}})


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


def connect_option(group: OptionsGroup, option: str, callback: Callable):
    binding = group.bind(option)
    source: GObject.Object = binding.target
    source_property: str = binding.target_properties[0]
    source.connect(f"notify::{source_property.replace("-", "_")}", callback)


def bind_option(
    group: OptionsGroup,
    option: str,
    target: GObject.Object,
    target_property: str,
    flags: GObject.BindingFlags = GObject.BindingFlags.BIDIRECTIONAL,
    transform_to: Callable | None = None,
    transform_from: Callable | None = None,
):
    # target.property = transform_to(group.option)
    def on_option_changed(*_):
        value = getattr(group, option)
        if transform_to:
            value = transform_to(value)
        if target.get_property(target_property) != value:
            target.set_property(target_property, value)

    connect_option(group, option, on_option_changed)
    on_option_changed()

    if flags | GObject.BindingFlags.BIDIRECTIONAL == flags:

        # group.option = transform_from(target.property)
        def on_option_set(*_):
            value = target.get_property(target_property)
            if transform_from:
                value = transform_from(value)
            if getattr(group, option) != value:
                setattr(group, option, value)

        target.connect(f"notify::{target_property}", on_option_set)


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
