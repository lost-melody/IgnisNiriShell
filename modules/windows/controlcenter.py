import math
import urllib.parse
from asyncio import create_task
from datetime import datetime
from typing import Any

from gi.repository import Adw, Gio, GLib, Gtk
from ignis.options import options
from ignis.services.audio import AudioService, Stream
from ignis.services.backlight import BacklightDevice, BacklightService
from ignis.services.bluetooth import BluetoothDevice, BluetoothService
from ignis.services.network import NetworkService
from ignis.services.notifications import NOTIFICATIONS_IMAGE_DATA, Notification, NotificationAction, NotificationService
from ignis.services.recorder import RecorderConfig, RecorderService
from ignis.widgets import Icon, Window
from ignis.window_manager import WindowManager

from ..constants import AudioStreamType, WindowName
from ..useroptions import user_options
from ..utils import (
    SpecsBase,
    WeakMethod,
    clear_dir,
    connect_option,
    connect_window,
    escape_pango_markup,
    GProperty,
    gtk_template,
    gtk_template_callback,
    gtk_template_child,
    niri_action,
    run_cmd_async,
    set_on_click,
    verify_pango_markup,
)
from ..variables import caffeine_state
from ..widgets import RevealerWindow
from .backdrop import overlay_window

wm = WindowManager.get_default()


