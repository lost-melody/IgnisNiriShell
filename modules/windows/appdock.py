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
    SpecsBase,
    WeakMethod,
    connect_option,
    get_app_icon_name,
    get_app_id,
    get_widget_monitor,
    gtk_template,
    gtk_template_child,
    hypr_command,
    launch_application,
    niri_action,
    set_on_click,
    set_on_scroll,
)


class WindowInfo:
    """
    A wrapper to unify queries on ``NiriWindow`` and ``HyprlandWindow``.
    """

    def __init__(self, window: NiriWindow | HyprlandWindow):
        self.window = window

        self.id = 0
        self.pid = window.pid
        self.app_id = ""
        self.workspace_id = window.workspace_id
        self.title = window.title

        if isinstance(window, NiriWindow):
            self.id = window.id
            self.app_id = window.app_id
        else:
            self.id = window.pid
            self.app_id = window.class_name

    def focus(self):
        if isinstance(self.window, NiriWindow):
            self.window.focus()
        elif isinstance(self.window, HyprlandWindow):
            hypr_command(f"dispatch focuswindow pid:{self.window.pid}")
            hypr_command("dispatch alterzorder top")

    def maximize(self):
        self.focus()
        if isinstance(self.window, NiriWindow):
            if not self.window.is_floating:
                niri_action("MaximizeColumn")
        elif isinstance(self.window, HyprlandWindow):
            hypr_command("dispatch fullscreen 1")

    def fullscreen(self):
        self.focus()
        if isinstance(self.window, NiriWindow):
            niri_action("FullscreenWindow", {"id": self.window.id})
        elif isinstance(self.window, HyprlandWindow):
            hypr_command("dispatch fullscreen 0")

    def toggle_floating(self):
        self.focus()
        if isinstance(self.window, NiriWindow):
            niri_action("ToggleWindowFloating", {"id": self.window.id})
        elif isinstance(self.window, HyprlandWindow):
            hypr_command(f"dispatch togglefloating pid:{self.window.pid}")

    def close(self):
        if isinstance(self.window, NiriWindow):
            niri_action("CloseWindow", {"id": self.window.id})
        elif isinstance(self.window, HyprlandWindow):
            hypr_command(f"dispatch closewindow pid:{self.window.pid}")


class WindowFocusHistory:
    """
    Manages windows focus history.
    Every time a new window is focused, ``sequence`` is increased by one,
    and the window is assigned to the sequence.
    """

    initialized: bool = False
    sequence: int = 0
    focused_window_id: int = 0
    # dict[win_id, hist_id]
    focus_hist: dict[int, int] = {}

    @classmethod
    def get_focus_hist(cls, window_id: int):
        """
        Queries the focus sequence of the window.
        """
        return cls.focus_hist.get(window_id, 0)

    @classmethod
    def focus_window(cls, window_id: int):
        """
        Updates the current focused window id.
        """
        if cls.focused_window_id == window_id:
            return

        cls.sequence += 1
        cls.focus_hist[window_id] = cls.sequence

    @classmethod
    def find_latest_index(cls, windows: list[WindowInfo] | None = None):
        """
        Finds the index of the latest focused window in ``windows``.
        Returns ``-1`` if not found.
        """
        i = 0
        idx = -1
        latest = 0
        for win in windows or []:
            id = win.id
            hist = cls.get_focus_hist(id)
            if hist > latest:
                idx = i
                latest = hist
            i += 1
        return idx

    @classmethod
    def sync_windows(cls, windows: list[WindowInfo] | None = None):
        if not windows:
            cls.initialized = True
            return

        if cls.initialized:
            id_set = None
            if windows and len(windows) != len(cls.focus_hist):
                id_set = set(w.id for w in windows)
            if id_set:
                for id in id_set:
                    cls.focus_hist.pop(id, None)
        else:
            cls.initialized = True
            if windows:
                for id in [w.id for w in sorted(windows, key=lambda w: w.id)]:
                    cls.focus_window(id)


