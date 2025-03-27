import asyncio
import datetime, math
from typing import Callable
from gi.repository import Gio, GObject, Gtk
from ignis.app import IgnisApp
from ignis.widgets import Widget
from ignis.services.audio import AudioService, Stream
from ignis.services.hyprland import HyprlandService, HyprlandWorkspace
from ignis.services.mpris import MprisPlayer, MprisService
from ignis.services.network import Ethernet, NetworkService, Wifi
from ignis.services.niri import NiriService, NiriWorkspace
from ignis.services.system_tray import SystemTrayItem, SystemTrayService
from ignis.services.upower import UPowerDevice, UPowerService
from ignis.dbus_menu import DBusMenu
from ignis.utils import Utils
from ignis.utils.icon import get_app_icon_name
from .constants import WindowName
from .template import gtk_template, gtk_template_callback, gtk_template_child
from .useroptions import user_options, UserOptions
from .utils import get_widget_monitor_id, get_widget_monitor, niri_action, run_cmd_async, set_on_click, set_on_scroll


app = IgnisApp.get_default()


@gtk_template("modules/activewindow")
class ActiveWindow(Gtk.CenterBox):
    __gtype_name__ = "NiriActiveWindow"

    box: Gtk.Box = gtk_template_child()
    icon: Gtk.Image = gtk_template_child()
    label: Gtk.Label = gtk_template_child()

    def __init__(self):
        self.__niri = NiriService.get_default()
        self.__hypr = HyprlandService.get_default()
        super().__init__()

        self.__options: UserOptions.ActiveWindow | None = None
        if user_options and user_options.activewindow:
            self.__options = user_options.activewindow

        set_on_click(
            self,
            left=lambda _: self.__on_click("LEFT"),
            right=lambda _: self.__on_click("RIGHT"),
            middle=lambda _: self.__on_click("MIDDLE"),
        )
        set_on_scroll(self, self.__on_scroll)

        if self.__niri.is_available:
            self.__niri.connect("notify::active-window", self.__on_change)

        if self.__hypr.is_available:
            self.__hypr.connect("notify::active-window", self.__on_change)

    @property
    def has_active_window(self) -> bool:
        if self.__niri.is_available:
            return self.__niri.active_window.id > 0
        elif self.__hypr.is_available:
            return self.__hypr.active_window.address != ""
        return False

    def __on_change(self, *_):
        icon: str | None = None
        label = ""

        if self.__niri.is_available:
            if self.has_active_window:
                icon = get_app_icon_name(self.__niri.active_window.app_id)
                label = self.__niri.active_window.title
            else:
                label = "niri"

        if self.__hypr.is_available:
            if self.has_active_window:
                icon = get_app_icon_name(self.__hypr.active_window.class_name)
                label = self.__hypr.active_window.title
            else:
                label = "Hyprland"

        self.icon.set_visible(self.has_active_window)
        self.icon.set_from_icon_name(icon)
        self.label.set_label(label)

    def __on_click(self, key: str = "LEFT"):
        if self.__options:
            cmd: str = ""
            match key:
                case "LEFT":
                    cmd = self.__options.on_click
                case "RIGHT":
                    cmd = self.__options.on_right_click
                case "MIDDLE":
                    cmd = self.__options.on_middle_click
            if cmd != "":
                run_cmd_async(cmd)

    def __on_scroll(self, _, dx: float, dy: float):
        if self.__options:
            cmd: str = ""
            if dx < 0:
                cmd = self.__options.on_scroll_left
            elif dx > 0:
                cmd = self.__options.on_scroll_right
            elif dy < 0:
                cmd = self.__options.on_scroll_up
            elif dy > 0:
                cmd = self.__options.on_scroll_down
            if cmd != "":
                run_cmd_async(cmd)


