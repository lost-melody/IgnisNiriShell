from typing import Any, Callable

from gi.repository import Gio, Gtk
from ignis.services.hyprland import HyprlandService
from ignis.services.niri import NiriService
from ignis.services.upower import UPowerDevice, UPowerService
from ignis.window_manager import WindowManager

from ..constants import WindowName
from ..utils import (
    SpecsBase,
    get_widget_monitor_id,
    gtk_template,
    gtk_template_child,
    niri_action,
    run_cmd_async,
    set_on_click,
)

wm = WindowManager.get_default()


@gtk_template("modules/batteries")
class Batteries(Gtk.Box):
    __gtype_name__ = "IgnisBatteries"

    @gtk_template("modules/batteries-item")
    class Item(Gtk.Box, SpecsBase):
        __gtype_name__ = "IgnisBatteriesItem"

        icon: Gtk.Image = gtk_template_child()
        label: Gtk.Label = gtk_template_child()

        def __init__(self, battery: UPowerDevice):
            super().__init__()
            SpecsBase.__init__(self)

            self.__battery = battery
            self.__percent: int = 0

            self.signal(battery, "removed", self.__on_removed)
            self.signal(battery, "notify::percent", self.__on_change)
            self.signal(battery, "notify::charging", self.__on_change)

            self.__on_change()

        def do_dispose(self):
            self.clear_specs()
            self.dispose_template(self.__class__)
            super().do_dispose()  # type: ignore

        def __on_removed(self, *_):
            self.unparent()
            self.run_dispose()

        def __on_change(self, *_):
            time_remaining = self.__battery.time_remaining // 60
            self.set_tooltip_text(f"{time_remaining} minutes" if time_remaining != 0 else "full")

            prev_percent = self.__percent
            self.__percent = int(self.__battery.percent)
            for threshold in (10, 20, 30):
                if self.__percent <= threshold < prev_percent:
                    self.__notify()
                    break

            self.label.set_label(f"{self.__percent}")
            level = round(self.__percent, -1)
            charging = "-charging" if self.__battery.charging else ""
            icon_name = f"battery-level-{level}{charging}-symbolic"
            self.icon.set_from_icon_name(icon_name)

        def __notify(self):
            monitor_id = get_widget_monitor_id(self)
            if monitor_id is not None and monitor_id != 0:
                return

            run_cmd_async(
                "notify-send -t %d --icon '%s' '%s' '%s'"
                % (30 * 1000, "battery-caution-symbolic", "LOW POWER", f"battery level: {self.__percent}%")
            )

    stack: Gtk.Stack = gtk_template_child()
    box: Gtk.Box = gtk_template_child()
    popover: Gtk.PopoverMenu = gtk_template_child()

    def __init__(self):
        self.__service = UPowerService.get_default()
        super().__init__()

        self.__group = Gio.SimpleActionGroup()
        self.insert_action_group("power", self.__group)

        self.__add_action("lock", lambda: run_cmd_async("loginctl lock-session"))
        self.__add_action("suspend", lambda: run_cmd_async("systemctl suspend"))
        self.__add_action("shutdown", lambda: run_cmd_async("systemctl poweroff"))
        self.__add_action("reboot", lambda: run_cmd_async("systemctl reboot"))
        self.__add_action("logout", self.__logout_session)

        set_on_click(
            self, left=lambda s: s.popover.popup(), right=lambda _: wm.toggle_window(WindowName.control_center.value)
        )

        self.__service.connect("battery_added", self.__on_battery_added)
        self.__service.connect("notify::batteries", self.__on_change)
        self.__on_change()

    @classmethod
    def __logout_session(cls):
        niri = NiriService.get_default()
        if niri.is_available:
            niri_action("Quit", {"skip_confirmation": True})

        hypr = HyprlandService.get_default()
        if hypr.is_available:
            run_cmd_async("hyprctl dispatch exit")

    def __add_action(self, name: str, callback: Callable[[], Any]):
        def do_action(*_):
            callback()

        action = Gio.SimpleAction(name=name)
        action.connect("activate", do_action)
        self.__group.add_action(action)

    def __on_battery_added(self, _, battery: UPowerDevice):
        self.box.append(self.Item(battery))

    def __on_change(self, *_):
        self.stack.set_visible_child_name("batteries" if len(self.__service.batteries) != 0 else "no-batteries")
