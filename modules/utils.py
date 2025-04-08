import base64
import shlex
from asyncio import create_task
from typing import Any, Callable
from gi.repository import Gdk, Gio, GObject, Gtk
from ignis.widgets import Widget
from ignis.services.applications import Application
from ignis.services.niri import NiriService
from ignis.options_manager import OptionsGroup
from ignis.utils.icon import get_app_icon_name as ignis_get_app_icon_name
from ignis.utils.shell import exec_sh_async
from ignis.utils.monitor import get_monitor


ScrollFlags = Gtk.EventControllerScrollFlags
gproperty: Callable[..., type[property]] = GObject.Property  # type: ignore

app_icon_overrides: dict[str, str] = {}
app_id_overrides: dict[str, str] = {}


class Pool[T]():
    def __init__(self, provider: Callable[[], T]):
        self.__pool: list[T] = []
        self.__provider = provider

    def acquire(self) -> T:
        if len(self.__pool) == 0:
            return self.__provider()
        else:
            return self.__pool.pop()

    def release(self, value: T):
        self.__pool.append(value)


class CpuTimes:
    def __init__(self):
        self.__times = self.read_cpu_times()

    @classmethod
    def read_cpu_times(cls):
        with open("/proc/stat") as stat:
            line = stat.readline().split()[1:]
            return list(map(int, line[: min(7, len(line))]))

    def get_delta(self):
        """
        returns (idle, total) since last called
        """
        times = self.read_cpu_times()
        deltas = [times[i] - self.__times[i] for i in range(len(times))]
        total = sum(deltas)
        idle = deltas[3]
        self.__times = times
        return idle, total


def b64enc(input: str) -> str:
    return base64.b64encode(input.encode()).decode().rstrip("=")


def get_app_id(app_id: str) -> str:
    if app_id.lower().endswith(".desktop"):
        app_id = app_id[:-8]
    override = app_id_overrides.get(app_id)
    if override:
        app_id = override
    return app_id


def get_app_icon_name(app_id: str | None = None, app_info: Application | None = None) -> str:
    app_id = app_id or app_info and app_info.id or ""
    app_id = get_app_id(app_id)
    icon = app_info and app_info.icon
    if not icon:
        icon = ignis_get_app_icon_name(app_id)
    if not icon:
        icon = app_icon_overrides.get(app_id)
    if not icon:
        icon = "image-missing-symbolic"
    return icon


def niri_action(action: str, args: Any = {}):
    niri = NiriService.get_default()
    if niri.is_available:
        return niri.send_command({"Action": {action: args}})


def launch_application(
    app: Application,
    files: list[str] | None = None,
    command_format: str | None = None,
    terminal_format: str | None = None,
):
    if not app.exec_string:
        return

    command = "%command%"
    # set key "Path" as cwd
    app_info: Gio.DesktopAppInfo = app.get_app()
    cwd = app_info.get_string("Path")
    if cwd:
        # cd xxx; %command%
        command = f"cd {shlex.quote(cwd)}; " + command

    format = terminal_format if app.is_terminal else command_format
    if format:
        # cd xxx; niri msg action spawn -- %command%
        command = command.replace("%command%", format)

    # pass file paths as arguments
    if files:
        files = [shlex.quote(file) for file in files]
        exec_string: str = app.exec_string
        for k, v in {"%f": files[0], "%F": " ".join(files), "%u": files[0], "%U": " ".join(files)}.items():
            exec_string = exec_string.replace(k, v)
        # cd xxx; niri msg action spawn -- nautilus --new-window filepath1 filepath2 ...
        command = command.replace("%command%", exec_string)

    app.launch(command_format=command, terminal_format=command)


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


def format_time_duration(seconds: int, minutes: int = 0, hours: int = 0) -> str:
    minutes += seconds // 60
    seconds %= 60
    hours += minutes // 60
    minutes %= 60
    if hours != 0:
        return "%d:%02d:%02d" % (hours, minutes, seconds)
    else:
        return "%d:%02d" % (minutes, seconds)


def connect_window(widget: Gtk.Widget, signal: str, callback: Callable[..., Any]):
    def on_realize(widget: Gtk.Widget):
        window = widget.get_ancestor(Widget.Window)
        if isinstance(window, Widget.Window):
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


def set_on_motion[Widget: Gtk.Widget](
    widget: Widget,
    enter: Callable[[Widget, float, float], Any] | None = None,
    leave: Callable[[Widget], Any] | None = None,
    motion: Callable[[Widget, float, float], Any] | None = None,
) -> Widget:
    controller = Gtk.EventControllerMotion()
    widget.add_controller(controller)

    if enter:
        controller.connect("enter", lambda _, x, y: enter(widget, x, y))
    if leave:
        controller.connect("leave", lambda _: leave(widget))
    if motion:
        controller.connect("motion", lambda _, x, y: motion(widget, x, y))

    return widget
