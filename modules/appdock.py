from gi.repository import Gdk, Gio, Gtk
from ignis.widgets import Widget
from ignis.services.applications import Application, ApplicationsService
from ignis.services.hyprland import HyprlandMonitor, HyprlandWindow, HyprlandWorkspace, HyprlandService
from ignis.services.niri import NiriWindow, NiriWorkspace, NiriService
from ignis.utils.timeout import Timeout
from .constants import WindowName
from .template import gtk_template, gtk_template_child
from .useroptions import user_options
from .utils import (
    Pool,
    connect_option,
    get_app_id,
    get_app_icon_name,
    get_widget_monitor,
    launch_application,
    set_on_click,
    set_on_scroll,
    set_on_motion,
)


class WindowFocusHistory:
    initialized: bool = False
    increment: int = 0
    focused_window_id: int = 0
    # dict[win_id, hist_id]
    focus_hist: dict[int, int] = {}

    @classmethod
    def get_focus_hist(cls, window_id: int):
        return cls.focus_hist.get(window_id, 0)

    @classmethod
    def focus_window(cls, window_id: int):
        if cls.focused_window_id == window_id:
            return

        cls.increment += 1
        cls.focus_hist[window_id] = cls.increment

    @classmethod
    def find_latest_index(
        cls, niri_windows: list[NiriWindow] | None = None, hypr_windows: list[HyprlandWindow] | None = None
    ):
        i = 0
        idx = -1
        latest = 0
        for win in niri_windows or hypr_windows or []:
            id = win.id if isinstance(win, NiriWindow) else win.pid
            hist = cls.get_focus_hist(id)
            if hist > latest:
                idx = i
                latest = hist
            i += 1
        return idx

    @classmethod
    def sync_windows(
        cls, niri_windows: list[NiriWindow] | None = None, hypr_windows: list[HyprlandWindow] | None = None
    ):
        if not niri_windows and not hypr_windows:
            cls.initialized = True
            return

        if cls.initialized:
            id_set = None
            if niri_windows and len(niri_windows) != len(cls.focus_hist):
                id_set = set(w.id for w in niri_windows)
            elif hypr_windows and len(hypr_windows) != len(cls.focus_hist):
                id_set = set(w.pid for w in hypr_windows)
            if id_set:
                for id in id_set:
                    cls.focus_hist.pop(id, None)
        else:
            cls.initialized = True
            if niri_windows:
                for id in [w.id for w in sorted(niri_windows, key=lambda w: w.id)]:
                    cls.focus_window(id)
            elif hypr_windows:
                for pid in [w.pid for w in sorted(hypr_windows, key=lambda w: -w.focus_history_id)]:
                    cls.focus_window(pid)


