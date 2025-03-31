from gi.repository import Adw, Gio, GLib, GObject, Gtk
from ignis.widgets import Widget
from ignis.options import options
from .constants import WindowName
from .template import gtk_template, gtk_template_callback, gtk_template_child
from .useroptions import user_options
from .utils import bind_option


class Preferences(Widget.RegularWindow):
    __gtype_name__ = "Preferences"

    @gtk_template("preferences")
    class View(Gtk.Box):
        __gtype_name__ = "PreferencesView"

        dnd: Adw.SwitchRow = gtk_template_child()
        popup_timeout: Adw.SpinRow = gtk_template_child()
        max_popups: Adw.SpinRow = gtk_template_child()
        bitrate: Adw.SpinRow = gtk_template_child()
        recorder_filename: Adw.EntryRow = gtk_template_child()
        wallpaper_path: Adw.ActionRow = gtk_template_child()
        command_format: Adw.EntryRow = gtk_template_child()
        terminal_format: Adw.EntryRow = gtk_template_child()
        on_active_click: Adw.EntryRow = gtk_template_child()
        on_active_right_click: Adw.EntryRow = gtk_template_child()
        on_active_middle_click: Adw.EntryRow = gtk_template_child()
        on_active_scroll_up: Adw.EntryRow = gtk_template_child()
        on_active_scroll_down: Adw.EntryRow = gtk_template_child()
        on_active_scroll_left: Adw.EntryRow = gtk_template_child()
        on_active_scroll_right: Adw.EntryRow = gtk_template_child()
        dock_monitor_only: Adw.SwitchRow = gtk_template_child()
        dock_workspace_only: Adw.SwitchRow = gtk_template_child()
        dock_conceal_delay: Adw.SpinRow = gtk_template_child()

        def __init__(self):
            super().__init__()
            self.__file_chooser = Gtk.FileDialog()

            self.__bind_ignis_options()
            self.__bind_user_options()

        def __bind_ignis_options(self):
            if not options:
                return

            if options.notifications is not None:
                bind_option(options.notifications, "dnd", self.dnd, "active")
                bind_option(
                    options.notifications,
                    "popup_timeout",
                    self.popup_timeout,
                    "value",
                    transform_from=lambda f: round(f),
                )
                bind_option(
                    options.notifications,
                    "max_popups_count",
                    self.max_popups,
                    "value",
                    transform_from=lambda f: round(f),
                )

            if options.recorder is not None:
                bind_option(options.recorder, "bitrate", self.bitrate, "value", transform_from=lambda f: round(f))
                bind_option(options.recorder, "default_filename", self.recorder_filename, "text")

            if options.wallpaper is not None:
                bind_option(
                    options.wallpaper,
                    "wallpaper_path",
                    self.wallpaper_path,
                    "subtitle",
                    flags=GObject.BindingFlags.DEFAULT,
                )

        def __bind_user_options(self):
            if not user_options:
                return

            if user_options.applauncher:
                bind_option(user_options.applauncher, "command_format", self.command_format, "text")
                bind_option(user_options.applauncher, "terminal_format", self.terminal_format, "text")

            if user_options.activewindow:
                bind_option(user_options.activewindow, "on_click", self.on_active_click, "text")
                bind_option(user_options.activewindow, "on_right_click", self.on_active_right_click, "text")
                bind_option(user_options.activewindow, "on_middle_click", self.on_active_middle_click, "text")
                bind_option(user_options.activewindow, "on_scroll_up", self.on_active_scroll_up, "text")
                bind_option(user_options.activewindow, "on_scroll_down", self.on_active_scroll_down, "text")
                bind_option(user_options.activewindow, "on_scroll_left", self.on_active_scroll_left, "text")
                bind_option(user_options.activewindow, "on_scroll_right", self.on_active_scroll_right, "text")

            if user_options.appdock:
                bind_option(user_options.appdock, "monitor_only", self.dock_monitor_only, "active")
                bind_option(user_options.appdock, "workspace_only", self.dock_workspace_only, "active")
                bind_option(user_options.appdock, "conceal_delay", self.dock_conceal_delay, "value")

        @gtk_template_callback
        def on_wallpaper_select_clicked(self, *_):
            group = options and options.wallpaper
            if group:

                def on_file_open(file_chooser: Gtk.FileDialog, res: Gio.AsyncResult, *_):
                    try:
                        file = file_chooser.open_finish(res)
                    except GLib.Error:
                        return
                    if file:
                        group.wallpaper_path = file.get_path()

                window = self.get_ancestor(Gtk.Window)
                if isinstance(window, Gtk.Window):
                    self.__file_chooser.open(parent=window, callback=on_file_open)

    def __init__(self):
        super().__init__(
            namespace=WindowName.preferences.value,
            default_width=512,
            default_height=384,
            hide_on_close=True,
            visible=False,
        )

        self.__view = self.View()
        self.set_child(self.__view)
