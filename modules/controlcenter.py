import urllib.parse
from gi.repository import Adw, Gio, GLib, Gtk
from ignis.app import IgnisApp
from ignis.widgets import Widget
from ignis.services.audio import AudioService, Stream
from ignis.services.network import Ethernet, EthernetDevice, NetworkService
from ignis.services.notifications import Notification, NotificationAction, NotificationService
from ignis.services.recorder import RecorderService
from ignis.options import options
from ignis.utils.thread import run_in_thread
from .backdrop import overlay_window
from .constants import AudioStreamType, WindowName
from .variables import caffeine_state
from .template import gtk_template, gtk_template_callback, gtk_template_child
from .utils import Pool, connect_window, connect_option, gproperty, niri_action, run_cmd_async, set_on_click


app = IgnisApp.get_default()


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
    class AudioControlStream(Gtk.ListBoxRow):
        __gtype_name__ = "AudioControlStream"

        icon: Gtk.Image = gtk_template_child()
        inscription: Gtk.Inscription = gtk_template_child()

        def __init__(self):
            self.__service = AudioService.get_default()
            self._stream: Stream | None = None
            self._default: Stream | None = None
            self._stream_type: AudioStreamType | None = None
            super().__init__()

            self.__notify_name = 0
            self.__notify_icon = 0
            self.__notify_is_default = 0
            self.__notify_default_id = 0

            set_on_click(self.icon, self.__on_mute_clicked)
            set_on_click(self, self.__on_clicked)

            self.__on_stream_changed()
            self.__on_default_changed()

        @property
        def stream(self) -> Stream | None:
            return self._stream

        @stream.setter
        def stream(self, stream: Stream):
            if self._stream:
                self._stream.disconnect(self.__notify_name)
                self._stream.disconnect(self.__notify_icon)
                self._stream.disconnect(self.__notify_is_default)
            self._stream = stream
            self.__notify_name = stream.connect("notify::name", self.__on_stream_changed)
            self.__notify_icon = stream.connect("notify::icon-name", self.__on_stream_changed)
            self.__notify_is_default = stream.connect("notify::is_default", self.__on_default_changed)
            self.__on_stream_changed()

        @property
        def stream_type(self) -> AudioStreamType | None:
            return self._stream_type

        @stream_type.setter
        def stream_type(self, stream_type: AudioStreamType):
            if self._stream_type and self._default:
                self._default.disconnect(self.__notify_default_id)
            self._stream_type = stream_type
            match stream_type:
                case AudioStreamType.speaker:
                    self._default = self.__service.get_speaker()
                case AudioStreamType.microphone:
                    self._default = self.__service.get_microphone()
            if self._default:
                self.__notify_default_id = self._default.connect("notify::id", self.__on_default_changed)
            self.__on_default_changed()

        def __on_stream_changed(self, *_):
            if not self._stream:
                return

            icon: str = self._stream.get_icon_name()
            description: str = self._stream.get_description()
            self.icon.set_from_icon_name(icon)
            self.inscription.set_text(description)
            self.inscription.set_tooltip_text(description)

        def __on_default_changed(self, *_):
            if not self._stream or not self._default:
                return
            if self._stream.get_id() == self._default.get_id():
                self.icon.add_css_class("accent")
            else:
                self.icon.remove_css_class("accent")

        def __on_mute_clicked(self, *_):
            if not self._stream:
                return
            self._stream.set_is_muted(not self._stream.get_is_muted())

        def __on_clicked(self, *_):
            match self._stream_type:
                case AudioStreamType.speaker:
                    self.__service.set_speaker(self._stream)
                case AudioStreamType.microphone:
                    self.__service.set_microphone(self._stream)

    def __init__(self, stream_type: AudioStreamType):
        self.__service = AudioService.get_default()
        self._stream_type = stream_type
        self._default: Stream | None = None
        self._streams = Gio.ListStore()

        super().__init__()
        self.__pool = Pool(self.AudioControlStream)
        self.list_box.bind_model(model=self._streams, create_widget_func=lambda item: item)

        set_on_click(self.icon, left=self.__on_mute_clicked)
        set_on_click(self.caption, left=self.__on_caption_clicked)
        connect_window(self, "notify::visible", self.__on_window_visible_change)

        match stream_type:
            case AudioStreamType.speaker:
                self._default = self.__service.get_speaker()
                self.__service.connect("speaker_added", self.__on_stream_added)
            case AudioStreamType.microphone:
                self._default = self.__service.get_microphone()
                self.__service.connect("microphone_added", self.__on_stream_added)

        if self._default is not None:
            self._default.connect("notify::description", self.__on_volume_changed)
            self._default.connect("notify::icon-name", self.__on_volume_changed)
            self._default.connect("notify::volume", self.__on_volume_changed)
            self.__on_volume_changed()

    def __new_stream(self, stream: Stream, stream_type: AudioStreamType) -> AudioControlStream:
        item = self.__pool.acquire()
        item.stream = stream
        item.stream_type = stream_type
        return item

    def __on_window_visible_change(self, window: Widget.Window, _):
        if not window.get_visible():
            self.revealer.set_reveal_child(False)

    def __on_volume_changed(self, *_):
        if self._default is None:
            return

        description: str = self._default.get_description()
        if description != self.caption.get_tooltip_text():
            self.caption.set_tooltip_text(description)

        icon_name: str = self._default.get_icon_name()
        if icon_name != self.icon.get_icon_name():
            self.icon.set_from_icon_name(self._default.get_icon_name())

        volume: int = round(self._default.get_volume())
        if volume != round(self.scale.get_value()):
            self.scale.set_value(volume)

    def __on_stream_added(self, _, stream: Stream):
        self._streams.append(self.__new_stream(stream, self._stream_type))

        def on_removed(stream: Stream):
            found, pos = self._streams.find(stream)
            if found:
                item = self._streams.get_item(pos)
                self._streams.remove(pos)
                if isinstance(item, self.AudioControlStream):
                    self.__pool.release(item)

        stream.connect("removed", on_removed)

    def __on_mute_clicked(self, *_):
        if self._default is None:
            return

        self._default.set_is_muted(not self._default.get_is_muted())

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
        if volume != round(self._default.get_volume()):
            self._default.set_volume(volume)


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