class Workspaces(Widget.Box):
    __gtype_name__ = "NiriWorkspaces"

    class WorkspaceItem(Gtk.Box):
        __gtype_name__ = "WorkspaceItem"

        def __init__(self, niri_ws: NiriWorkspace | None = None, hypr_ws: HyprlandWorkspace | None = None):
            self.__niri = NiriService.get_default()
            self.__hypr = HyprlandService.get_default()
            self.__niri_ws = niri_ws
            self.__hypr_ws = hypr_ws
            super().__init__()

            self.icon = Gtk.Image(icon_name="pager-checked-symbolic")
            self.append(self.icon)

            set_on_click(self, left=self.__on_clicked)
            self.__on_changed()

            if self.__niri.is_available:
                self.__niri.connect("notify::active-workspace", self.__on_changed)
            if self.__hypr.is_available:
                self.__hypr.connect("notify::active-workspace", self.__on_changed)

        @property
        def is_active(self) -> bool:
            if self.__niri_ws:
                return self.__niri_ws.is_active
            if self.__hypr_ws:
                return self.__hypr_ws.id == self.__hypr.active_workspace.id
            return False

        def __set_ws_active(self, active: bool):
            if active:
                self.remove_css_class("dimmed")
            else:
                self.add_css_class("dimmed")

        def __on_changed(self, *_):
            if self.__niri_ws:
                self.set_tooltip_text(f"Workspace {self.__niri_ws.name or self.__niri_ws.idx}")
                self.__set_ws_active(self.is_active)
            if self.__hypr_ws:
                self.set_tooltip_text(f"Workspace {self.__hypr_ws.name or self.__hypr_ws.id}")
                self.__set_ws_active(self.is_active)

        def __on_clicked(self, *_):
            if self.__niri_ws:
                self.__niri_ws.switch_to()
            if self.__hypr_ws:
                self.__hypr_ws.switch_to()

    def __init__(self):
        self.__niri = NiriService.get_default()
        self.__hypr = HyprlandService.get_default()
        self.__connector: str | None = None
        super().__init__(css_classes=["hover", "rounded", "p-2"])

        self.connect("realize", self.__on_realize)
        set_on_scroll(self, self.__on_scroll)

        if self.__niri.is_available:
            self.__niri.connect("notify::workspaces", self.__on_change)

        if self.__hypr.is_available:
            self.__hypr.connect("notify::workspaces", self.__on_change)

    def __on_realize(self, _):
        monitor = get_widget_monitor(self)
        if monitor:
            self.__connector = monitor.get_connector()

    def __on_change(self, *_):
        if self.__niri.is_available:
            self.set_child(
                [self.WorkspaceItem(niri_ws=ws) for ws in self.__niri.workspaces if ws.output == self.__connector]
            )
        if self.__hypr.is_available:
            self.set_child(
                [self.WorkspaceItem(hypr_ws=ws) for ws in self.__hypr.workspaces if ws.monitor == self.__connector]
            )

    def __on_scroll(self, _, dx: float, dy: float):
        if self.__niri.is_available:
            niri_action(f"FocusWorkspace{"Up" if dx + dy < 0 else "Down"}")
        if self.__hypr.is_available:
            self.__hypr.send_command(f"dispatch workspace {"r-1" if dx + dy < 0 else "r+1"}")


class CommandPill(Gtk.Button):
    __gtype_name__ = "CommandPill"

    def __init__(self):
        self._click_cmd: str = ""
        super().__init__()

        self.connect("clicked", self.__on_clicked)

    def __on_clicked(self, *_):
        self.set_sensitive(False)
        Utils.Timeout(ms=1000, target=lambda: self.set_sensitive(True))

        if self._click_cmd != "":
            run_cmd_async(self._click_cmd)

    @GObject.Property(type=str)
    def click_command(self) -> str:  # type: ignore
        return self._click_cmd

    @click_command.setter
    def click_command(self, cmd: str):
        self._click_cmd = cmd


class Tray(Widget.Box):
    __gtype_name__ = "IgnisTray"

    class TrayItem(Widget.Box):
        __gtype_name__ = "IgnisTrayItem"

        def __init__(self, item: SystemTrayItem):
            super().__init__(tooltip_text=item.bind("tooltip"), child=[Widget.Icon(image=item.bind("icon"))])
            set_on_click(
                self,
                left=lambda _: asyncio.create_task(item.activate_async()),
                middle=lambda _: asyncio.create_task(item.secondary_activate_async()),
                right=self.__on_right_click,
            )
            set_on_scroll(self, self.__on_scroll)

            self.__item = item
            self.__menu: DBusMenu | None = item.get_menu()
            if self.__menu:
                self.__menu = self.__menu.copy()
                self.append(self.__menu)

        def __on_scroll(self, _, dx: float, dy: float):
            if dx != 0:
                self.__item.scroll(int(dx), orientation="horizontal")
            elif dy != 0:
                self.__item.scroll(int(dy), orientation="vertical")

        def __on_right_click(self, _):
            if self.__menu:
                self.__menu.popup()

    def __init__(self):
        self.__service = SystemTrayService.get_default()
        super().__init__(css_classes=["hover", "hpadding", "rounded", "tray"])
        self.__service.connect("notify::items", self.__on_change)

    def __on_change(self, *_):
        self.set_child([self.TrayItem(item) for item in self.__service.items[::-1]])


