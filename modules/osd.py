from gi.repository import Gtk
from ignis.services.audio import AudioService, Stream
from ignis.services.backlight import BacklightDevice, BacklightService
from ignis.utils.timeout import Timeout
from .constants import WindowName
from .services import KeyboardLedsService
from .template import gtk_template, gtk_template_child
from .useroptions import user_options
from .widgets import RevealerWindow


class OnscreenDisplay(RevealerWindow):
    __gtype_name__ = "OnscreenDisplay"

    @gtk_template("osd")
    class View(Gtk.Box):
        __gtype_name__ = "OnscreenDisplayView"

        page_indicator = "indicator"
        page_progress = "progress"

        revealer: Gtk.Revealer = gtk_template_child()
        title: Gtk.Label = gtk_template_child()
        stack: Gtk.Stack = gtk_template_child()
        indicator: Gtk.Image = gtk_template_child()
        icon: Gtk.Image = gtk_template_child()
        progress: Gtk.ProgressBar = gtk_template_child()
        label: Gtk.Label = gtk_template_child()

        def __init__(self):
            self.__audio = AudioService.get_default()
            self.__backlight = BacklightService.get_default()
            self.__leds = KeyboardLedsService.get_default()
            super().__init__()

            for stream in [self.__audio.speaker, self.__audio.microphone]:
                stream.connect("notify::volume", self.__on_stream_changed)
                stream.connect("notify::is-muted", self.__on_stream_changed)

            self.__backlight_ids: list[tuple[BacklightDevice, int]] = []
            self.__backlight.connect("notify::devices", self.__on_backlight_devices_changed)
            self.__on_backlight_devices_changed()

            self.__leds.connect("notify::capslock", self.__on_capslock_changed)

        def __display(self):
            window = self.get_ancestor(OnscreenDisplay)
            if isinstance(window, OnscreenDisplay):
                window.display_osd()

        def __on_capslock_changed(self, *_):
            enabled = self.__leds.capslock
            self.stack.set_visible_child_name(self.page_indicator)
            self.__display()
            self.title.set_label("Caps Lock")
            self.indicator.set_from_icon_name(f"capslock-{"enabled" if enabled else "disabled"}-symbolic")

        def __on_stream_changed(self, stream: Stream, *_):
            self.stack.set_visible_child_name(self.page_progress)
            self.__display()
            self.title.set_label(stream.description)
            self.icon.set_from_icon_name(stream.icon_name)
            self.progress.set_fraction(stream.volume / 100)
            self.label.set_label(f"{round(stream.volume)}/100")

        def __on_backlight_changed(self, device: BacklightDevice, *_):
            self.stack.set_visible_child_name(self.page_progress)
            self.__display()
            self.title.set_label(device.device_name)
            self.icon.set_from_icon_name("display-brightness-symbolic")
            self.progress.set_fraction(device.brightness / device.max_brightness)
            self.label.set_label(f"{round(device.brightness)}/{round(device.max_brightness)}")

        def __on_backlight_devices_changed(self, *_):
            for device, id in self.__backlight_ids:
                device.disconnect(id)
            self.__backlight_ids.clear()

            devices: list[BacklightDevice] = self.__backlight.devices
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
