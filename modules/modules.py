import asyncio
import datetime, math
from typing import Callable
from gi.repository import Gio, GObject, Gtk
from ignis.app import IgnisApp
from ignis.widgets import Widget
from ignis.services.audio import AudioService, Stream
from ignis.services.hyprland import HyprlandService, HyprlandWorkspace
from ignis.services.mpris import ART_URL_CACHE_DIR, MprisPlayer, MprisService
from ignis.services.network import Ethernet, NetworkService, Wifi
from ignis.services.niri import NiriService, NiriWorkspace
from ignis.services.recorder import RecorderService
from ignis.services.system_tray import SystemTrayItem, SystemTrayService
from ignis.services.upower import UPowerDevice, UPowerService
from ignis.dbus_menu import DBusMenu
from ignis.options import options
from ignis.utils import Utils
from .constants import WindowName
from .variables import caffeine_state
from .services import CpuLoadService
from .template import gtk_template, gtk_template_callback, gtk_template_child
from .useroptions import user_options
from .utils import (
    Pool,
    clear_dir,
    connect_option,
    format_time_duration,
    get_app_id,
    get_app_icon_name,
    get_widget_monitor_id,
    get_widget_monitor,
    gproperty,
    niri_action,
    run_cmd_async,
    set_on_click,
    set_on_scroll,
)


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

        self.__options = user_options and user_options.activewindow

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
        tooltip: str | None = None

        if self.__niri.is_available:
            if self.has_active_window:
                niri_win = self.__niri.active_window
                icon = get_app_icon_name(niri_win.app_id)
                label = niri_win.title
                tooltip = f"{get_app_id(niri_win.app_id)} - {niri_win.title}"
            else:
                label = "niri"

        if self.__hypr.is_available:
            if self.has_active_window:
                hypr_win = self.__hypr.active_window
                icon = get_app_icon_name(hypr_win.class_name)
                label = hypr_win.title
                tooltip = f"{get_app_id(hypr_win.class_name)} - {hypr_win.title}"
            else:
                label = "Hyprland"

        self.icon.set_visible(self.has_active_window)
        self.icon.set_from_icon_name(icon)
        self.label.set_label(label)
        self.set_tooltip_text(tooltip)

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

        def __init__(self):
            self.__niri = NiriService.get_default()
            self.__hypr = HyprlandService.get_default()
            self.__niri_ws: NiriWorkspace | None = None
            self.__hypr_ws: HyprlandWorkspace | None = None
            super().__init__()

            self.icon = Gtk.Image(icon_name="pager-checked-symbolic")
            self.append(self.icon)

            set_on_click(self, left=self.__on_clicked)
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

        @property
        def niri_ws(self) -> NiriWorkspace | None:
            return self.__niri_ws

        @niri_ws.setter
        def niri_ws(self, ws: NiriWorkspace):
            self.__niri_ws = ws
            self.__on_changed()

        @property
        def hypr_ws(self) -> HyprlandWorkspace | None:
            return self.__hypr_ws

        @hypr_ws.setter
        def hypr_ws(self, ws: HyprlandWorkspace):
            self.__hypr_ws = ws
            self.__on_changed()

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

        self.__pool = Pool(self.WorkspaceItem)
        self.connect("realize", self.__on_realize)
        set_on_scroll(self, self.__on_scroll)

        if self.__niri.is_available:
            self.__niri.connect("notify::workspaces", self.__on_change)

        if self.__hypr.is_available:
            self.__hypr.connect("notify::workspaces", self.__on_change)

    def __new_item(self, niri_ws: NiriWorkspace | None = None, hypr_ws: HyprlandWorkspace | None = None):
        item = self.__pool.acquire()
        if niri_ws:
            item.niri_ws = niri_ws
        if hypr_ws:
            item.hypr_ws = hypr_ws
        return item

    def __on_realize(self, _):
        monitor = get_widget_monitor(self)
        if monitor:
            self.__connector = monitor.get_connector()

    def __on_change(self, *_):
        children = self.child
        self.child = []
        for item in children:
            if isinstance(item, Workspaces.WorkspaceItem):
                self.__pool.release(item)
        if self.__niri.is_available:
            self.child = [self.__new_item(niri_ws=ws) for ws in self.__niri.workspaces if ws.output == self.__connector]
        if self.__hypr.is_available:
            self.child = [
                self.__new_item(hypr_ws=ws) for ws in self.__hypr.workspaces if ws.monitor == self.__connector
            ]

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
        if self._click_cmd != "":
            run_cmd_async(self._click_cmd)

    @gproperty(type=str)
    def click_command(self) -> str:
        return self._click_cmd

    @click_command.setter
    def click_command(self, cmd: str):
        self._click_cmd = cmd