@gtk_template("controlcenter/audio-group")
class AudioControlGroup(Gtk.Box):
    __gtype_name__ = "AudioControlGroup"

    caption: Gtk.Box = gtk_template_child()
    icon: Gtk.Image = gtk_template_child()
    scale: Gtk.Scale = gtk_template_child()
    label: Gtk.Label = gtk_template_child()
    arrow: Gtk.Image = gtk_template_child()
    revealer: Gtk.Revealer = gtk_template_child()
    list_box: Gtk.ListBox = gtk_template_child()

    @gtk_template("controlcenter/audio-stream")
    class AudioControlStream(Gtk.ListBoxRow, SpecsBase):
        __gtype_name__ = "AudioControlStream"

        icon: Gtk.Image = gtk_template_child()
        inscription: Gtk.Inscription = gtk_template_child()

        def __init__(self, stream: Stream, stream_type: AudioStreamType):
            self.__service = AudioService.get_default()
            self._stream = stream
            self._stream_type = stream_type
            self._default: Stream | None = None
            super().__init__()
            SpecsBase.__init__(self)

            set_on_click(self.icon, WeakMethod(self.__on_mute_clicked))
            set_on_click(self, self.__class__.__on_clicked)

            self.signal(stream, "removed", self.__on_removed)
            self.signal(stream, "notify::name", self.__on_stream_changed)
            self.signal(stream, "notify::icon-name", self.__on_stream_changed)
            self.signal(stream, "notify::is_default", self.__on_default_changed)
            self.__on_stream_changed()

            match stream_type:
                case AudioStreamType.speaker:
                    self._default = self.__service.speaker
                case AudioStreamType.microphone:
                    self._default = self.__service.microphone
            if self._default:
                self.signal(self._default, "notify::id", self.__on_default_changed)
            self.__on_default_changed()

        def do_dispose(self):
            self.clear_specs()
            self.dispose_template(self.__class__)
            super().do_dispose()  # type: ignore

        @property
        def stream(self) -> Stream:
            return self._stream

        def __on_removed(self, *_):
            widget = self.get_ancestor(AudioControlGroup)
            if isinstance(widget, AudioControlGroup):
                widget.on_stream_removed(self.stream)

        def __on_stream_changed(self, *_):
            icon = self._stream.icon_name
            description = self._stream.description
            self.icon.set_from_icon_name(icon)
            self.inscription.set_text(description)
            self.inscription.set_tooltip_text(description)

        def __on_default_changed(self, *_):
            if not self._default:
                return
            if self._stream.id == self._default.id:
                self.icon.add_css_class("accent")
            else:
                self.icon.remove_css_class("accent")

        def __on_mute_clicked(self, *_):
            self._stream.is_muted = not self._stream.is_muted

        def __on_clicked(self):
            match self._stream_type:
                case AudioStreamType.speaker:
                    self.__service.speaker = self._stream
                case AudioStreamType.microphone:
                    self.__service.microphone = self._stream

    def __init__(self, stream_type: AudioStreamType):
        self.__service = AudioService.get_default()
        self._stream_type = stream_type
        self._default: Stream | None = None
        self._streams = Gio.ListStore()

        super().__init__()
        self.list_box.bind_model(model=self._streams, create_widget_func=lambda item: item)

        set_on_click(self.icon, left=self.__on_mute_clicked)
        set_on_click(self.caption, left=self.__on_caption_clicked)
        connect_window(self, "notify::visible", self.__on_window_visible_change)

        match stream_type:
            case AudioStreamType.speaker:
                self._default = self.__service.speaker
                self.__service.connect("speaker_added", self.__on_stream_added)
            case AudioStreamType.microphone:
                self._default = self.__service.microphone
                self.__service.connect("microphone_added", self.__on_stream_added)

        if self._default is not None:
            self._default.connect("notify::description", self.__on_volume_changed)
            self._default.connect("notify::icon-name", self.__on_volume_changed)
            self._default.connect("notify::volume", self.__on_volume_changed)
            self.__on_volume_changed()

    def __on_window_visible_change(self, window: Window, _):
        if not window.get_visible():
            self.revealer.set_reveal_child(False)

    def __on_volume_changed(self, *_):
        if self._default is None:
            return

        description = self._default.description
        if description != self.caption.get_tooltip_text():
            self.caption.set_tooltip_text(description)

        icon_name = self._default.icon_name
        if icon_name != self.icon.get_icon_name():
            self.icon.set_from_icon_name(self._default.icon_name)

        volume = round(self._default.volume)
        if volume != round(self.scale.get_value()):
            self.scale.set_value(volume)

    def __on_stream_added(self, _, stream: Stream):
        self._streams.append(self.AudioControlStream(stream, self._stream_type))

    def on_stream_removed(self, stream: Stream):
        found, pos = self._streams.find_with_equal_func(stream, lambda item, stream: item.stream == stream)
        if found:
            item = self._streams.get_item(pos)
            self._streams.remove(pos)
            if isinstance(item, self.AudioControlStream):
                GLib.idle_add(lambda *_: item.run_dispose())

    def __on_mute_clicked(self, *_):
        if self._default is None:
            return

        self._default.is_muted = not self._default.is_muted

    def __on_caption_clicked(self, *_):
        revealed = not self.revealer.get_reveal_child()
        self.revealer.set_reveal_child(revealed)
        if revealed:
            self.arrow.add_css_class("rotate-icon-90")
        else:
            self.arrow.remove_css_class("rotate-icon-90")

    @gtk_template_callback
    def on_scale_value_changed(self, *_):
        if self._default is None:
            return

        volume = round(self.scale.get_value())
        self.label.set_label(f"{volume}")
        if volume != round(self._default.volume):
            self._default.volume = volume
            if self._default.is_muted:
                self._default.is_muted = False


class AudioControlGroupSpeaker(Gtk.Box):
    __gtype_name__ = "AudioControlGroupSpeaker"

    def __init__(self):
        super().__init__()
        self.append(AudioControlGroup(AudioStreamType.speaker))


class AudioControlGroupMicrophone(Gtk.Box):
    __gtype_name__ = "AudioControlGroupMicrophone"

    def __init__(self):
        super().__init__()
        self.append(AudioControlGroup(AudioStreamType.microphone))