@gtk_template("appdock")
class AppDockView(Gtk.Box):
    __gtype_name__ = "IgnisAppDockView"

    @gtk_template("appdock-item")
    class Item(Gtk.FlowBoxChild, SpecsBase):
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
            self.__app_options = user_options and user_options.applauncher
            self.__app_id: str = ""
            self.__app_info: Application | None = None
            self.__windows: list[WindowInfo] = []
            super().__init__()
            SpecsBase.__init__(self)

            self.__idx: int = 0
            self.__menu = IgnisMenuModel()
            self.__dots_store = Gio.ListStore()
            self.dots.bind_model(self.__dots_store, lambda i: i)
            set_on_click(self.icon, left=WeakMethod(self.__on_clicked), right=WeakMethod(self.__on_right_clicked))
            set_on_scroll(self.icon, WeakMethod(self.__on_scrolled))

            drop_target = Gtk.DropTarget.new(str, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
            self.signal(drop_target, "drop", self.__on_drop_target)
            self.add_controller(drop_target)

        def do_dispose(self):
            self.menu.set_menu_model(None)
            self.__menu.clean_gmenu()
            self.clear_specs()
            self.dispose_template(self.__class__)
            super().do_dispose()  # type: ignore

        @property
        def app_id(self) -> str:
            return self.__app_id

        @app_id.setter
        def app_id(self, app_id: str):
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
        def windows(self) -> list[WindowInfo]:
            return self.__windows

        @windows.setter
        def windows(self, windows: list[WindowInfo]):
            self.__dots_store.remove_all()
            if windows:
                windows = sorted(windows, key=lambda w: w.id)
                self.__windows = windows

                idx = WindowFocusHistory.find_latest_index(windows)
                if idx < 0:
                    idx = 0

                self.set_tooltip_text(f"{self.app_id} - {windows[idx].title}")
                self.__update_dots(idx, len(windows))
                self.__idx = idx

            else:
                self.__windows = []
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
            windows = self.windows
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

        def __menu_windows(self, items: ItemsType, windows: list[WindowInfo]):
            # windows actions
            items.append(IgnisMenuItem("Active Windows", False))
            for win in windows:
                title = win.title
                title = title if len(title) < 32 else title[:32] + "..."
                items.append(
                    IgnisMenuModel(
                        IgnisMenuItem(f"pid: {win.pid}", False),
                        IgnisMenuItem("Focus", True, lambda _, win=win: win.focus()),
                        IgnisMenuItem("Maximize", True, lambda _, win=win: win.maximize()),
                        IgnisMenuItem("Fullscreen", True, lambda _, win=win: win.fullscreen()),
                        IgnisMenuItem("Toggle Floating", True, lambda _, win=win: win.toggle_floating()),
                        IgnisMenuItem("Close", True, lambda _, win=win: win.close()),
                        label=title,
                    )
                )

            # close all windows
            def close_all_windows(wins: list[WindowInfo]):
                for win in wins:
                    win.close()

            items.append(IgnisMenuItem("Close All Windows", True, lambda _: close_all_windows(windows)))

        def __launch_app(self, files: list[str] | None = None):
            if not self.app_info:
                return

            command_format = self.__app_options.command_format
            terminal_format = self.__app_options.terminal_format

            launch_application(
                self.app_info, files=files, command_format=command_format, terminal_format=terminal_format
            )

        def __on_clicked(self, *_):
            if self.windows:
                self.windows[self.__idx].focus()
            elif self.app_info:
                self.__launch_app()

        def __on_right_clicked(self, *_):
            self.menu.popup()

        def __on_scrolled(self, _, dx: float, dy: float):
            delta = 1 if dx + dy > 0 else -1
            if self.windows:
                idx = WindowFocusHistory.find_latest_index(self.windows)
                if idx >= 0:
                    idx = (idx + delta) % len(self.windows)
                else:
                    idx = 0
                self.windows[idx].focus()

        def __on_drop_target(self, controller: Gtk.DropTarget, value: str, x: float, y: float):
            files = value.split("\n")
            if self.app_info and files:
                self.__launch_app(files)

    conceal: Gtk.Revealer = gtk_template_child()
    revealer: Gtk.Revealer = gtk_template_child()
    flow_box: Gtk.FlowBox = gtk_template_child()

    def __init__(self):
        self.__dock_options = user_options.appdock
        self.__apps = ApplicationsService.get_default()
        self.__niri = NiriService.get_default()
        self.__hypr = HyprlandService.get_default()

        self.__windows: list[WindowInfo] = []
        """Windows to display in dock."""
        self.__items: dict[str, AppDockView.Item] = {}
        """Maps ``app_id`` to ``DockItem``."""
        self.__monitor_ws: set[int] = set()
        """Workspace ids in the current monitor."""
        self.__active_ws: set[int] = set()
        """Focused workspace ids in any monitors."""
        self.__connector: str | None = None
        """Currently focused monitor connector/name."""

        super().__init__()

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
            WindowFocusHistory.sync_windows([WindowInfo(w) for w in self.__niri.windows])
            self.__niri.connect("notify::workspaces", self.__on_workspaces_changed)
            self.__niri.connect("notify::windows", self.__on_windows_changed)
            self.__niri.connect(
                "notify::active-window", lambda *_: WindowFocusHistory.focus_window(self.__niri.active_window.id)
            )
            self.__niri.connect("notify::active-window", self.__on_windows_changed)
            self.__niri.connect("notify::overview-opened", self.__on_overview_changed)
        if self.__hypr.is_available:
            WindowFocusHistory.sync_windows([WindowInfo(w) for w in self.__hypr.windows])
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
            self.__monitor_ws = set(ws.id for ws in self.__niri.workspaces if ws.output == self.__connector)
            self.__active_ws = set(ws.id for ws in self.__niri.workspaces if ws.is_active)
        elif self.__hypr.is_available:
            self.__monitor_ws = set(ws.id for ws in self.__hypr.workspaces if ws.monitor == self.__connector)
            self.__active_ws = set(m.active_workspace_id for m in self.__hypr.monitors)
        else:
            return

        self.__on_windows_changed()

    def __on_windows_changed(self, *_):
        self.__windows = [
            WindowInfo(win) for win in (self.__niri.windows if self.__niri.is_available else self.__hypr.windows)
        ]
        if self.__dock_options.monitor_only:
            self.__windows = [win for win in self.__windows if win.workspace_id in self.__monitor_ws]
        elif self.__dock_options.workspace_only:
            self.__windows = [win for win in self.__windows if win.workspace_id in self.__monitor_ws & self.__active_ws]

        self.__refresh()

    def __refresh(self):
        pinned_set = {get_app_id(app.id) for app in self.__apps.pinned if app.id}
        # all the items to display: pinned apps and open windows
        app_id_set = pinned_set | ({get_app_id(win.app_id) for win in self.__windows})
        # map app id to app info
        app_dict = {get_app_id(app.id): app for app in self.__apps.apps if app.id}

        # remove dock items that are not in app_id_set
        for app_id in [app_id for app_id in self.__items if app_id not in app_id_set]:
            dock_item = self.__items.pop(app_id)
            self.flow_box.remove(dock_item)
            dock_item.run_dispose()
        # create missing dock items from app_id_set
        for app_id in app_id_set:
            dock_item = self.__items.get(app_id)
            if not dock_item:
                dock_item = self.Item()
                self.__items[app_id] = dock_item
                self.flow_box.append(dock_item)
            dock_item.app_id = app_id
            dock_item.app_info = app_dict.get(app_id)

        # sync open windows to dock items
        app_windows: dict[str, list[WindowInfo]] = {}
        for window in self.__windows:
            app_id = get_app_id(window.app_id)
            if app_id not in app_windows:
                app_windows[app_id] = []
            app_windows[app_id].append(window)
        for app_id, item in self.__items.items():
            item.windows = app_windows.get(app_id, [])

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
            self.__on_focusable_changed()

    def __on_exclusive_changed(self, *_):
        if not self.__options:
            return

        self.exclusivity = "exclusive" if self.__options.exclusive else "normal"

    def __on_focusable_changed(self, *_):
        if not self.__options:
            return

        self.focusable = "on_demand" if self.__options.focusable else "none"
