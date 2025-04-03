from gi.repository import Gio, Gtk
from ignis.widgets import Widget
from ignis.services.applications import ApplicationsService
from ignis.services.hyprland import HyprlandMonitor, HyprlandWindow, HyprlandWorkspace, HyprlandService
from ignis.services.niri import NiriWindow, NiriWorkspace, NiriService
from ignis.utils.timeout import Timeout
from .constants import WindowName
from .template import gtk_template, gtk_template_child
from .useroptions import user_options
from .utils import Pool, connect_option, get_app_icon_name, get_widget_monitor, set_on_click, set_on_motion


@gtk_template("appdock")
class AppDockView(Gtk.Box):
    __gtype_name__ = "IgnisAppDockView"

    conceal: Gtk.Revealer = gtk_template_child()
    revealer: Gtk.Revealer = gtk_template_child()
    flow_box: Gtk.FlowBox = gtk_template_child()

    class Item(Gtk.Box):
        __gtype_name__ = "IgnisAppDockItem"

        def __init__(self):
            self.__hypr = HyprlandService.get_default()
            self.__niri_win: NiriWindow | None = None
            self.__hypr_win: HyprlandWindow | None = None
            super().__init__()
            self.add_css_class("hover")
            self.add_css_class("p-1")
            self.add_css_class("rounded")

            self.__icon = Gtk.Image(pixel_size=48)
            self.append(self.__icon)
            set_on_click(self, left=self.__on_clicked)

        @property
        def niri_window(self) -> NiriWindow | None:
            return self.__niri_win

        @niri_window.setter
        def niri_window(self, win: NiriWindow):
            self.__niri_win = win
            self.__icon.set_from_icon_name(get_app_icon_name(win.app_id))
            self.set_tooltip_text(win.title)

        @property
        def hypr_window(self) -> HyprlandWindow | None:
            return self.__hypr_win

        @hypr_window.setter
        def hypr_window(self, win: HyprlandWindow):
            self.__hypr_win = win
            self.__icon.set_from_icon_name(get_app_icon_name(win.class_name))
            self.set_tooltip_text(win.title)

        def __on_clicked(self, *_):
            if self.__niri_win:
                self.__niri_win.focus()
            if self.__hypr_win:
                self.__hypr.send_command(f"dispatch focuswindow pid:{self.__hypr_win.pid}")
                self.__hypr.send_command("dispatch alterzorder top")

    def __init__(self):
        self.__dock_options = user_options and user_options.appdock
        self.__apps = ApplicationsService.get_default()
        self.__niri = NiriService.get_default()
        self.__hypr = HyprlandService.get_default()
        self.__niri_wins: list[NiriWindow] = []
        self.__hypr_wins: list[HyprlandWindow] = []
        self.__monitor_ws: list[int] = []
        self.__active_ws: list[int] = []
        self.__connector: str | None = None
        super().__init__()

        self.__pool = Pool(self.Item)
        self.__list_store = Gio.ListStore()
        self.flow_box.bind_model(self.__list_store, create_widget_func=lambda item: item)
        self.__defer_conceal: Timeout | None = None
        self.connect("realize", self.__on_realized)
        set_on_motion(self, enter=self.__on_mouse_enter, leave=self.__on_mouse_leave)

        self.__apps.connect("notify::pinned", self.__on_pinned_changed)
        if self.__niri.is_available:
            self.__niri.connect("notify::workspaces", self.__on_workspaces_changed)
            self.__niri.connect("notify::windows", self.__on_windows_changed)
        if self.__hypr.is_available:
            self.__hypr.connect("notify::workspaces", self.__on_workspaces_changed)
            self.__hypr.connect("notify::windows", self.__on_windows_changed)
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

    def __new_item(self, niri_win: NiriWindow | None = None, hypr_win: HyprlandWindow | None = None):
        item = self.__pool.acquire()
        if niri_win:
            item.niri_window = niri_win
        if hypr_win:
            item.hypr_window = hypr_win
        return item

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
        pass

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
        for item in self.__list_store:
            if isinstance(item, self.Item):
                self.__pool.release(item)
        self.__list_store.remove_all()

        if self.__niri.is_available:
            for win in self.__niri_wins:
                self.__list_store.append(self.__new_item(niri_win=win))
        if self.__hypr.is_available:
            for win in self.__hypr_wins:
                self.__list_store.append(self.__new_item(hypr_win=win))


class AppDock(Widget.Window):
    __gtype_name__ = "IgnisAppDock"

    def __init__(self, monitor: int = 0):
        super().__init__(
            namespace=f"{WindowName.app_dock.value}-{monitor}",
            monitor=monitor,
            layer="overlay",
            anchor=["bottom"],
            exclusivity="ignore",
        )
        self.add_css_class("rounded-tl")
        self.add_css_class("rounded-tr")
        self.add_css_class("transparent")

        self.__view = AppDockView()
        self.set_child(self.__view)