@gtk_template("controlcenter/backlight-group")
class BacklightControlGroup(Gtk.ListBox):
    __gtype_name__ = "BacklightControlGroup"

    @gtk_template("controlcenter/backlight-item")
    class Item(Gtk.ListBoxRow, SpecsBase):
        __gtype_name__ = "BacklightControlItem"

        scale: Gtk.Scale = gtk_template_child()
        label: Gtk.Label = gtk_template_child()

        def __init__(self, device: BacklightDevice):
            self._device = device
            super().__init__()
            SpecsBase.__init__(self)

            adjustment = self.scale.get_adjustment()
            adjustment.set_upper(math.ceil(device.max_brightness))
            self.signal(self.scale, "value-changed", self.__on_scale_value_changed)
            self.signal(device, "notify::brightness", self.__on_brightness_changed)

        def do_dispose(self):
            self.clear_specs()
            self.dispose_template(self.__class__)
            super().do_dispose()  # type: ignore

        @GProperty(type=BacklightDevice)
        def device(self) -> BacklightDevice | None:
            return self._device

        def __on_scale_value_changed(self, *_):
            if not self._device:
                return

            name = self._device.device_name
            value = round(self.scale.get_value())
            upper = round(self.scale.get_adjustment().get_upper())
            self.label.set_label(f"{value}")
            self.set_tooltip_text(f"{name}\nbrightness: {value} / {upper}")
            if value != self._device.brightness:
                create_task(self._device.set_brightness_async(round(self.scale.get_value())))

        def __on_brightness_changed(self, *_):
            if self._device:
                self.scale.set_value(self._device.brightness)

    def __init__(self):
        self.__service = BacklightService.get_default()
        super().__init__()

        self.__list = Gio.ListStore()
        self.bind_model(self.__list, lambda i: i)

        self.__service.connect("notify::devices", self.__on_devices_changed)
        self.__on_devices_changed()

    def __on_devices_changed(self, *_):
        items = list(self.__list)
        self.__list.remove_all()
        for item in items:
            if isinstance(item, self.Item):
                item.run_dispose()

        for device in self.__service.devices:
            self.__list.append(self.Item(device))


@gtk_template("controlcenter/switchpill")
class ControlSwitchPill(Gtk.Box):
    __gtype_name__ = "ControlSwitchPill"

    pill: Gtk.Box = gtk_template_child()
    icon: Gtk.Image = gtk_template_child()
    title: Gtk.Inscription = gtk_template_child()
    subtitle: Gtk.Inscription = gtk_template_child()
    action: Gtk.Button = gtk_template_child()

    def __init__(self):
        super().__init__()

    def set_title(self, title: str | None = None):
        self.title.set_text(title)

    def set_subtitle(self, subtitle: str | None = None):
        self.subtitle.set_text(subtitle)

    def set_icon(self, icon_name: str | None = None):
        self.icon.set_from_icon_name(icon_name)

    def set_style_accent(self, accent: bool):
        if accent:
            self.add_css_class("accent-bg")
        else:
            self.remove_css_class("accent-bg")

    def set_style_warning(self, warning: bool):
        if warning:
            self.pill.add_css_class("warning-bg")
        else:
            self.pill.remove_css_class("warning-bg")


class ControlSwitchCmd(Gtk.Box):
    __gtype_name__ = "ControlSwitchCmd"

    def __init__(self):
        self._enabled: bool = False
        self._status_cmd: str = ""
        self._enable_cmd: str = ""
        self._disable_cmd: str = ""
        self._action_icon: str = ""
        self._action_cmd: str = ""
        super().__init__()

        self.__pill = ControlSwitchPill()
        self.append(self.__pill)
        set_on_click(self, self.__on_clicked)

    @GProperty(type=str)
    def title(self) -> str:
        return self.__pill.title.get_text() or ""

    @title.setter
    def title(self, title: str):
        self.__pill.set_title(title)

    @GProperty(type=str)
    def icon_name(self) -> str:
        return self.__pill.icon.get_icon_name() or ""

    @icon_name.setter
    def icon_name(self, icon: str):
        self.__pill.icon.set_from_icon_name(icon)

    @GProperty(type=str)
    def status_cmd(self) -> str:
        return self._status_cmd

    @status_cmd.setter
    def status_cmd(self, cmd: str):
        self._status_cmd = cmd

        if cmd != "":

            def on_cmd_done(status: int):
                self._enabled = status == 0
                self.__on_status_changed()

            task = run_cmd_async(cmd)
            task.add_done_callback(lambda x, *_: on_cmd_done(x.result().returncode))

    @GProperty(type=str)
    def enable_cmd(self) -> str:
        return self._enable_cmd

    @enable_cmd.setter
    def enable_cmd(self, cmd: str):
        self._enable_cmd = cmd

    @GProperty(type=str)
    def disable_cmd(self) -> str:
        return self._disable_cmd

    @disable_cmd.setter
    def disable_cmd(self, cmd: str):
        self._disable_cmd = cmd

    @GProperty(type=str)
    def action_icon(self) -> str:
        return self._action_icon

    @action_icon.setter
    def action_icon(self, icon: str):
        self._action_icon = icon
        if icon:
            self.__pill.action.set_visible(True)
            self.__pill.action.set_icon_name(icon)
        else:
            self.__pill.action.set_visible(False)

    @GProperty(type=str)
    def action_cmd(self) -> str:
        return self._action_cmd

    @action_cmd.setter
    def action_cmd(self, cmd: str):
        self._action_cmd = cmd
        if cmd:
            self.__pill.action.connect("clicked", lambda *_: run_cmd_async(cmd))

    def __on_clicked(self, *_):
        self._enabled = not self._enabled
        self.__on_status_changed()

        if self._enabled and self.enable_cmd != "":
            run_cmd_async(self.enable_cmd)
        elif not self._enabled and self.disable_cmd != "":
            run_cmd_async(self.disable_cmd)

    def __on_status_changed(self):
        if self._enabled:
            self.__pill.set_subtitle("enabled")
            self.__pill.set_style_accent(True)
        else:
            self.__pill.set_subtitle("disabled")
            self.__pill.set_style_accent(False)


