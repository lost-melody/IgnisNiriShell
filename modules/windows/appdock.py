from gi.repository import Gdk, Gio, Gtk
from ignis.menu_model import IgnisMenuItem, IgnisMenuModel, IgnisMenuSeparator, ItemsType
from ignis.services.applications import Application, ApplicationsService
from ignis.services.hyprland import HyprlandService, HyprlandWindow
from ignis.services.niri import NiriService, NiriWindow
from ignis.utils import Timeout
from ignis.widgets import Window

from ..constants import WindowName
from ..useroptions import user_options
from ..utils import (
    Pool,
    connect_option,
    get_app_icon_name,
    get_app_id,
    get_widget_monitor,
    gtk_template,
    gtk_template_child,
    launch_application,
    niri_action,
    set_on_click,
    set_on_scroll,
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
                    else types.SLIDE_LEFT
                    if direction == "right"
                    else types.CROSSFADE
                )
                self.__revealer.set_transition_type(transition)
                self.__revealer.set_reveal_child(reveal)

        icon: Gtk.Image = gtk_template_child()
        menu: Gtk.PopoverMenu = gtk_template_child()
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

            self.__idx: int = 0
            self.__menu = IgnisMenuModel()
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
                self.__idx = idx
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
                self.__idx = idx
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

        def rebuild_menu(self):
            self.menu.set_menu_model(None)
            self.__menu.clean_gmenu()

            items: ItemsType = []
            # application menu
            if self.app_info:
                app = self.app_info
                self.__menu_application(items, app)

            # active windows menu
            windows = self.niri_windows or self.hypr_windows
            if windows:
                if items:
                    items.append(IgnisMenuSeparator())
                self.__menu_windows(items, windows)

            self.__menu.items = items
            self.menu.set_menu_model(self.__menu.gmenu)

        def __menu_application(self, items: ItemsType, app: Application):
            # application launch and pin/unpin
            items.append(IgnisMenuItem("Application", False))
            items.append(IgnisMenuItem("Launch", True, lambda _: self.__launch_app()))
            items.append(
                IgnisMenuItem(
                    label="Unpin" if app.is_pinned else "Pin",
                    enabled=True,
                    on_activate=lambda _: app.unpin() if app.is_pinned else app.pin(),
                )
            )
            # application actions
            if app.actions:
                items.append(IgnisMenuSeparator())
            for action in app.actions:
                items.append(IgnisMenuItem(action.name, True, lambda _, act=action: act.launch()))

        def __menu_windows(self, items: ItemsType, windows: list[NiriWindow] | list[HyprlandWindow]):
            # windows actions
            items.append(IgnisMenuItem("Active Windows", False))
            for win in windows:
                title = win.title
                title = title if len(title) < 32 else title[:32] + "..."
                items.append(
                    IgnisMenuModel(
                        IgnisMenuItem(f"pid: {win.pid}", False),
                        IgnisMenuItem("Focus", True, lambda _, win=win: self.__focus_window(win)),
                        IgnisMenuItem("Maximize", True, lambda _, win=win: self.__maximize_window(win)),
                        IgnisMenuItem("Fullscreen", True, lambda _, win=win: self.__fullscreen_window(win)),
                        IgnisMenuItem("Toggle Floating", True, lambda _, win=win: self.__toggle_floating_window(win)),
                        IgnisMenuItem("Close", True, lambda _, win=win: self.__close_window(win)),
                        label=title,
                    )
                )

            # close all windows
            def close_all_windows(wins: list[NiriWindow] | list[HyprlandWindow]):
                for win in wins:
                    self.__close_window(win)

            items.append(IgnisMenuItem("Close All Windows", True, lambda _: close_all_windows(windows)))

        def __focus_window(self, window: NiriWindow | HyprlandWindow):
            if isinstance(window, NiriWindow):
                window.focus()
            elif isinstance(window, HyprlandWindow):
                self.__hypr.send_command(f"dispatch focuswindow pid:{window.pid}")
                self.__hypr.send_command("dispatch alterzorder top")

        def __maximize_window(self, window: NiriWindow | HyprlandWindow):
            if isinstance(window, NiriWindow):
                window.focus()
                if not window.is_floating:
                    niri_action("MaximizeColumn")
            elif isinstance(window, HyprlandWindow):
                self.__focus_window(window)
                self.__hypr.send_command("dispatch fullscreen 1")

        def __fullscreen_window(self, window: NiriWindow | HyprlandWindow):
            if isinstance(window, NiriWindow):
                window.focus()
                niri_action("FullscreenWindow", {"id": window.id})
            elif isinstance(window, HyprlandWindow):
                self.__focus_window(window)
                self.__hypr.send_command("dispatch fullscreen 0")

        def __toggle_floating_window(self, window: NiriWindow | HyprlandWindow):
            if isinstance(window, NiriWindow):
                window.focus()
                niri_action("ToggleWindowFloating", {"id": window.id})
            elif isinstance(window, HyprlandWindow):
                self.__focus_window(window)
                self.__hypr.send_command(f"dispatch togglefloating pid:{window.pid}")

        def __close_window(self, window: NiriWindow | HyprlandWindow):
            if isinstance(window, NiriWindow):
                niri_action("CloseWindow", {"id": window.id})
            elif isinstance(window, HyprlandWindow):
                self.__hypr.send_command(f"dispatch closewindow pid:{window.pid}")

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
                self.__focus_window(self.niri_windows[self.__idx])
            elif self.hypr_windows:
                self.__focus_window(self.hypr_windows[self.__idx])
            elif self.app_info:
                self.__launch_app()

        def __on_right_clicked(self, *_):
            self.menu.popup()

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
        self.flow_box.set_sort_func(self.__dock_item_sorter)

        self.__defer_conceal: Timeout | None = None
        self.connect("realize", self.__on_realized)
        self.__prelight = False
        self.connect("state-flags-changed", self.__on_state_flags_changed)

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
            self.__niri.connect("notify::overview-opened", self.__on_overview_changed)
        if self.__hypr.is_available:
            WindowFocusHistory.sync_windows(hypr_windows=self.__hypr.windows)
            self.__hypr.connect("notify::workspaces", self.__on_workspaces_changed)
            self.__hypr.connect("notify::windows", self.__on_windows_changed)
            self.__hypr.connect(
                "notify::active-window", lambda *_: WindowFocusHistory.focus_window(self.__hypr.active_window.pid)
            )
            self.__hypr.connect("notify::active-window", self.__on_windows_changed)
            for monitor in self.__hypr.monitors:
                monitor.connect("notify::active-workspace-id", self.__on_workspaces_changed)
        if self.__dock_options:
            connect_option(self.__dock_options, "auto_conceal", self.__on_auto_conceal_changed)
            connect_option(self.__dock_options, "monitor_only", self.__on_options_changed)
            connect_option(self.__dock_options, "workspace_only", self.__on_options_changed)

    def __on_state_flags_changed(self, *_):
        flags = self.get_state_flags()
        prelight = Gtk.StateFlags.PRELIGHT & flags != 0
        if prelight == self.__prelight:
            return

        self.__prelight = prelight
        if self.__prelight:
            self.__on_mouse_enter()
        else:
            self.__on_mouse_leave()

    def __on_realized(self, *_):
        monitor = get_widget_monitor(self)
        if monitor:
            self.__connector = monitor.get_connector()
        self.__on_auto_conceal_changed()

    def __on_overview_changed(self, *_):
        if self.__dock_options and self.__dock_options.show_in_overview:
            if self.__niri.overview_opened:
                self.__on_mouse_enter()
            else:
                self.__on_mouse_leave()

    def __on_mouse_enter(self, *_):
        if self.__defer_conceal:
            self.__defer_conceal.cancel()
            self.__defer_conceal = None
        self.conceal.set_reveal_child(False)
        self.revealer.set_reveal_child(True)

    def __on_mouse_leave(self, *_):
        if self.__dock_options:
            if not self.__dock_options.auto_conceal:
                return
            if self.__dock_options.show_in_overview and self.__niri.overview_opened:
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

    def __dock_item_sorter(self, a: Item, b: Item) -> int:
        def key(item: AppDockView.Item):
            pinned = item.app_info and item.app_info.is_pinned or False
            return (not pinned, item.app_id)

        ka, kb = key(a), key(b)
        return (ka > kb) - (ka < kb)

    def __on_options_changed(self, *_):
        self.__on_workspaces_changed()

    def __on_pinned_changed(self, *_):
        self.__refresh()

    def __on_workspaces_changed(self, *_):
        if self.__niri.is_available:
            niri_ws = self.__niri.workspaces
            self.__monitor_ws = [ws.id for ws in niri_ws if ws.output == self.__connector]
            self.__active_ws = [ws.id for ws in niri_ws if ws.output == self.__connector and ws.is_active]
        if self.__hypr.is_available:
            hypr_monitors = self.__hypr.monitors
            ws_of_monitor = [m.active_workspace_id for m in hypr_monitors if m.name == self.__connector]
            hypr_ws = self.__hypr.workspaces
            self.__monitor_ws = [ws.id for ws in hypr_ws if ws.monitor == self.__connector]
            self.__active_ws = [ws.id for ws in hypr_ws if ws.monitor == self.__connector and ws.id in ws_of_monitor]
        self.__on_windows_changed()

    def __on_windows_changed(self, *_):
        if self.__niri.is_available:
            self.__niri_wins = self.__niri.windows
            if self.__dock_options:
                if self.__dock_options.workspace_only:
                    self.__niri_wins = [win for win in self.__niri_wins if win.workspace_id in self.__active_ws]
                elif self.__dock_options.monitor_only:
                    self.__niri_wins = [win for win in self.__niri_wins if win.workspace_id in self.__monitor_ws]
        if self.__hypr.is_available:
            self.__hypr_wins = self.__hypr.windows
            if self.__dock_options:
                if self.__dock_options.workspace_only:
                    self.__hypr_wins = [win for win in self.__hypr_wins if win.workspace_id in self.__active_ws]
                elif self.__dock_options.monitor_only:
                    self.__hypr_wins = [win for win in self.__hypr_wins if win.workspace_id in self.__monitor_ws]
        self.__refresh()

    def __refresh(self):
        pinned_set = {get_app_id(app.id) for app in self.__apps.pinned if app.id}
        # all the items to display: pinned apps and open windows
        app_id_set = pinned_set
        if self.__niri.is_available:
            app_id_set = app_id_set | ({get_app_id(win.app_id) for win in self.__niri_wins})
        if self.__hypr.is_available:
            app_id_set = app_id_set | ({get_app_id(win.class_name) for win in self.__hypr_wins})

        # sync items to display
        app_dict = {get_app_id(app.id): app for app in self.__apps.apps if app.id}
        for app_id in [app_id for app_id in self.__items if app_id not in app_id_set]:
            self.flow_box.remove(self.__items[app_id])
            self.__pool.release(self.__items.pop(app_id))
        for app_id in app_id_set:
            dock_item = self.__items.get(app_id)
            if not dock_item:
                dock_item = self.__pool.acquire()
                self.__items[app_id] = dock_item
                self.flow_box.append(dock_item)
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

        # refresh flow_box
        for item in self.__items.values():
            item.rebuild_menu()
        self.flow_box.invalidate_sort()


class AppDock(Window):
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

        self.exclusivity = "exclusive" if self.__options.exclusive else "normal"

    def __on_focusable_changed(self, *_):
        if not self.__options:
            return

        self.focusable = "on_demand" if self.__options.focusable else "none"