class CpuUsagePill(CommandPill):
    __gtype_name__ = "CpuUsagePill"

    def __init__(self):
        self._label: Gtk.Label | None = None
        super().__init__()

        self.__cpu = CpuLoadService.get_default()
        self.__processors = self.__cpu.cpu_count
        self.__cpu.connect("notify::total-time", self.__on_updated)

    @gproperty(type=int)
    def interval(self) -> int:
        return self.__cpu.interval

    @interval.setter
    def interval(self, interval: int):
        self.__cpu.interval = interval

    @gproperty(type=Gtk.Label)
    def labeler(self) -> Gtk.Label | None:
        return self._label

    @labeler.setter
    def labeler(self, label: Gtk.Label):
        self._label = label

    def __on_updated(self, *_):
        idle, total = self.__cpu.idle_time, self.__cpu.total_time
        # this means how many percent of computing resources of a single processor are used
        # e.g. 234% means 2.34 processors are used; 1600% (with 16 processors) means all processors are used
        percent = (total - idle) * 100 * self.__processors // total if total else 0
        label = f"{round(percent)}"
        self.set_tooltip_text(f"CPU Usage: {round(percent)}% / {self.__processors * 100}%")
        if self.labeler:
            self.labeler.set_label(label)
        else:
            self.set_label(label)


class Tray(Gtk.FlowBox):
    __gtype_name__ = "IgnisTray"

    class TrayItem(Gtk.FlowBoxChild):
        __gtype_name__ = "IgnisTrayItem"

        def __init__(self):
            self.__icon = Widget.Icon()
            self.__box = Gtk.Box()
            self.__box.append(self.__icon)
            super().__init__(css_classes=["px-1"], child=self.__box)
            set_on_click(self, left=self.__on_clicked, middle=self.__on_middlet_clicked, right=self.__on_right_clicked)
            set_on_scroll(self, self.__on_scroll)
            self.__tooltip_id: int = 0
            self.__icon_id: int = 0

            self.__item: SystemTrayItem | None = None
            self.__menu: DBusMenu | None = None

        @property
        def tray_item(self) -> SystemTrayItem | None:
            return self.__item

        @tray_item.setter
        def tray_item(self, item: SystemTrayItem):
            if self.__item:
                self.__item.disconnect(self.__tooltip_id)
                self.__item.disconnect(self.__icon_id)
            if self.__menu:
                self.__box.remove(self.__menu)

            self.__item = item
            self.__menu = item.menu
            self.__tooltip_id = item.connect("notify::tooltip", self.__on_changed)
            self.__icon_id = item.connect("notify::icon", self.__on_changed)
            if self.__menu:
                self.__menu = self.__menu.copy()
                self.__box.append(self.__menu)

            self.__on_changed()

        def __on_changed(self, *_):
            if self.__item:
                self.__icon.image = self.__item.icon or ""
                self.set_tooltip_text(self.__item.tooltip)

        def __on_clicked(self, _):
            if self.__item:
                asyncio.create_task(self.__item.activate_async())

        def __on_middlet_clicked(self, _):
            if self.__item:
                asyncio.create_task(self.__item.secondary_activate_async())

        def __on_scroll(self, _, dx: float, dy: float):
            if not self.__item:
                return

            if dx != 0:
                self.__item.scroll(int(dx), orientation="horizontal")
            elif dy != 0:
                self.__item.scroll(int(dy), orientation="vertical")

        def __on_right_clicked(self, _):
            if self.__menu:
                self.__menu.popup()

    def __init__(self):
        self.__service = SystemTrayService.get_default()
        super().__init__()
        self.add_css_class("hover")
        self.add_css_class("rounded")

        self.__pool = Pool(self.TrayItem)
        self.__service.connect("added", self.__on_item_added)
        self.__list_store = Gio.ListStore()
        self.bind_model(self.__list_store, lambda item: item)
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_min_children_per_line(100)
        self.set_max_children_per_line(100)

    def __new_item(self, tray_item: SystemTrayItem):
        item = self.__pool.acquire()
        item.tray_item = tray_item
        return item

    def __on_item_added(self, _, tray_item: SystemTrayItem):
        item = self.__new_item(tray_item)
        self.__list_store.insert(0, item)
        tray_item.connect("removed", self.__on_item_removed)

    def __on_item_removed(self, tray_item: SystemTrayItem):
        found, pos = self.__list_store.find_with_equal_func(tray_item, lambda i, t: i.tray_item == t)
        if found:
            item = self.__list_store.get_item(pos)
            self.__list_store.remove(pos)
            if isinstance(item, Tray.TrayItem):
                self.__pool.release(item)