class ColorSchemeSwitcher(Gtk.Box):
    __gtype_name__ = "ColorSchemeSwitcher"

    def __init__(self):
        super().__init__()

        self.__pill = ControlSwitchPill()
        self.append(self.__pill)
        self.__pill.set_icon("dark-mode-symbolic")
        self.__pill.set_title("Color Scheme")

        self.__color_scheme = "default"
        self.__color_scheme_range: list[str] = []
        self.__desktop_settings: Gio.Settings | None = None

        try:
            gs = Gio.Settings(schema_id="org.gnome.desktop.interface")
            self.__desktop_settings = gs

            schema: Gio.SettingsSchema = gs.get_property("settings-schema")
            rng = schema.get_key("color-scheme").get_range()
            assert rng.get_child_value(0).get_string() == "enum", "failed to get 'color-scheme' range"
            rng = rng.get_child_value(1).get_variant()
            self.__color_scheme_range = rng.get_strv()
            self.set_tooltip_text("/".join(self.__color_scheme_range))

            gs.connect("changed::color-scheme", self.__on_color_scheme_changed)
            self.__on_color_scheme_changed()
            set_on_click(
                self, left=lambda *_: self.__switch_color_scheme(1), right=lambda *_: self.__switch_color_scheme(-1)
            )

        except GLib.Error as e:
            from loguru import logger

            logger.warning(f"failed to connect gsettings monitor: {e}")

    def __on_color_scheme_changed(self, *_):
        if self.__desktop_settings is None:
            return

        self.__color_scheme = self.__desktop_settings.get_string("color-scheme")
        self.__pill.set_subtitle(self.__color_scheme)

        if self.__color_scheme != "default":
            self.__pill.set_style_accent(True)
        else:
            self.__pill.set_style_accent(False)

    def __switch_color_scheme(self, delta: int):
        if self.__desktop_settings is None:
            return

        current_index = self.__color_scheme_range.index(self.__color_scheme)
        value = self.__color_scheme_range[(current_index + delta) % len(self.__color_scheme_range)]
        niri_action("DoScreenTransition")
        self.__desktop_settings.set_string("color-scheme", value)


class IgnisRecorder(Gtk.Box):
    __gtype_name__ = "IgnisRecorder"

    def __init__(self):
        self.__service = RecorderService.get_default()
        super().__init__()

        self.__pill = ControlSwitchPill()
        self.append(self.__pill)
        self.__pill.set_title("Recorder")
        self.__pill.set_subtitle("screen recorder")
        self.set_tooltip_text("Click to start/stop; right click to pause")

        self.__service.connect("notify::active", self.__on_status_changed)
        self.__service.connect("notify::is-paused", self.__on_status_changed)
        set_on_click(self, left=self.__on_clicked, right=self.__on_right_clicked)
        self.__on_status_changed()

    def __on_status_changed(self, *_):
        if self.__service.active:
            self.__pill.set_style_accent(True)
            if self.__service.is_paused:
                self.__pill.set_style_warning(True)
                self.__pill.icon.set_from_icon_name("media-playback-pause-symbolic")
            else:
                self.__pill.set_style_warning(False)
                self.__pill.icon.set_from_icon_name("media-playback-stop-symbolic")
        else:
            self.__pill.set_style_accent(False)
            self.__pill.set_style_warning(False)
            self.__pill.icon.set_from_icon_name("screencast-recorded-symbolic")

    def __on_clicked(self, *_):
        if self.__service.active:
            if self.__service.is_paused:
                self.__service.continue_recording()
            else:
                self.__service.stop_recording()
        else:
            wm.close_window(WindowName.control_center.value)
            create_task(self.__service.start_recording(RecorderConfig.new_from_options()))

    def __on_right_clicked(self, *_):
        if self.__service.active:
            if self.__service.is_paused:
                self.__service.continue_recording()
            else:
                self.__service.pause_recording()


