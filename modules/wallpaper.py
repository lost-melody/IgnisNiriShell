from gi.repository import Gtk
from ignis.widgets import Widget
from ignis.utils.monitor import get_monitor
from ignis.utils.debounce import debounce
from ignis.options import options
from .useroptions import user_options
from .utils import connect_option


class BlurredPicture(Gtk.Picture):
    __gtype_name__ = "IgnisBlurredPicture"

    def __init__(self, blur_radius: float = 0, **kvargs):
        self.__blur_radius = blur_radius
        super().__init__(**kvargs)

    def do_snapshot(self, snapshot: Gtk.Snapshot):
        snapshot.push_blur(self.blur_radius)
        Gtk.Picture.do_snapshot(self, snapshot)
        snapshot.pop()

    @property
    def blur_radius(self) -> float:
        return self.__blur_radius

    @blur_radius.setter
    def blur_radius(self, radius: float):
        self.__blur_radius = radius


class WallpaperWindow(Widget.Window):
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
            namespace=f"ignis_wallpaper_{"backdrop" if is_backdrop else "service"}_{monitor_idx}",
            monitor=monitor_idx,
            anchor=["top", "right", "bottom", "left"],
            exclusivity="ignore",
            layer="background",
            kb_mode="none",
            child=self.__picture,
        )

        self.__on_blur_radius_changed()
        self.__on_margin_changed()

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

    def __load_picture(self, *_):
        opts = options and options.wallpaper
        if opts:
            self.__picture.set_filename(opts.wallpaper_path)
