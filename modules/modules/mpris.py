import asyncio

from gi.repository import GObject, Gtk
from ignis.services.mpris import ART_URL_CACHE_DIR, MprisPlayer, MprisService
from ignis.widgets import Box
from ignis.window_manager import WindowManager

from ..constants import WindowName
from ..utils import SpecsBase, clear_dir, format_time_duration, gtk_template, gtk_template_child, set_on_click

wm = WindowManager.get_default()


class Mpris(Box):
    __gtype_name__ = "Mpris"

    # clear mpris art images cache on startup
    clear_dir(ART_URL_CACHE_DIR)

    @gtk_template("modules/mpris-item")
    class MprisItem(Gtk.Box, SpecsBase):
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
            SpecsBase.__init__(self)

            self.previous.set_sensitive(player.can_go_previous)
            self.next.set_sensitive(player.can_go_next)
            self.pause.set_sensitive(player.can_pause and player.can_play)

            self.signal(self.previous, "clicked", self.__on_previous_clicked)
            self.signal(self.next, "clicked", self.__on_next_clicked)
            self.signal(self.pause, "clicked", self.__on_pause_clicked)
            self.signal(player, "closed", self.__on_closed)

            flags = GObject.BindingFlags.SYNC_CREATE
            self.bind(player, "art-url", self.avatar, "file", flags, transform_to=lambda _, s: s)
            self.bind(player, "title", self.title, "text", flags, transform_to=lambda _, s: s or "Unknown Title")
            self.bind(player, "title", self.title, "tooltip-text", flags, transform_to=lambda _, s: s)
            self.bind(player, "artist", self.artist, "text", flags, transform_to=lambda _, s: s or "Unknown Artist")
            self.bind(player, "artist", self.artist, "tooltip-text", flags, transform_to=lambda _, s: s)
            self.bind(
                player,
                "playback-status",
                self.pause,
                "icon-name",
                flags,
                transform_to=lambda _, s: (
                    "media-playback-pause-symbolic" if s == "Playing" else "media-playback-start-symbolic"
                ),
            )
            self.bind(
                player,
                "position",
                self.progress,
                "fraction",
                flags,
                transform_to=lambda _, p: p / player.length if player.length > 0 else 0,
            )
            self.bind(
                player,
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

            set_on_click(self, right=lambda _: wm.toggle_window(WindowName.control_center.value))

        def do_dispose(self):
            self.clear_specs()
            self.dispose_template(self.__class__)
            super().do_dispose()  # type: ignore

        def __on_closed(self, *_):
            self.unparent()
            self.run_dispose()

        def __on_pause_clicked(self, *_):
            if self.__player.can_play and self.__player.can_pause:
                asyncio.create_task(self.__player.play_pause_async())

        def __on_previous_clicked(self, *_):
            if self.__player.can_go_previous:
                asyncio.create_task(self.__player.previous_async())

        def __on_next_clicked(self, *_):
            if self.__player.can_go_next:
                asyncio.create_task(self.__player.next_async())

    def __init__(self):
        self.__service = MprisService.get_default()
        super().__init__(vertical=True)
        self.__service.connect("player-added", self.__on_player_added)

    def __on_player_added(self, _, player: MprisPlayer):
        self.append(self.MprisItem(player))