class Audio(Widget.Box):
    __gtype_name__ = "IgnisAudio"

    class AudioItem(Widget.Box):
        __gtype_name__ = "IgnisAudioItem"

        def __init__(self, stream: Stream):
            super().__init__(
                css_classes=["audio-item"],
                tooltip_text=stream.bind("description"),
                child=[Widget.Icon(image=stream.bind("icon_name"))],
            )
            set_on_click(
                self,
                left=lambda _: stream.set_is_muted(not stream.get_is_muted()),
                right=lambda _: app.toggle_window(WindowName.control_center.value),
            )

    def __init__(self):
        self.__service = AudioService.get_default()
        super().__init__(
            css_classes=["audio", "hover", "hpadding", "rounded"],
            child=[self.AudioItem(stream) for stream in [self.__service.speaker, self.__service.microphone] if stream],
        )


class Network(Widget.Box):
    __gtype_name__ = "IgnisNetwork"

    class NetworkEthernet(Widget.Box):
        __gtype_name__ = "IgnisNetworkEthernet"

        def __init__(self, ethernet: Ethernet):
            self.__ethernet = ethernet
            super().__init__(child=[Widget.Icon(image=ethernet.bind("icon_name"))])
            ethernet.connect("notify::is-connected", self.__on_change)
            self.__on_change()

        def __on_change(self, *_):
            connected: bool = self.__ethernet.is_connected
            self.set_tooltip_text("Connected" if connected else "Disconnected")

    class NetworkWifi(Widget.Box):
        __gtype_name__ = "IgnisNetworkWifi"

        def __init__(self, wifi: Wifi):
            self.__wifi = wifi
            super().__init__(child=[Widget.Icon(image=wifi.bind("icon_name"))])
            wifi.connect("notify::enabled", self.__on_change)
            wifi.connect("notify::is-connected", self.__on_change)
            self.__on_change()

        def __on_change(self, *_):
            enabled: bool = self.__wifi.enabled
            connected: bool = self.__wifi.is_connected
            self.set_tooltip_text("Disabled" if not enabled else "Connected" if connected else "Disconnected")

    def __init__(self):
        self.__service = NetworkService.get_default()
        super().__init__(
            css_classes=["network", "hover", "hpadding", "rounded"],
            child=[self.NetworkEthernet(self.__service.ethernet), self.NetworkWifi(self.__service.wifi)],
        )
        set_on_click(self, left=lambda _: app.toggle_window(WindowName.control_center.value))


class Mpris(Widget.Box):
    __gtype_name__ = "Mpris"

    @gtk_template("modules/mpris-item")
    class MprisItem(Gtk.Box):
        __gtype_name__ = "MprisItem"

        previous: Gtk.Button = gtk_template_child()
        next: Gtk.Button = gtk_template_child()
        pause: Gtk.Button = gtk_template_child()
        title: Gtk.Label = gtk_template_child()

        def __init__(self, player: MprisPlayer):
            self.__player = player
            super().__init__()

            self.previous.set_sensitive(player.can_go_previous)
            self.next.set_sensitive(player.can_go_next)
            self.pause.set_sensitive(player.can_pause and player.can_play)

            player.connect("notify::title", self.__on_change)
            player.connect("notify::playback-status", self.__on_change)
            player.connect("closed", self.__on_closed)
            self.__on_change()

            set_on_click(self, right=lambda _: app.toggle_window(WindowName.control_center.value))

        def __on_closed(self, *_):
            self.unparent()

        def __on_change(self, *_):
            self.title.set_text(self.__player.title or "Unknown")
            self.pause.set_icon_name(
                "media-playback-pause-symbolic"
                if self.__player.playback_status == "Playing"
                else "media-playback-start-symbolic"
            )

        @gtk_template_callback
        def on_pause_clicked(self, *_):
            status = self.__player.playback_status
            if status == "Playing" and self.__player.can_pause:
                self.__player.pause()
            elif status == "Paused" and self.__player.can_play:
                self.__player.play()

        @gtk_template_callback
        def on_previous_clicked(self, *_):
            if self.__player.can_go_previous:
                self.__player.previous()

        @gtk_template_callback
        def on_next_clicked(self, *_):
            if self.__player.can_go_next:
                self.__player.next()

    def __init__(self):
        self.__service = MprisService.get_default()
        super().__init__()
        self.__service.connect("player-added", self.__on_player_added)

    def __on_player_added(self, _, player: MprisPlayer):
        self.append(self.MprisItem(player))