class CaffeineIndicator(Widget.Box):
    __gtype_name__ = "IgnisCaffeineIndicator"

    def __init__(self):
        self.__state = caffeine_state
        self.__cookie: int = 0
        super().__init__(
            css_classes=["hover", "px-1", "rounded"],
            tooltip_text="Caffeine enabled",
            visible=False,
            child=[Widget.Icon(image="my-caffeine-on-symbolic")],
        )
        self.__state.connect("notify::value", self.__on_changed)
        set_on_click(self, left=self.__on_clicked, right=self.__on_right_clicked)

    def __on_changed(self, *_):
        enabled = self.__state.value == True
        self.set_visible(enabled)

        if enabled:
            window = self.get_ancestor(Widget.Window)
            if isinstance(window, Widget.Window):
                self.__cookie = app.inhibit(
                    window=window, flags=Gtk.ApplicationInhibitFlags.IDLE, reason="Caffeine Mode Enabled"
                )
        else:
            if self.__cookie != 0:
                app.uninhibit(self.__cookie)

    def __on_clicked(self, *_):
        self.__state.value = not self.__state.value

    def __on_right_clicked(self, *_):
        app.toggle_window(WindowName.control_center.value)


class DndIndicator(Widget.Box):
    __gtype_name__ = "IgnisDndIndicator"

    def __init__(self):
        self.__options = options and options.notifications
        super().__init__(
            css_classes=["hover", "px-1", "rounded", "warning"],
            tooltip_text="Do Not Disturb enabled",
            child=[Widget.Icon(image="notifications-disabled-symbolic")],
        )

        if self.__options:
            connect_option(self.__options, "dnd", self.__on_changed)
            set_on_click(self, left=self.__on_clicked, right=self.__on_right_clicked)
        self.__on_changed()

    def __on_changed(self, *_):
        self.set_visible(self.__options and self.__options.dnd or False)

    def __on_clicked(self, *_):
        if self.__options:
            self.__options.dnd = not self.__options.dnd

    def __on_right_clicked(self, *_):
        app.toggle_window(WindowName.control_center.value)


class RecorderIndicator(Widget.Box):
    __gtype_name__ = "IgnisRecorderIndicator"

    def __init__(self):
        self.__service = RecorderService.get_default()
        self.__icon = Widget.Icon()
        super().__init__(css_classes=["hover", "px-1", "rounded", "warning"], child=[self.__icon])

        self.__service.connect("notify::active", self.__on_status_changed)
        self.__service.connect("notify::is-paused", self.__on_status_changed)
        set_on_click(self, left=self.__on_clicked, right=self.__on_right_clicked)
        self.__on_status_changed()

    def __on_status_changed(self, *_):
        if self.__service.active:
            self.set_visible(True)
            if self.__service.is_paused:
                self.set_tooltip_text("Screen Recorder Paused")
                self.__icon.image = "media-playback-pause-symbolic"
            else:
                self.set_tooltip_text("Screen Recording")
                self.__icon.image = "camera-video-symbolic"
        else:
            self.set_visible(False)

    def __on_clicked(self, *_):
        if self.__service.active:
            if self.__service.is_paused:
                self.__service.continue_recording()
            else:
                self.__service.stop_recording()
        else:
            self.__service.start_recording()

    def __on_right_clicked(self, *_):
        if self.__service.active:
            if self.__service.is_paused:
                self.__service.continue_recording()
            else:
                self.__service.pause_recording()


