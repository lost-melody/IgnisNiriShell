from gi.repository import Gtk
from ignis.options import options
from ignis.services.niri import NiriService
from ignis.utils.monitor import get_monitor
from ignis.widgets import Window

from ..useroptions import user_options
from ..utils import connect_option
from ..widgets import BlurredPicture

niri = NiriService.get_default()


class WallpaperWindow(Window):
    __gtype_name__ = "IgnisBackdropWallpaper"

    def __init__(self, monitor_idx: int, is_backdrop: bool = False):
        self.__is_backdrop = is_backdrop
        self.__picture = BlurredPicture()
        self.__picture.set_content_fit(Gtk.ContentFit.COVER)

        monitor = get_monitor(monitor_idx)
        if monitor:
            geometry = monitor.get_geometry()
            self.__picture.set_size_request(geometry.width, geometry.height)

        super().__init__(
            namespace=f"ignis_wallpaper_{'backdrop' if is_backdrop else 'service'}_{monitor_idx}",
            monitor=monitor_idx,
            anchor=["top", "right", "bottom", "left"],
            exclusivity="ignore",
            layer="background",
            kb_mode="none",
            child=self.__picture,
        )

        if is_backdrop:
            self.add_css_class("wallpaper-backdrop")
        else:
            self.add_css_class("wallpaper")

        self.__on_overview_opened()
        self.__on_blur_radius_changed()
        self.__on_margin_changed()

        if niri.is_available:
            niri.connect("notify::overview-opened", self.__on_overview_opened)

        if options and options.wallpaper:
            connect_option(options.wallpaper, "wallpaper_path", self.__load_picture)

        if user_options and user_options.wallpaper:
            if is_backdrop:
                connect_option(user_options.wallpaper, "backdrop_blur_radius", self.__on_blur_radius_changed)
                connect_option(user_options.wallpaper, "backdrop_bottom_margin", self.__on_margin_changed)
            else:
                connect_option(user_options.wallpaper, "blur_radius", self.__on_blur_radius_changed)
                connect_option(user_options.wallpaper, "bottom_margin", self.__on_margin_changed)

    def __on_blur_radius_changed(self, *_):
        opts = user_options and user_options.wallpaper
        if opts:
            self.__picture.blur_radius = opts.backdrop_blur_radius if self.__is_backdrop else opts.blur_radius
        self.__load_picture()

    def __on_margin_changed(self, *_):
        opts = user_options and user_options.wallpaper
        if opts:
            self.set_margin_bottom(opts.backdrop_bottom_margin if self.__is_backdrop else opts.bottom_margin)

    def __on_overview_opened(self, *_):
        css_class = "wallpaper-overview"
        if niri.overview_opened:
            self.add_css_class(css_class)
        else:
            self.remove_css_class(css_class)

    def __load_picture(self, *_):
        opts = options and options.wallpaper
        if opts:
            self.__picture.set_filename(opts.wallpaper_path)