@gtk_template("controlcenter/switchpill")
class ControlSwitchPill(Gtk.Box):
    __gtype_name__ = "ControlSwitchPill"

    pill: Gtk.Box = gtk_template_child()
    icon: Gtk.Image = gtk_template_child()
    title: Gtk.Inscription = gtk_template_child()
    subtitle: Gtk.Inscription = gtk_template_child()

    def __init__(self):
        super().__init__()

    def set_title(self, title: str | None = None):
        self.title.set_text(title)

    def set_subtitle(self, subtitle: str | None = None):
        self.subtitle.set_text(subtitle)

    def set_icon(self, icon_name: str | None = None):
        self.icon.set_from_icon_name(icon_name)


class ControlSwitchCmd(Gtk.Box):
    __gtype_name__ = "ControlSwitchCmd"

    def __init__(self):
        self._enabled: bool = False
        self._status_cmd: str = ""
        self._enable_cmd: str = ""
        self._disable_cmd: str = ""
        super().__init__()

        self.__pill = ControlSwitchPill()
        self.append(self.__pill)
        set_on_click(self, self.__on_clicked)

    @gproperty(type=str)
    def title(self) -> str:
        return self.__pill.title.get_text() or ""

    @title.setter
    def title(self, title: str):
        self.__pill.set_title(title)

    @gproperty(type=str)
    def icon_name(self) -> str:
        return self.__pill.icon.get_icon_name() or ""

    @icon_name.setter
    def icon_name(self, icon: str):
        self.__pill.icon.set_from_icon_name(icon)

    @gproperty(type=str)
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

    @gproperty(type=str)
    def enable_cmd(self) -> str:
        return self._enable_cmd

    @enable_cmd.setter
    def enable_cmd(self, cmd: str):
        self._enable_cmd = cmd

    @gproperty(type=str)
    def disable_cmd(self) -> str:
        return self._disable_cmd

    @disable_cmd.setter
    def disable_cmd(self, cmd: str):
        self._disable_cmd = cmd

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
            self.__pill.pill.add_css_class("accent")
        else:
            self.__pill.set_subtitle("disabled")
            self.__pill.pill.remove_css_class("accent")


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
            rng: GLib.Variant = schema.get_key("color-scheme").get_range()
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
            self.__pill.pill.add_css_class("accent")
        else:
            self.__pill.pill.remove_css_class("accent")

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
        if self.__service.get_active():
            self.__pill.pill.add_css_class("accent")
            if self.__service.get_is_paused():
                self.__pill.pill.add_css_class("warning")
                self.__pill.icon.set_from_icon_name("media-playback-pause-symbolic")
            else:
                self.__pill.pill.remove_css_class("warning")
                self.__pill.icon.set_from_icon_name("media-playback-stop-symbolic")
        else:
            self.__pill.pill.remove_css_class("accent")
            self.__pill.pill.remove_css_class("warning")
            self.__pill.icon.set_from_icon_name("media-record-symbolic")

    @run_in_thread
    def __on_clicked(self, *_):
        if self.__service.get_active():
            if self.__service.get_is_paused():
                self.__service.continue_recording()
            else:
                self.__service.stop_recording()
        else:
            app.close_window(WindowName.control_center.value)
            self.__service.start_recording()

    def __on_right_clicked(self, *_):
        if self.__service.get_active():
            if self.__service.get_is_paused():
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
                self.__pill.pill.add_css_class("accent")
                self.__pill.icon.set_from_icon_name("notifications-disabled-symbolic")
            else:
                self.__pill.set_subtitle("default")
                self.__pill.pill.remove_css_class("accent")
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
            self.__pill.pill.add_css_class("accent")
        else:
            self.__pill.set_icon("my-caffeine-off-symbolic")
            self.__pill.pill.remove_css_class("accent")

    def __on_clicked(self, *_):
        self.__state.value = not self.__state.value