class DndSwitch(Gtk.Box):
    __gtype_name__ = "DndSwitch"

    def __init__(self):
        self.__group = options and options.notifications
        super().__init__()

        self.__pill = ControlSwitchPill()
        self.append(self.__pill)
        self.__pill.set_title("Do Not Disturb")
        self.set_tooltip_text("Click to toggle")

        set_on_click(self, left=self.__on_clicked)
        if self.__group:
            connect_option(self.__group, "dnd", self.__on_option_changed)
            self.__on_option_changed()

    def __on_option_changed(self, *_):
        if self.__group:
            if self.__group.dnd:
                self.__pill.set_subtitle("disable popups")
                self.__pill.set_style_accent(True)
                self.__pill.icon.set_from_icon_name("notifications-disabled-symbolic")
            else:
                self.__pill.set_subtitle("default")
                self.__pill.set_style_accent(False)
                self.__pill.icon.set_from_icon_name("notifications-symbolic")

    def __on_clicked(self, *_):
        if self.__group:
            self.__group.dnd = not self.__group.dnd


class CaffeineSwitch(Gtk.Box):
    __gtype_name__ = "CaffeineSwitch"

    def __init__(self):
        self.__state = caffeine_state
        super().__init__()

        self.__pill = ControlSwitchPill()
        self.append(self.__pill)
        self.__pill.set_title("Caffeine")
        self.__pill.set_subtitle("disabled")
        self.__pill.set_icon("my-caffeine-off-symbolic")
        self.set_tooltip_text("Click to toggle")

        self.__state.connect("notify::value", self.__on_changed)
        set_on_click(self, left=self.__on_clicked)

    def __on_changed(self, *_):
        enabled = self.__state.value == True
        self.__pill.set_subtitle("enabled" if enabled else "disabled")
        if enabled:
            self.__pill.set_icon("my-caffeine-on-symbolic")
            self.__pill.set_style_accent(True)
        else:
            self.__pill.set_icon("my-caffeine-off-symbolic")
            self.__pill.set_style_accent(False)

    def __on_clicked(self, *_):
        self.__state.value = not self.__state.value


class EthernetStatus(Gtk.Box):
    __gtype_name__ = "EthernetStatus"

    def __init__(self):
        self.__service = NetworkService.get_default()
        self.__ethernet = self.__service.ethernet
        super().__init__()

        self.__pill = ControlSwitchPill()
        self.append(self.__pill)
        self.__pill.set_title("Ethernet")

        self.__ethernet.connect("notify::icon-name", self.__on_status_changed)
        self.__ethernet.connect("notify::devices", self.__on_status_changed)
        self.__on_status_changed()

    def __on_status_changed(self, *_):
        self.__pill.icon.set_from_icon_name(self.__ethernet.icon_name)
        self.set_tooltip_text()

        if not self.__ethernet.is_connected:
            self.__pill.set_subtitle("disconnected")
            self.__pill.set_style_accent(False)
            return

        self.__pill.set_style_accent(True)
        devices = self.__ethernet.devices
        match len(devices):
            case 0:
                self.__pill.set_subtitle("no device")
            case 1:
                device_name = devices[0].name
                self.__pill.set_subtitle(device_name)
                self.set_tooltip_text(device_name)
            case _:
                self.__pill.set_subtitle(f"{len(devices)} devices")