class Audio(Widget.Box):
    __gtype_name__ = "IgnisAudio"

    class AudioItem(Widget.Box):
        __gtype_name__ = "IgnisAudioItem"

        def __init__(self, stream: Stream):
            super().__init__(
                css_classes=["px-1"],
                tooltip_text=stream.bind("description"),
                child=[Widget.Icon(image=stream.bind("icon_name"))],
            )
            set_on_click(
                self,
                left=lambda _: stream.set_is_muted(not stream.is_muted),
                right=lambda _: app.toggle_window(WindowName.control_center.value),
            )

    def __init__(self):
        self.__service = AudioService.get_default()
        super().__init__(
            css_classes=["hover", "rounded"],
            child=[self.AudioItem(stream) for stream in [self.__service.speaker, self.__service.microphone] if stream],
        )


class Network(Widget.Box):
    __gtype_name__ = "IgnisNetwork"

    class NetworkEthernet(Widget.Box):
        __gtype_name__ = "IgnisNetworkEthernet"

        def __init__(self, ethernet: Ethernet):
            self.__ethernet = ethernet
            super().__init__(css_classes=["px-1"], child=[Widget.Icon(image=ethernet.bind("icon_name"))])
            ethernet.connect("notify::is-connected", self.__on_change)
            self.__on_change()
            set_on_click(self, left=self.__on_clicked, right=self.__on_clicked)

        def __on_change(self, *_):
            connected = self.__ethernet.is_connected
            self.set_tooltip_text("Connected" if connected else "Disconnected")

        def __on_clicked(self, *_):
            app.toggle_window(WindowName.control_center.value)

    class NetworkWifi(Widget.Box):
        __gtype_name__ = "IgnisNetworkWifi"

        def __init__(self, wifi: Wifi):
            self.__wifi = wifi
            super().__init__(css_classes=["px-1"], child=[Widget.Icon(image=wifi.bind("icon_name"))])
            wifi.connect("notify::enabled", self.__on_change)
            wifi.connect("notify::is-connected", self.__on_change)
            self.__on_change()
            set_on_click(
                self, left=self.__on_clicked, right=lambda _: app.toggle_window(WindowName.control_center.value)
            )

        def __on_change(self, *_):
            enabled = self.__wifi.enabled
            connected = self.__wifi.is_connected
            self.set_tooltip_text("Disabled" if not enabled else "Connected" if connected else "Disconnected")

        def __on_clicked(self, *_):
            self.__wifi.enabled = not self.__wifi.enabled

    def __init__(self):
        self.__service = NetworkService.get_default()
        super().__init__(
            css_classes=["hover", "rounded"],
            child=[self.NetworkEthernet(self.__service.ethernet), self.NetworkWifi(self.__service.wifi)],
        )


class Mpris(Widget.Box):
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

            set_on_click(self, right=lambda _: app.toggle_window(WindowName.control_center.value))

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


@gtk_template("modules/clock")
class Clock(Gtk.Box):
    __gtype_name__ = "IgnisClock"

    label: Gtk.Label = gtk_template_child()
    popover: Gtk.Popover = gtk_template_child()
    calendar: Gtk.Calendar = gtk_template_child()

    def __init__(self):
        super().__init__()

        set_on_click(self, left=self.__on_clicked, right=self.__on_right_clicked)

        Utils.Poll(timeout=1000, callback=self.__on_change)

    def __on_change(self, poll: Utils.Poll):
        now = datetime.datetime.now()

        self.label.set_label(now.strftime("%H:%M"))
        self.label.set_tooltip_text(now.strftime("%Y-%m-%d"))

        poll.set_timeout(60 * 1000 - math.floor(now.second * 1000 + now.microsecond / 1000))

    def __on_clicked(self, *_):
        now = datetime.datetime.now()
        self.calendar.set_year(now.year)
        self.calendar.set_month(now.month - 1)
        self.calendar.set_day(now.day)
        self.popover.popup()

    def __on_right_clicked(self, *_):
        app.toggle_window(WindowName.control_center.value)


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
            time_remaining = self.__battery.time_remaining // 60
            self.set_tooltip_text(f"{time_remaining} minutes" if time_remaining != 0 else "full")

            prev_percent = self.__percent
            self.__percent = int(self.__battery.percent)
            for threshold in (10, 20, 30):
                if self.__percent <= threshold < prev_percent:
                    self.__notify()
                    break

            self.label.set_label(f"{self.__percent}")
            level = round(self.__percent, -1)
            charging = "-charging" if self.__battery.charging else ""
            icon_name = f"battery-level-{level}{charging}-symbolic"
            self.icon.set_from_icon_name(icon_name)

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
        self.stack.set_visible_child_name("batteries" if len(self.__service.batteries) != 0 else "no-batteries")
