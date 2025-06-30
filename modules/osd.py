from gi.repository import Gtk
from ignis.services.audio import AudioService, Stream
from ignis.services.backlight import BacklightDevice, BacklightService
from ignis.services.hyprland import HyprlandService
from ignis.services.niri import NiriService
from ignis.utils import Timeout
from .constants import WindowName
from .services import FcitxStateService, KeyboardLedsService
from .template import gtk_template, gtk_template_child
from .useroptions import user_options
from .widgets import RevealerWindow


class OnscreenDisplay(RevealerWindow):
    __gtype_name__ = "OnscreenDisplay"

    @gtk_template("osd")
    class View(Gtk.Box):
        __gtype_name__ = "OnscreenDisplayView"

        page_indicator = "indicator"
        page_indicator_text = "indicator-text"
        page_progress = "progress"

        revealer: Gtk.Revealer = gtk_template_child()
        title: Gtk.Label = gtk_template_child()
        stack: Gtk.Stack = gtk_template_child()
        indicator: Gtk.Image = gtk_template_child()
        indicator_text: Gtk.Label = gtk_template_child()
        icon: Gtk.Image = gtk_template_child()
        progress: Gtk.ProgressBar = gtk_template_child()
        label: Gtk.Label = gtk_template_child()

        def __init__(self):
            self.__audio = AudioService.get_default()
            self.__backlight = BacklightService.get_default()
            self.__fcitx = FcitxStateService.get_default()
            self.__hypr = HyprlandService.get_default()
            self.__leds = KeyboardLedsService.get_default()
            self.__niri = NiriService.get_default()
            super().__init__()

            for stream in [self.__audio.speaker, self.__audio.microphone]:
                stream.connect("notify::volume", self.__on_stream_changed)
                stream.connect("notify::is-muted", self.__on_stream_changed)

            self.__backlight_ids: list[tuple[BacklightDevice, int]] = []
            self.__backlight.connect("notify::devices", self.__on_backlight_devices_changed)
            self.__on_backlight_devices_changed()

            self.__fcitx.kimpanel.connect("notify::show-aux", self.__on_fcitx5_show_aux)

            self.__leds.connect("notify::capslock", self.__on_capslock_changed)

            if self.__hypr.is_available:
                self.__hypr.main_keyboard.connect("notify::layout", self.__on_keyboard_layout_changed)
                self.__hypr.main_keyboard.connect("notify::variant", self.__on_keyboard_layout_changed)
            if self.__niri.is_available:
                self.__niri.keyboard_layouts.connect("notify::current-name", self.__on_keyboard_layout_changed)

        def __display(self):
            window = self.get_ancestor(OnscreenDisplay)
            if isinstance(window, OnscreenDisplay):
                window.display_osd()

        def __display_indicator(self, title: str, icon: str):
            self.stack.set_visible_child_name(self.page_indicator)
            self.title.set_label(title)
            self.indicator.set_from_icon_name(icon)
            self.__display()

        def __display_indicator_text(self, title: str, indicator_text: str):
            self.stack.set_visible_child_name(self.page_indicator_text)
            self.title.set_label(title)
            self.indicator_text.set_label(indicator_text)
            self.__display()

        def __display_progress(self, title: str, icon: str, progress: float, max_progress: float):
            self.stack.set_visible_child_name(self.page_progress)
            self.title.set_label(title)
            self.icon.set_from_icon_name(icon)
            self.progress.set_fraction(progress / max_progress)
            self.label.set_label(f"{round(progress)}/{round(max_progress)}")
            self.__display()

        def __on_capslock_changed(self, *_):
            enabled = self.__leds.capslock
            self.__display_indicator("Caps Lock", f"capslock-{"enabled" if enabled else "disabled"}-symbolic")

        def __on_fcitx5_show_aux(self, *_):
            if not self.__fcitx.kimpanel.show_aux:
                return
            prop = self.__fcitx.kimpanel.fcitx_im
            if prop.icon:
                self.__display_indicator(prop.text, prop.icon)
            else:
                self.__display_indicator_text(prop.text, prop.label)

        def __on_keyboard_layout_changed(self, *_):
            label = ""
            if self.__hypr.is_available:
                label = f"{self.__hypr.main_keyboard.layout}-{self.__hypr.main_keyboard.variant}"
            if self.__niri.is_available:
                label = self.__niri.keyboard_layouts.current_name
            self.__display_indicator(label, "input-keyboard-symbolic")

        def __on_stream_changed(self, stream: Stream, *_):
            self.__display_progress(stream.description, stream.icon_name, stream.volume, 100)

        def __on_backlight_changed(self, device: BacklightDevice, *_):
            self.__display_progress(
                device.device_name, "display-brightness-symbolic", device.brightness, device.max_brightness
            )

        def __on_backlight_devices_changed(self, *_):
            for device, id in self.__backlight_ids:
                device.disconnect(id)
            self.__backlight_ids.clear()

            devices = self.__backlight.devices
            for device in devices:
                id = device.connect("notify::brightness", self.__on_backlight_changed)
                self.__backlight_ids.append((device, id))

    def __init__(self):
        self.__view = self.View()
        self.__options = user_options and user_options.osd
        super().__init__(
            namespace=WindowName.osd.value,
            anchor=["bottom"],
            margin_bottom=64,
            visible=False,
            revealer=self.__view.revealer,
        )
        self.add_css_class("rounded")
        self.add_css_class("transparent")
        self.set_child(self.__view)

        self.__defer_hide: Timeout | None = None
        self.__startup: bool | None = True

        def unsilent(*_):
            self.__startup = None

        Timeout(ms=1000, target=unsilent)

    def display_osd(self):
        if self.__startup:
            return

        if self.__defer_hide:
            self.__defer_hide.cancel()

        timeout = 3000
        if self.__options:
            timeout = self.__options.timeout

        self.__defer_hide = Timeout(ms=timeout, target=self.__hide_osd)
        self.set_visible(True)

    def __hide_osd(self, *_):
        self.__defer_hide = None
        self.set_visible(False)