class WifiStatus(Gtk.Box):
    __gtype_name__ = "WifiStatus"

    def __init__(self):
        self.__service = NetworkService.get_default()
        self.__wifi = self.__service.wifi
        super().__init__()

        self.__pill = ControlSwitchPill()
        self.append(self.__pill)
        self.__pill.set_title("Wifi")

        self.__wifi.connect("notify::icon-name", self.__on_status_changed)
        self.__wifi.connect("notify::devices", self.__on_status_changed)
        set_on_click(self, left=self.__on_clicked)

    def __on_status_changed(self, *_):
        self.__pill.icon.set_from_icon_name(self.__wifi.icon_name)
        self.set_tooltip_text()

        if not self.__wifi.enabled:
            self.__pill.set_subtitle("disabled")
            self.__pill.set_style_accent(False)
            return

        self.__pill.set_style_accent(True)
        if not self.__wifi.is_connected:
            self.__pill.set_subtitle("disconnected")
            return

        devices = self.__wifi.devices
        match len(devices):
            case 0:
                self.__pill.set_subtitle("no device")
            case 1:
                ssid = devices[0].ap.ssid
                if isinstance(ssid, str):
                    self.__pill.set_subtitle(ssid)
                    self.set_tooltip_text(ssid)
            case _:
                self.__pill.set_subtitle(f"{len(devices)} devices")

    def __on_clicked(self, *_):
        self.__wifi.enabled = not self.__wifi.enabled


class BluetoothStatus(Gtk.Box):
    __gtype_name__ = "BluetoothStatus"

    def __init__(self):
        self.__service = BluetoothService.get_default()
        super().__init__()

        self.__pill = ControlSwitchPill()
        self.append(self.__pill)
        self.__pill.set_title("Bluetooth")

        self.__service.connect("notify::state", self.__on_status_changed)
        self.__service.connect("notify::devices", self.__on_devices_changed)
        self.__devices_signals: list[tuple[BluetoothDevice, int]] = []
        set_on_click(self, left=self.__on_clicked)

    def __on_devices_changed(self, *_):
        for device, id in self.__devices_signals:
            device.disconnect(id)
        self.__devices_signals.clear()

        for device in self.__service.devices:
            id = device.connect("notify::connected", self.__on_status_changed)
            self.__devices_signals.append((device, id))

    def __on_status_changed(self, *_):
        if not self.__service.powered:
            self.__pill.set_subtitle("disabled")
            self.__pill.icon.set_from_icon_name("bluetooth-disabled-symbolic")
            self.__pill.set_style_accent(False)
            return

        self.__pill.set_style_accent(True)
        devices = [device for device in self.__service.devices if device.connected]
        match len(devices):
            case 0:
                self.__pill.set_subtitle("disconnected")
                self.__pill.icon.set_from_icon_name("bluetooth-disconnected-symbolic")
            case 1:
                alias = devices[0].alias
                self.__pill.set_subtitle(alias)
                self.__pill.icon.set_from_icon_name(devices[0].icon_name)
                self.set_tooltip_text(alias)
            case _:
                self.__pill.set_subtitle(f"{len(devices)} devices")

    def __on_clicked(self, *_):
        self.__service.powered = not self.__service.powered