@gtk_template("modules/clock")
class Clock(Gtk.Box):
    __gtype_name__ = "IgnisClock"

    label: Gtk.Label = gtk_template_child()
    popover: Gtk.Popover = gtk_template_child()
    calendar: Gtk.Calendar = gtk_template_child()

    def __init__(self):
        super().__init__()

        set_on_click(
            self,
            left=lambda _: self.popover.popup(),
            right=lambda _: app.toggle_window(WindowName.control_center.value),
        )

        Utils.Poll(timeout=1000, callback=self.__on_change)

    def __on_change(self, poll: Utils.Poll):
        now = datetime.datetime.now()

        self.label.set_label(now.strftime("%H:%M"))
        self.label.set_tooltip_text(now.strftime("%Y-%m-%d"))

        poll.set_timeout(60 * 1000 - math.floor(now.second * 1000 + now.microsecond / 1000))


@gtk_template("modules/batteries")
class Batteries(Gtk.Box):
    __gtype_name__ = "IgnisBatteries"

    @gtk_template("modules/batteries-item")
    class Item(Gtk.Box):
        __gtype_name__ = "IgnisBatteriesItem"

        icon: Gtk.Image = gtk_template_child()
        label: Gtk.Label = gtk_template_child()

        def __init__(self, battery: UPowerDevice):
            super().__init__()

            self.__battery = battery
            self.__percent: int = 0

            battery.connect("removed", self.__on_removed)
            battery.connect("notify::percent", self.__on_change)
            battery.connect("notify::charging", self.__on_change)

            self.__on_change()

        def __on_removed(self, *_):
            self.unparent()

        def __on_change(self, *_):
            time_remaining: int = self.__battery.get_time_remaining() // 60
            self.set_tooltip_text(f"{time_remaining} minutes" if time_remaining != 0 else "full")

            prev_percent = self.__percent
            self.__percent = int(self.__battery.get_percent())
            for threshold in (10, 20, 30):
                if self.__percent <= threshold < prev_percent:
                    self.__notify()
                    break

            self.label.set_label(f"{self.__percent}")
            self.icon.set_from_icon_name(self.__battery.get_icon_name())

        def __notify(self):
            monitor_id = get_widget_monitor_id(self)
            if monitor_id is not None and monitor_id != 0:
                return

            run_cmd_async(
                "notify-send -t %d --icon '%s' '%s' '%s'"
                % (30 * 1000, "battery-caution-symbolic", "LOW POWER", f"battery level: {self.__percent}%")
            )

    stack: Gtk.Stack = gtk_template_child()
    box: Gtk.Box = gtk_template_child()
    popover: Gtk.PopoverMenu = gtk_template_child()

    def __init__(self):
        self.__service = UPowerService.get_default()
        super().__init__()

        self.__group = Gio.SimpleActionGroup()
        self.insert_action_group("power", self.__group)

        self.__add_action("lock", lambda: run_cmd_async("loginctl lock-session"))
        self.__add_action("suspend", lambda: run_cmd_async("systemctl suspend"))
        self.__add_action("shutdown", lambda: run_cmd_async("systemctl poweroff"))
        self.__add_action("reboot", lambda: run_cmd_async("systemctl reboot"))
        self.__add_action("logout", self.__logout_session)

        set_on_click(
            self,
            left=lambda _: self.popover.popup(),
            right=lambda _: app.toggle_window(WindowName.control_center.value),
        )

        self.__service.connect("battery_added", self.__on_battery_added)
        self.__service.connect("notify::batteries", self.__on_change)
        self.__on_change()

    def __logout_session(self):
        niri = NiriService.get_default()
        if niri.is_available:
            niri_action("Quit", {"skip_confirmation": True})

        hypr = HyprlandService.get_default()
        if hypr.is_available:
            run_cmd_async("hyprctl dispatch exit")

    def __add_action(self, name: str, callback: Callable):
        def do_action(*_):
            callback()

        action = Gio.SimpleAction(name=name)
        action.connect("activate", do_action)
        self.__group.add_action(action)

    def __on_battery_added(self, _, battery: UPowerDevice):
        self.box.append(self.Item(battery))

    def __on_change(self, *_):
        self.stack.set_visible_child_name("batteries" if len(self.__service.get_batteries()) != 0 else "no-batteries")