class EthernetStatus(Gtk.Box):
    __gtype_name__ = "EthernetStatus"

    def __init__(self):
        self.__service = NetworkService.get_default()
        self.__ethernet: Ethernet = self.__service.get_ethernet()
        super().__init__()

        self.__pill = ControlSwitchPill()
        self.append(self.__pill)
        self.__pill.set_title("Ethernet")

        self.__ethernet.connect("notify::icon-name", self.__on_status_changed)
        self.__ethernet.connect("notify::devices", self.__on_status_changed)
        self.__on_status_changed()

    def __on_status_changed(self, *_):
        self.__pill.icon.set_from_icon_name(self.__ethernet.get_icon_name())
        if not self.__ethernet.get_is_connected():
            self.__pill.set_subtitle("disconnected")
            return

        devices: list[EthernetDevice] = self.__ethernet.get_devices()
        match len(devices):
            case 0:
                self.__pill.set_subtitle("no device")
            case 1:
                device_name: str | None = devices[0].get_name()
                self.__pill.set_subtitle(device_name)
                self.set_tooltip_text(device_name)
            case _:
                self.__pill.set_subtitle(f"{len(devices)} devices")


@gtk_template("controlcenter/notification-item")
class NotificationItem(Gtk.ListBoxRow):
    __gtype_name__ = "NotificationItem"

    revealer: Gtk.Revealer = gtk_template_child()
    action_row: Adw.ActionRow = gtk_template_child()
    icon: Widget.Icon = gtk_template_child()
    actions: Gtk.Box = gtk_template_child()

    def __init__(self):
        self._notification: Notification | None = None
        self._is_popup = False
        super().__init__()

        self.__pool = Pool(Gtk.Button)
        self.__action_signals: list[int] = []
        self.revealer.connect("notify::child-revealed", self.__on_child_revealed)
        self.connect("map", lambda *_: self.revealer.set_reveal_child(True))
        set_on_click(self.action_row, left=self.__on_clicked, right=self.__on_right_clicked)

    @property
    def notify_id(self) -> int:
        return self.notification.id if self.notification else 0

    @property
    def notification(self) -> Notification | None:
        return self._notification

    @notification.setter
    def notification(self, notify: Notification):
        self._notification = notify

        self.action_row.set_title(notify.get_summary())
        self.action_row.set_subtitle(notify.get_body())

        if notify.get_icon():
            icon = notify.get_icon()
            if icon.startswith("file://"):
                icon = urllib.parse.unquote(icon).removeprefix("file://")
            self.icon.set_image(icon)

        self.actions.set_visible(len(notify.get_actions()) != 0)

        children: list[Gtk.Button] = list(self.actions.observe_children())
        for idx, child in enumerate(children):
            self.actions.remove(child)
            child.disconnect(self.__action_signals[idx])
            self.__pool.release(child)
        self.__action_signals.clear()

        for action in notify.get_actions():
            action: NotificationAction
            button = self.__pool.acquire()
            button.set_label(action.get_label())
            self.__action_signals.append(button.connect("clicked", self.__on_action(action)))
            self.actions.append(button)

    @property
    def is_popup(self) -> bool:
        return self._is_popup

    @is_popup.setter
    def is_popup(self, is_popup):
        self._is_popup = is_popup

    def __on_child_revealed(self, *_):
        if self.revealer.get_reveal_child():
            self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        else:
            self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)

    def __on_clicked(self, *_):
        if not self.revealer.get_reveal_child():
            return

        if self.is_popup:
            app.open_window(WindowName.control_center.value)

    def __on_right_clicked(self, *_):
        if not self.revealer.get_reveal_child():
            return
        if not self.notification:
            return

        if self._is_popup:
            self.notification.dismiss()
        else:
            self.notification.close()

    def __on_action(self, action: NotificationAction):
        def callback(_):
            action.invoke()
            app.close_window(WindowName.control_center.value)

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

        self.__pool = Pool(NotificationItem)
        self._notifications.connect("notify::n-items", self.__on_store_changed)
        self.__service.connect("notified", self.__on_notified)

        for notify in self.__service.get_notifications():
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
        return self._notifications.find_with_equal_func(notify, lambda i, n: i.notify_id == n.id)

    def __on_notified(self, _, notify: Notification):
        item = self.__pool.acquire()
        item.notification = notify
        item.is_popup = False
        self._notifications.insert(0, item)
        notify.connect("closed", self.__on_notify_closed)

    def __on_notify_closed(self, notify: Notification):
        found, pos = self.__find_notify(notify)
        if not found:
            return

        item = self._notifications.get_item(pos)
        if not isinstance(item, NotificationItem):
            return

        if not item.revealer.get_reveal_child():
            self._notifications.remove(pos)
            return

        def on_child_folded(*_):
            found, pos = self.__find_notify(notify)
            if found:
                self._notifications.remove(pos)
                self.__pool.release(item)

        item.revealer.set_reveal_child(False)
        item.revealer.connect("notify::child-revealed", on_child_folded)

    @gtk_template_callback
    def on_clear_all_clicked(self, *_):
        self.__service.clear_all()


