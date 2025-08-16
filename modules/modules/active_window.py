from gi.repository import Gtk
from ignis.services.hyprland import HyprlandService
from ignis.services.niri import NiriService

from ..useroptions import user_options
from ..utils import (
    get_app_icon_name,
    get_app_id,
    gtk_template,
    gtk_template_child,
    run_cmd_async,
    set_on_click,
    set_on_scroll,
)


@gtk_template("modules/activewindow")
class ActiveWindow(Gtk.CenterBox):
    __gtype_name__ = "NiriActiveWindow"

    box: Gtk.Box = gtk_template_child()
    icon: Gtk.Image = gtk_template_child()
    label: Gtk.Label = gtk_template_child()

    def __init__(self):
        self.__niri = NiriService.get_default()
        self.__hypr = HyprlandService.get_default()
        super().__init__()

        self.__options = user_options and user_options.activewindow

        set_on_click(
            self,
            left=lambda _: self.__on_click("LEFT"),
            right=lambda _: self.__on_click("RIGHT"),
            middle=lambda _: self.__on_click("MIDDLE"),
        )
        set_on_scroll(self, self.__on_scroll)

        if self.__niri.is_available:
            self.__niri.connect("notify::active-window", self.__on_change)

        if self.__hypr.is_available:
            self.__hypr.connect("notify::active-window", self.__on_change)

    @property
    def has_active_window(self) -> bool:
        if self.__niri.is_available:
            return self.__niri.active_window.id > 0
        elif self.__hypr.is_available:
            return self.__hypr.active_window.address != ""
        return False

    def __on_change(self, *_):
        icon: str | None = None
        label = ""
        tooltip: str | None = None

        if self.__niri.is_available:
            if self.has_active_window:
                niri_win = self.__niri.active_window
                icon = get_app_icon_name(niri_win.app_id)
                label = niri_win.title
                tooltip = f"{get_app_id(niri_win.app_id)} - {niri_win.title}"
            else:
                label = "niri"

        if self.__hypr.is_available:
            if self.has_active_window:
                hypr_win = self.__hypr.active_window
                icon = get_app_icon_name(hypr_win.class_name)
                label = hypr_win.title
                tooltip = f"{get_app_id(hypr_win.class_name)} - {hypr_win.title}"
            else:
                label = "Hyprland"

        self.icon.set_visible(self.has_active_window)
        self.icon.set_from_icon_name(icon)
        self.label.set_label(label)
        self.set_tooltip_text(tooltip)

    def __on_click(self, key: str = "LEFT"):
        if self.__options:
            cmd: str = ""
            match key:
                case "LEFT":
                    cmd = self.__options.on_click
                case "RIGHT":
                    cmd = self.__options.on_right_click
                case "MIDDLE":
                    cmd = self.__options.on_middle_click
            if cmd != "":
                run_cmd_async(cmd)

    def __on_scroll(self, _, dx: float, dy: float):
        if self.__options:
            cmd: str = ""
            if dx < 0:
                cmd = self.__options.on_scroll_left
            elif dx > 0:
                cmd = self.__options.on_scroll_right
            elif dy < 0:
                cmd = self.__options.on_scroll_up
            elif dy > 0:
                cmd = self.__options.on_scroll_down
            if cmd != "":
                run_cmd_async(cmd)