@gtk_template("appdock")
class AppDockView(Gtk.Box):
    __gtype_name__ = "IgnisAppDockView"

    @gtk_template("appdock-item")
    class Item(Gtk.FlowBoxChild):
        __gtype_name__ = "IgnisAppDockItem"

        class Dot(Gtk.FlowBoxChild):
            __gtype_name__ = "IgnisAppDockItemDot"

            def __init__(self):
                self.__icon = Gtk.Image(icon_name="pager-checked-symbolic", pixel_size=8)
                self.__revealer = Gtk.Revealer(reveal_child=True, child=self.__icon)
                super().__init__(child=self.__revealer)
                self.__icon.add_css_class("dimmed")

            def set_focused(self, focused: bool):
                if focused:
                    self.__icon.remove_css_class("dimmed")
                else:
                    self.__icon.add_css_class("dimmed")

            def set_reveal(self, reveal: bool, direction: str | None = None):
                types = Gtk.RevealerTransitionType
                transition = (
                    types.SLIDE_RIGHT
                    if direction == "left"
                    else types.SLIDE_LEFT if direction == "right" else types.CROSSFADE
                )
                self.__revealer.set_transition_type(transition)
                self.__revealer.set_reveal_child(reveal)

        icon: Gtk.Image = gtk_template_child()
        pin_icon: Gtk.Image = gtk_template_child()
        dots: Gtk.FlowBox = gtk_template_child()

        def __init__(self):
            self.__hypr = HyprlandService.get_default()
            self.__app_options = user_options and user_options.applauncher
            self.__app_id: str = ""
            self.__app_info: Application | None = None
            self.__niri_wins: list[NiriWindow] | None = None
            self.__hypr_wins: list[HyprlandWindow] | None = None
            super().__init__()

            self.__dots_store = Gio.ListStore()
            self.dots.bind_model(self.__dots_store, lambda i: i)
            set_on_click(self.icon, left=self.__on_clicked, right=self.__on_right_clicked)
            set_on_scroll(self.icon, self.__on_scrolled)

            drop_target = Gtk.DropTarget.new(str, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
            drop_target.connect("drop", self.__on_drop_target)
            self.add_controller(drop_target)

        @property
        def app_id(self) -> str:
            return self.__app_id

        @app_id.setter
        def app_id(self, app_id: str):
            if self.__app_id == app_id:
                return

            self.__app_id = app_id
            self.icon.set_from_icon_name(get_app_icon_name(self.app_id))

        @property
        def app_info(self) -> Application | None:
            return self.__app_info

        @app_info.setter
        def app_info(self, app_info: Application | None):
            self.__app_info = app_info
            self.pin_icon.set_visible(True if app_info and app_info.is_pinned else False)

        @property
        def niri_windows(self) -> list[NiriWindow] | None:
            return self.__niri_wins

        @niri_windows.setter
        def niri_windows(self, wins: list[NiriWindow] | None):
            self.__dots_store.remove_all()
            if wins:
                wins = sorted(wins, key=lambda w: w.id)
                self.__niri_wins = wins
                idx = WindowFocusHistory.find_latest_index(niri_windows=wins)
                if idx < 0:
                    idx = 0
                self.set_tooltip_text(f"{self.app_id} - {wins[idx].title}")
                self.__update_dots(idx, len(wins))
            else:
                self.__niri_wins = None
                if self.app_info:
                    self.set_tooltip_text(f"{self.app_id} - {self.app_info.name}\n{self.app_info.description}")
                else:
                    self.set_tooltip_text(self.app_id)

        @property
        def hypr_windows(self) -> list[HyprlandWindow] | None:
            return self.__hypr_wins

        @hypr_windows.setter
        def hypr_windows(self, wins: list[HyprlandWindow] | None):
            self.__dots_store.remove_all()
            if wins:
                wins = sorted(wins, key=lambda w: w.pid)
                self.__hypr_wins = wins
                idx = WindowFocusHistory.find_latest_index(hypr_windows=wins)
                if idx < 0:
                    idx = 0
                self.set_tooltip_text(f"{self.app_id} - {wins[idx].title}")
                self.__update_dots(idx, len(wins))
            else:
                self.__hypr_wins = None
                if self.app_info:
                    self.set_tooltip_text(f"{self.app_id} - {self.app_info.name}\n{self.app_info.description}")
                else:
                    self.set_tooltip_text(self.app_id)

        def __update_dots(self, index: int, length: int):
            if index <= 2:
                left, right = index, min(length - 1, 4) - index
            elif length - 1 - index <= 2:
                left, right = index - (length - 5), length - 1 - index
            else:
                left, right = 2, 2
            for focused in [False] * left + [True] + [False] * right:
                dot = self.Dot()
                dot.set_focused(focused)
                self.__dots_store.append(dot)

        def __launch_app(self, files: list[str] | None = None):
            if not self.app_info:
                return

            command_format = self.__app_options and self.__app_options.command_format
            terminal_format = self.__app_options and self.__app_options.terminal_format

            launch_application(
                self.app_info, files=files, command_format=command_format, terminal_format=terminal_format
            )

        def __on_clicked(self, *_):
            if self.niri_windows:
                # first window
                self.niri_windows[0].focus()
            elif self.hypr_windows:
                # most recently focus window
                pid: int = sorted(self.hypr_windows, key=lambda w: w.focus_history_id)[0].pid
                self.__hypr.send_command(f"dispatch focuswindow pid:{pid}")
                self.__hypr.send_command("dispatch alterzorder top")
            elif self.app_info:
                self.__launch_app()

        def __on_right_clicked(self, *_):
            if self.niri_windows:
                pass
            elif self.hypr_windows:
                pass
            elif self.app_info:
                pass

        def __on_scrolled(self, _, dx: float, dy: float):
            delta = 1 if dx + dy > 0 else -1
            if self.niri_windows:
                idx = WindowFocusHistory.find_latest_index(niri_windows=self.niri_windows)
                if idx >= 0:
                    idx = (idx + delta) % len(self.niri_windows)
                else:
                    idx = 0
                self.niri_windows[idx].focus()
            elif self.hypr_windows:
                idx = WindowFocusHistory.find_latest_index(hypr_windows=self.hypr_windows)
                if idx >= 0:
                    idx = (idx + delta) % len(self.hypr_windows)
                else:
                    idx = 0
                pid = self.hypr_windows[idx].pid
                self.__hypr.send_command(f"dispatch focuswindow pid:{pid}")
                self.__hypr.send_command("dispatch alterzorder top")

        def __on_drop_target(self, controller: Gtk.DropTarget, value: str, x: float, y: float):
            files = value.split("\n")
            if self.app_info and files:
                self.__launch_app(files)

    conceal: Gtk.Revealer = gtk_template_child()
    revealer: Gtk.Revealer = gtk_template_child()
    flow_box: Gtk.FlowBox = gtk_template_child()

    def __init__(self):
        self.__dock_options = user_options and user_options.appdock
        self.__apps = ApplicationsService.get_default()
        self.__niri = NiriService.get_default()
        self.__hypr = HyprlandService.get_default()
        self.__niri_wins: list[NiriWindow] = []
        self.__hypr_wins: list[HyprlandWindow] = []
        # dict[app_id, DockItem]
        self.__items: dict[str, AppDockView.Item] = {}
        # workspaces in the current monitor
        self.__monitor_ws: list[int] = []
        # focused workspace in the current monitor
        self.__active_ws: list[int] = []
        # current monitor connector/name
        self.__connector: str | None = None
        super().__init__()

        self.__pool = Pool(self.Item)
        self.__list_store = Gio.ListStore()
        self.flow_box.bind_model(self.__list_store, create_widget_func=lambda item: item)
        self.__defer_conceal: Timeout | None = None
        self.connect("realize", self.__on_realized)
        set_on_motion(self, enter=self.__on_mouse_enter, leave=self.__on_mouse_leave)

        drop_target = Gtk.DropTarget.new(str, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        drop_target.connect("enter", lambda *_: self.__on_mouse_enter() or 0)
        drop_target.connect("leave", self.__on_mouse_leave)
        self.add_controller(drop_target)

        self.__apps.connect("notify::pinned", self.__on_pinned_changed)
        if self.__niri.is_available:
            WindowFocusHistory.sync_windows(niri_windows=self.__niri.windows)
            self.__niri.connect("notify::workspaces", self.__on_workspaces_changed)
            self.__niri.connect("notify::windows", self.__on_windows_changed)
            self.__niri.connect(
                "notify::active-window", lambda *_: WindowFocusHistory.focus_window(self.__niri.active_window.id)
            )
            self.__niri.connect("notify::active-window", self.__on_windows_changed)
        if self.__hypr.is_available:
            WindowFocusHistory.sync_windows(hypr_windows=self.__hypr.windows)
            self.__hypr.connect("notify::workspaces", self.__on_workspaces_changed)
            self.__hypr.connect("notify::windows", self.__on_windows_changed)
            self.__hypr.connect(
                "notify::active-window", lambda *_: WindowFocusHistory.focus_window(self.__hypr.active_window.pid)
            )
            self.__hypr.connect("notify::active-window", self.__on_windows_changed)
            for monitor in self.__hypr.monitors:
                monitor: HyprlandMonitor
                monitor.connect("notify::active-workspace-id", self.__on_workspaces_changed)
        if self.__dock_options:
            connect_option(self.__dock_options, "auto_conceal", self.__on_auto_conceal_changed)
            connect_option(self.__dock_options, "monitor_only", self.__on_options_changed)
            connect_option(self.__dock_options, "workspace_only", self.__on_options_changed)

    def __on_realized(self, *_):
        monitor = get_widget_monitor(self)
        if monitor:
            self.__connector = monitor.get_connector()
        self.__on_auto_conceal_changed()

    def __on_mouse_enter(self, *_):
        if self.__defer_conceal:
            self.__defer_conceal.cancel()
            self.__defer_conceal = None
        self.conceal.set_reveal_child(False)
        self.revealer.set_reveal_child(True)

    def __on_mouse_leave(self, *_):
        if self.__dock_options and not self.__dock_options.auto_conceal:
            return

        delay = 1000
        if self.__dock_options:
            delay = self.__dock_options.conceal_delay
        self.__defer_conceal = Timeout(ms=delay, target=self.__conceal)

    def __conceal(self, *_):
        self.__defer_conceal = None
        self.conceal.set_reveal_child(True)
        self.revealer.set_reveal_child(False)

    def __on_auto_conceal_changed(self, *_):
        if not self.__dock_options:
            return

        if self.__dock_options.auto_conceal:
            self.__on_mouse_leave()
        else:
            self.__on_mouse_enter()

    def __on_options_changed(self, *_):
        self.__on_workspaces_changed()

    def __on_pinned_changed(self, *_):
        self.__refresh()

    def __on_workspaces_changed(self, *_):
        if self.__niri.is_available:
            niri_ws: list[NiriWorkspace] = self.__niri.get_workspaces()
            self.__monitor_ws = [ws.id for ws in niri_ws if ws.output == self.__connector]
            self.__active_ws = [ws.id for ws in niri_ws if ws.output == self.__connector and ws.is_active]
        if self.__hypr.is_available:
            hypr_monitors: list[HyprlandMonitor] = self.__hypr.get_monitors()
            ws_of_monitor: list[int] = [m.active_workspace_id for m in hypr_monitors if m.name == self.__connector]
            hypr_ws: list[HyprlandWorkspace] = self.__hypr.get_workspaces()
            self.__monitor_ws = [ws.id for ws in hypr_ws if ws.monitor == self.__connector]
            self.__active_ws = [ws.id for ws in hypr_ws if ws.monitor == self.__connector and ws.id in ws_of_monitor]
        self.__on_windows_changed()

    def __on_windows_changed(self, *_):
        if self.__niri.is_available:
            self.__niri_wins = self.__niri.get_windows()
            if self.__dock_options:
                if self.__dock_options.workspace_only:
                    self.__niri_wins = [win for win in self.__niri_wins if win.workspace_id in self.__active_ws]
                elif self.__dock_options.monitor_only:
                    self.__niri_wins = [win for win in self.__niri_wins if win.workspace_id in self.__monitor_ws]
        if self.__hypr.is_available:
            self.__hypr_wins = self.__hypr.get_windows()
            if self.__dock_options:
                if self.__dock_options.workspace_only:
                    self.__hypr_wins = [win for win in self.__hypr_wins if win.workspace_id in self.__active_ws]
                elif self.__dock_options.monitor_only:
                    self.__hypr_wins = [win for win in self.__hypr_wins if win.workspace_id in self.__monitor_ws]
        self.__refresh()

    def __refresh(self):
        self.__list_store.remove_all()

        pinned_set: set[str] = {get_app_id(app.id) for app in self.__apps.pinned if app.id}
        # all the items to display: pinned apps and open windows
        app_id_set = pinned_set
        if self.__niri.is_available:
            app_id_set = app_id_set | ({get_app_id(win.app_id) for win in self.__niri_wins})
        if self.__hypr.is_available:
            app_id_set = app_id_set | ({get_app_id(win.class_name) for win in self.__hypr_wins})

        # sync items to display
        app_dict: dict[str, Application] = {get_app_id(app.id): app for app in self.__apps.apps if app.id}
        for app_id in [app_id for app_id in self.__items if app_id not in app_id_set]:
            self.__pool.release(self.__items.pop(app_id))
        for app_id in app_id_set:
            dock_item = self.__items.get(app_id)
            if not dock_item:
                dock_item = self.__pool.acquire()
                self.__items[app_id] = dock_item
            dock_item.app_id = app_id
            dock_item.app_info = app_dict.get(app_id)

        # sync open windows to items
        if self.__niri.is_available:
            niri_map: dict[str, list[NiriWindow]] = {}
            for win in self.__niri_wins:
                app_id = get_app_id(win.app_id)
                if app_id not in niri_map:
                    niri_map[app_id] = []
                niri_map[app_id].append(win)
            for app_id, item in self.__items.items():
                item.niri_windows = niri_map.get(app_id)
        if self.__hypr.is_available:
            hypr_map: dict[str, list[HyprlandWindow]] = {}
            for win in self.__hypr_wins:
                app_id = get_app_id(win.class_name)
                if app_id not in hypr_map:
                    hypr_map[app_id] = []
                hypr_map[app_id].append(win)
            for app_id, item in self.__items.items():
                item.hypr_windows = hypr_map.get(app_id)

        # rebuild list_store
        for item in sorted(self.__items.values(), key=lambda i: (i.app_id not in pinned_set, i.app_id)):
            self.__list_store.append(item)


class AppDock(Widget.Window):
    __gtype_name__ = "IgnisAppDock"

    def __init__(self, monitor: int = 0):
        self.__options = user_options and user_options.appdock
        super().__init__(
            namespace=f"{WindowName.app_dock.value}-{monitor}",
            monitor=monitor,
            anchor=["bottom"],
            css_classes=["rounded-tl", "rounded-tr", "transparent"],
        )

        self.__view = AppDockView()
        self.set_child(self.__view)

        if self.__options:
            connect_option(self.__options, "exclusive", self.__on_exclusive_changed)
            connect_option(self.__options, "focusable", self.__on_focusable_changed)
            self.__on_exclusive_changed()

    def __on_exclusive_changed(self, *_):
        if not self.__options:
            return

        self.set_exclusivity("exclusive" if self.__options.exclusive else "normal")

    def __on_focusable_changed(self, *_):
        if not self.__options:
            return

        self.set_exclusivity("on_demand" if self.__options.focusable else "none")
