from typing import Any, Callable
import weakref

from gi.repository import Gdk, Gtk

ScrollFlags = Gtk.EventControllerScrollFlags


def set_on_click[Widget: Gtk.Widget](
    widget: Widget,
    left: Callable[[Widget], Any] | None = None,
    middle: Callable[[Widget], Any] | None = None,
    right: Callable[[Widget], Any] | None = None,
) -> Widget:
    def on_released(widget: Widget, callback: Callable[[Widget], Any]):
        ref = weakref.ref(widget)

        def handler(gesture_click: Gtk.GestureClick, n_press: int, x: int, y: int):
            widget = ref()
            if widget and widget.contains(x, y):
                gesture_click.set_state(Gtk.EventSequenceState.CLAIMED)
                return callback(widget)

        return handler

    def set_controller(widget: Widget, button: int, callback: Callable[[Widget], Any] | None):
        if callback:
            controller = Gtk.GestureClick(button=button)
            widget.add_controller(controller)
            controller.connect("released", on_released(widget, callback))

    for button, callback in [(Gdk.BUTTON_PRIMARY, left), (Gdk.BUTTON_MIDDLE, middle), (Gdk.BUTTON_SECONDARY, right)]:
        set_controller(widget, button, callback)

    return widget


def set_on_scroll[Widget: Gtk.Widget](
    widget: Widget,
    callback: Callable[[Widget, float, float], Any] | None = None,
    flags: ScrollFlags = ScrollFlags.BOTH_AXES | ScrollFlags.DISCRETE,
) -> Widget:
    if callback:
        ref = weakref.ref(widget)

        def on_scroll(controller: Gtk.EventControllerScroll, dx: float, dy: float):
            widget = ref()
            if widget:
                return callback(widget, dx, dy)

        controller = Gtk.EventControllerScroll(flags=flags)
        widget.add_controller(controller)
        controller.connect("scroll", on_scroll)

    return widget


def set_on_motion[Widget: Gtk.Widget](
    widget: Widget,
    enter: Callable[[Widget, float, float], Any] | None = None,
    leave: Callable[[Widget], Any] | None = None,
    motion: Callable[[Widget, float, float], Any] | None = None,
) -> Widget:
    controller = Gtk.EventControllerMotion()
    widget.add_controller(controller)

    def callback(widget: Widget, cb: Callable[[Widget], Any]):
        ref = weakref.ref(widget)

        def handler():
            widget = ref()
            if widget:
                return cb(widget)

        return handler

    def callback_xy(widget: Widget, cb: Callable[[Widget, float, float], Any]):
        ref = weakref.ref(widget)

        def handler(controller: Gtk.EventControllerMotion, x: float, y: float):
            widget = ref()
            if widget:
                return cb(widget, x, y)

        return handler

    if enter:
        controller.connect("enter", callback_xy(widget, enter))
    if leave:
        controller.connect("leave", callback(widget, leave))
    if motion:
        controller.connect("motion", callback_xy(widget, motion))

    return widget
