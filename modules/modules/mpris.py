import asyncio

from gi.repository import GObject, Gtk
from ignis.services.mpris import ART_URL_CACHE_DIR, MprisPlayer, MprisService
from ignis.widgets import Box
from ignis.window_manager import WindowManager

from ..constants import WindowName
from ..utils import (
    clear_dir,
    format_time_duration,
    gtk_template,
    gtk_template_callback,
    gtk_template_child,
    set_on_click,
)

wm = WindowManager.get_default()


class Mpris(Box):
    __gtype_name__ = "Mpris"

    # clear mpris art images cache on startup
    clear_dir(ART_URL_CACHE_DIR)

    @gtk_template("modules/mpris-item")
    class MprisItem(Gtk.Box):
        __gtype_name__ = "MprisItem"

        avatar: Gtk.Image = gtk_template_child()
        title: Gtk.Inscription = gtk_template_child()
        artist: Gtk.Inscription = gtk_template_child()
        previous: Gtk.Button = gtk_template_child()
        next: Gtk.Button = gtk_template_child()
        pause: Gtk.Button = gtk_template_child()
        progress: Gtk.ProgressBar = gtk_template_child()

        def __init__(self, player: MprisPlayer):
            self.__player = player
            super().__init__()

            self.previous.set_sensitive(player.can_go_previous)
            self.next.set_sensitive(player.can_go_next)
            self.pause.set_sensitive(player.can_pause and player.can_play)

            flags = GObject.BindingFlags.SYNC_CREATE
            player.bind_property("art-url", self.avatar, "file", flags, transform_to=lambda _, s: s)
            player.bind_property("title", self.title, "text", flags, transform_to=lambda _, s: s or "Unknown Title")
            player.bind_property("title", self.title, "tooltip-text", flags, transform_to=lambda _, s: s)
            player.bind_property("artist", self.artist, "text", flags, transform_to=lambda _, s: s or "Unknown Artist")
            player.bind_property("artist", self.artist, "tooltip-text", flags, transform_to=lambda _, s: s)
            player.bind_property(
                "playback-status",
                self.pause,
                "icon-name",
                flags,
                transform_to=lambda _, s: (
                    "media-playback-pause-symbolic" if s == "Playing" else "media-playback-start-symbolic"
                ),
            )
            player.bind_property(
                "position",
                self.progress,
                "fraction",
                flags,
                transform_to=lambda _, p: p / player.length if player.length > 0 else 0,
            )
            player.bind_property(
                "position",
                self.progress,
                "tooltip-text",
                flags,
                transform_to=lambda _, p: (
                    f"{format_time_duration(p)} / {format_time_duration(player.length)}"
                    if player.length > 0
                    else "--:--"
                ),
            )
            player.connect("closed", self.__on_closed)

            set_on_click(self, right=lambda _: wm.toggle_window(WindowName.control_center.value))

        def __on_closed(self, *_):
            self.unparent()

        @gtk_template_callback
        def on_pause_clicked(self, *_):
            if self.__player.can_play and self.__player.can_pause:
                asyncio.create_task(self.__player.play_pause_async())

        @gtk_template_callback
        def on_previous_clicked(self, *_):
            if self.__player.can_go_previous:
                asyncio.create_task(self.__player.previous_async())

        @gtk_template_callback
        def on_next_clicked(self, *_):
            if self.__player.can_go_next:
                asyncio.create_task(self.__player.next_async())

    def __init__(self):
        self.__service = MprisService.get_default()
        super().__init__(vertical=True)
        self.__service.connect("player-added", self.__on_player_added)

    def __on_player_added(self, _, player: MprisPlayer):
        self.append(self.MprisItem(player))