class NotificationPopups(Widget.RevealerWindow):
    __gtype_name__ = "IgnisNotificationPopups"

    @gtk_template("notificationpopups")
    class View(Gtk.Box):
        __gtype_name__ = "NotificationPopupsView"

        revealer: Widget.Revealer = gtk_template_child()
        list_box: Gtk.ListBox = gtk_template_child()

    def __init__(self):
        self.__service = NotificationService.get_default()
        super().__init__(
            namespace=WindowName.notification_popups.value,
            anchor=["top", "right"],
            visible=False,
            margin_top=8,
            margin_right=8,
            css_classes=["transparent"],
            revealer=Widget.Revealer(),
        )

        self.__view = self.View()
        self.set_child(self.__view)
        self.set_revealer(self.__view.revealer)

        self._popups = Gio.ListStore()
        self.__view.list_box.bind_model(model=self._popups, create_widget_func=lambda i: i)

        self.__pool = Pool(NotificationItem)
        self._popups.connect("notify::n-items", self.__on_store_changed)
        self.__service.connect("new_popup", self.__on_new_popup)

    def __on_store_changed(self, *_):
        if self._popups.get_n_items() != 0:
            self.set_visible(True)
        else:
            self.set_visible(False)

    def __find_popup(self, popup: Notification):
        return self._popups.find_with_equal_func(popup, lambda i, p: i.notify_id == p.id)

    def __on_new_popup(self, _, popup: Notification):
        item = self.__pool.acquire()
        item.notification = popup
        item.is_popup = True
        self._popups.insert(0, item)
        popup.connect("dismissed", self.__on_popup_dismissed)

    def __on_popup_dismissed(self, popup: Notification):
        found, pos = self.__find_popup(popup)
        if not found:
            return

        item = self._popups.get_item(pos)
        if not isinstance(item, NotificationItem):
            return

        if not item.revealer.get_reveal_child():
            self._popups.remove(pos)
            return

        def on_child_folded(*_):
            found, pos = self.__find_popup(popup)
            if found:
                self._popups.remove(pos)
                self.__pool.release(item)

        item.revealer.set_reveal_child(False)
        item.revealer.connect("notify::child-revealed", on_child_folded)


class ControlCenter(Widget.RevealerWindow):
    __gtype_name__ = "ControlCenter"

    @gtk_template("controlcenter")
    class View(Gtk.Box):
        __gtype_name__ = "ControlCenterView"

        revealer: Widget.Revealer = gtk_template_child()
        preferences_button: Gtk.Button = gtk_template_child()

        @gtk_template_callback
        def on_preferences_button_clicked(self, *_):
            app.close_window(WindowName.control_center.value)
            app.open_window(WindowName.preferences.value)

    def __init__(self):
        super().__init__(
            namespace=WindowName.control_center.value,
            kb_mode="exclusive",
            margin_top=8,
            margin_bottom=8,
            margin_right=8,
            anchor=["top", "right", "bottom"],
            layer="overlay",
            popup=True,
            visible=False,
            revealer=Widget.Revealer(),
        )
        self.add_css_class("rounded")

        self.__view = self.View()
        self.set_child(self.__view)
        self.set_revealer(self.__view.revealer)
        self.connect("notify::visible", self.__on_visible_changed)

    def __on_visible_changed(self, *_):
        if self.get_visible():
            overlay_window.set_window(self.get_namespace())
        else:
            overlay_window.unset_window(self.get_namespace())
