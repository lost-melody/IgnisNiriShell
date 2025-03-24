from typing import Callable
from gi.repository import Adw, Gio, GObject, Gtk
from ignis.widgets import Widget
from ignis.options import options
from ignis.options_manager import OptionsGroup
from .constants import WindowName
from .template import gtk_template, gtk_template_callback, gtk_template_child


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

        def __init__(self):
            self.__options = options
            super().__init__()
            self.__file_chooser = Gtk.FileDialog()

            if options is not None:
                if options.notifications is not None:
                    self.__bind_option(options.notifications, "dnd", self.dnd, "active")
                    self.__bind_option(
                        options.notifications,
                        "popup_timeout",
                        self.popup_timeout,
                        "value",
                        transform_from=lambda f: round(f),
                    )
                    self.__bind_option(
                        options.notifications,
                        "max_popups_count",
                        self.max_popups,
                        "value",
                        transform_from=lambda f: round(f),
                    )

                if options.recorder is not None:
                    self.__bind_option(
                        options.recorder, "bitrate", self.bitrate, "value", transform_from=lambda f: round(f)
                    )
                    self.__bind_option(options.recorder, "default_filename", self.recorder_filename, "text")

                if options.wallpaper is not None:
                    self.__bind_option(
                        options.wallpaper,
                        "wallpaper_path",
                        self.wallpaper_path,
                        "subtitle",
                        flags=GObject.BindingFlags.DEFAULT,
                    )

        def __bind_option(
            self,
            group: OptionsGroup,
            option: str,
            target: GObject.Object,
            target_property: str,
            flags: GObject.BindingFlags = GObject.BindingFlags.BIDIRECTIONAL,
            transform_to: Callable | None = None,
            transform_from: Callable | None = None,
        ):
            binding = group.bind(option, transform_to)
            source: GObject.Object = binding.target
            source_property: str = binding.target_properties[0]

            # target.property = transform_to(group.option)
            def on_option_changed(*_):
                value = source.get_property(source_property.replace("-", "_"))
                if transform_to:
                    value = transform_to(value)
                if target.get_property(target_property) != value:
                    target.set_property(target_property, value)

            source.connect(f"notify::{source_property}", on_option_changed)
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

        @gtk_template_callback
        def on_wallpaper_select_clicked(self, *_):
            group = self.__options and self.__options.wallpaper
            if group:

                def on_file_open(file_chooser: Gtk.FileDialog, res: Gio.AsyncResult, *_):
                    file = file_chooser.open_finish(res)
                    if file:
                        group.wallpaper_path = file.get_path()

                window: Gtk.Window | None = self.get_ancestor(Gtk.Window)  # type: ignore
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