@gtk_template("controlcenter/notification-item")
class NotificationItem(Gtk.ListBoxRow, SpecsBase):
    __gtype_name__ = "NotificationItem"

    revealer: Gtk.Revealer = gtk_template_child()
    action_row: Adw.ActionRow = gtk_template_child()
    icon: Icon = gtk_template_child()
    time: Gtk.Label = gtk_template_child()
    actions: Gtk.Box = gtk_template_child()

    def __init__(self, notification: Notification):
        self._notification = notification
        self._is_popup = False
        super().__init__()
        SpecsBase.__init__(self)

        self.__update_notification()
        self.signal(notification, "closed", self.__on_closed)
        self.signal(notification, "dismissed", self.__on_dismissed)
        self.signal(self.revealer, "notify::child-revealed", self.__on_child_revealed)
        self.signal(self, "map", lambda *_: self.revealer.set_reveal_child(True))

        set_on_click(self.action_row, left=WeakMethod(self.__on_clicked), right=WeakMethod(self.__on_right_clicked))

    def do_dispose(self):
        self.clear_specs()
        self.dispose_template(self.__class__)
        super().do_dispose()  # type: ignore

    @property
    def notify_id(self) -> int:
        return self.notification.id

    @property
    def notify_ts(self) -> float:
        return self.notification.time

    @property
    def notification(self) -> Notification:
        return self._notification

    @property
    def is_popup(self) -> bool:
        return self._is_popup

    @is_popup.setter
    def is_popup(self, is_popup: bool):
        self._is_popup = is_popup
        css_class = "notification-popup-item"
        if is_popup:
            self.add_css_class(css_class)
        else:
            self.remove_css_class(css_class)

    def __update_notification(self):
        notify = self.notification
        self.__update_urgency(notify)

        summary, body = notify.summary, notify.body
        valid_markup = verify_pango_markup(summary) and verify_pango_markup(body)
        if not valid_markup:
            summary = escape_pango_markup(summary)
            body = escape_pango_markup(body)
        self.action_row.set_title(summary)
        self.action_row.set_subtitle(body)

        notified_at = datetime.fromtimestamp(notify.time)
        self.time.set_label(notified_at.strftime("%H:%M:%S\n%Y-%m-%d"))

        if notify.icon:
            icon = notify.icon
            if icon.startswith("file://"):
                icon = urllib.parse.unquote(icon).removeprefix("file://")
            self.icon.image = icon
        else:
            self.icon.image = "info-symbolic"

        self.actions.set_visible(len(notify.actions) != 0)

        children: list[Gtk.Button] = list(self.actions.observe_children())
        for child in children:
            self.actions.remove(child)
            child.run_dispose()

        for action in notify.actions:
            button = Gtk.Button()
            button.set_label(action.label)
            self.signal(button, "clicked", self.__on_action(action))
            self.actions.append(button)

    def __update_urgency(self, notify: Notification):
        urgency_dict = {0: "low", 1: "normal", 2: "critical"}
        for urgency in urgency_dict:
            css_class = f"notification-item-{urgency_dict[urgency]}"
            if notify.urgency == urgency:
                self.add_css_class(css_class)
            else:
                self.remove_css_class(css_class)

    def __on_closed(self, *_):
        def callback(*_):
            widget = self.get_ancestor(NotificationCenter)
            if isinstance(widget, NotificationCenter):
                widget.on_notify_closed(self.notification)

        if self.revealer.get_reveal_child():
            self.signal(self.revealer, "notify::child-revealed", callback)
            self.revealer.set_reveal_child(False)
        else:
            callback()

    def __on_dismissed(self, *_):
        def callback(*_):
            widget = self.get_ancestor(NotificationPopups)
            if isinstance(widget, NotificationPopups):
                widget.on_popup_dismissed(self.notification)

        if self.revealer.get_reveal_child():
            self.signal(self.revealer, "notify::child-revealed", callback)
            self.revealer.set_reveal_child(False)
        else:
            callback()

    def __on_child_revealed(self, *_):
        if self.revealer.get_reveal_child():
            self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        else:
            self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)

    def __on_clicked(self, *_):
        if not self.revealer.get_reveal_child():
            return

        if self.is_popup:
            wm.open_window(WindowName.control_center.value)

    def __on_right_clicked(self, *_):
        if not self.revealer.get_reveal_child():
            return

        if self._is_popup:
            self.notification.dismiss()
        else:
            self.notification.close()

    def __on_action(self, action: NotificationAction):
        def callback(_):
            action.invoke()
            wm.close_window(WindowName.control_center.value)

        return callback


@gtk_template("controlcenter/notificationcenter")
class NotificationCenter(Gtk.Box):
    __gtype_name__ = "NotificationCenter"

    clear_all: Gtk.Button = gtk_template_child()
    stack: Gtk.Stack = gtk_template_child()
    list_box: Gtk.ListBox = gtk_template_child()

    def __init__(self):
        self.__service = NotificationService.get_default()
        super().__init__()
        self._notifications = Gio.ListStore()
        self.list_box.bind_model(model=self._notifications, create_widget_func=lambda i: i)

        self._notifications.connect("notify::n-items", self.__on_store_changed)
        self.__service.connect("notified", self.__on_notified)

        for notify in self.__service.notifications:
            self.__on_notified(self.__service, notify)
        self.__on_store_changed()

    def __on_store_changed(self, *_):
        if self._notifications.get_n_items() != 0:
            self.clear_all.set_sensitive(True)
            self.stack.set_visible_child_name("notifications")
        else:
            self.clear_all.set_sensitive(False)
            self.stack.set_visible_child_name("no-notifications")

    def __find_notify(self, notify: Notification):
        return self._notifications.find_with_equal_func(
            notify, lambda i, n: i.notify_id == n.id and i.notify_ts == n.time
        )

    def __on_notified(self, _, notify: Notification):
        item = NotificationItem(notify)
        item.is_popup = False
        self._notifications.insert(0, item)

    def on_notify_closed(self, notify: Notification):
        found, pos = self.__find_notify(notify)
        if found:
            item = self._notifications.get_item(pos)
            self._notifications.remove(pos)
            if isinstance(item, NotificationItem):
                GLib.idle_add(lambda *_: item.run_dispose())

    @gtk_template_callback
    def on_clear_all_clicked(self, *_):
        self.__service.clear_all()
        clear_dir(NOTIFICATIONS_IMAGE_DATA)


class NotificationPopups(RevealerWindow):
    __gtype_name__ = "IgnisNotificationPopups"

    @gtk_template("notificationpopups")
    class View(Gtk.Box):
        __gtype_name__ = "NotificationPopupsView"

        revealer: Gtk.Revealer = gtk_template_child()
        list_box: Gtk.ListBox = gtk_template_child()

    def __init__(self):
        self.__service = NotificationService.get_default()
        self.__view = self.View()

        super().__init__(
            namespace=WindowName.notification_popups.value,
            anchor=["top", "right"],
            visible=False,
            margin_top=8,
            margin_right=8,
            css_classes=["transparent"],
            revealer=self.__view.revealer,
        )

        self.set_child(self.__view)

        self._popups = Gio.ListStore()
        self.__view.list_box.bind_model(model=self._popups, create_widget_func=lambda i: i)

        self._popups.connect("notify::n-items", self.__on_store_changed)
        self.__service.connect("new_popup", self.__on_new_popup)

    def __on_store_changed(self, *_):
        if self._popups.get_n_items() != 0:
            self.set_visible(True)
        else:
            self.set_visible(False)

    def __find_popup(self, popup: Notification):
        return self._popups.find_with_equal_func(popup, lambda i, p: i.notify_id == p.id and i.notify_ts == p.time)

    def __on_new_popup(self, _, popup: Notification):
        item = NotificationItem(popup)
        item.is_popup = True
        self._popups.insert(0, item)

    def on_popup_dismissed(self, popup: Notification):
        found, pos = self.__find_popup(popup)
        if found:
            item = self._popups.get_item(pos)
            self._popups.remove(pos)
            if isinstance(item, NotificationItem):
                GLib.idle_add(lambda *_: item.run_dispose())


class ControlCenter(RevealerWindow):
    __gtype_name__ = "ControlCenter"

    @gtk_template("controlcenter")
    class View(Gtk.Box):
        __gtype_name__ = "ControlCenterView"

        revealer: Gtk.Revealer = gtk_template_child()

    def __init__(self):
        self.__view = self.View()

        super().__init__(
            namespace=WindowName.control_center.value,
            kb_mode="on_demand",
            margin_top=8,
            margin_bottom=8,
            margin_right=8,
            anchor=["top", "right", "bottom"],
            layer="overlay",
            popup=True,
            visible=False,
            revealer=self.__view.revealer,
        )
        self.add_css_class("rounded")

        self.set_child(self.__view)

        if user_options and user_options.applauncher:
            connect_option(user_options.applauncher, "exclusive_focus", self.__on_exclusive_focus_changed)
        self.__on_exclusive_focus_changed()

    def set_property(self, property_name: str, value: Any):
        if property_name == "visible":
            overlay_window.update_window_visible(self.namespace, value)
        super().set_property(property_name, value)

    def __on_exclusive_focus_changed(self, *_):
        opts = user_options and user_options.applauncher
        if opts:
            self.kb_mode = "exclusive" if opts.exclusive_focus else "on_demand"
