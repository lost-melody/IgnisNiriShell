from gi.repository import Gtk
from ignis.services.hyprland import HyprlandService, HyprlandWorkspace
from ignis.services.niri import NiriService, NiriWorkspace

from ..utils import SpecsBase, get_widget_monitor, niri_action, set_on_click, set_on_scroll


class Workspaces(Gtk.Box):
    __gtype_name__ = "NiriWorkspaces"

    class WorkspaceItem(Gtk.Box, SpecsBase):
        __gtype_name__ = "WorkspaceItem"

        def __init__(self):
            self.__niri = NiriService.get_default()
            self.__hypr = HyprlandService.get_default()
            self.__niri_ws: NiriWorkspace | None = None
            self.__hypr_ws: HyprlandWorkspace | None = None
            super().__init__()
            SpecsBase.__init__(self)

            self.__icon = Gtk.Image(icon_name="pager-checked-symbolic")
            self.append(self.__icon)

            set_on_click(self, left=self.__class__.__on_clicked)
            if self.__niri.is_available:
                self.signal(self.__niri, "notify::active-workspace", self.__on_changed)
            if self.__hypr.is_available:
                self.signal(self.__hypr, "notify::active-workspace", self.__on_changed)

        def do_dispose(self):
            self.clear_specs()
            super().do_dispose()  # type: ignore

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
        self.__childs: list[Workspaces.WorkspaceItem] = []
        super().__init__(css_classes=["hover", "rounded", "p-2"])

        self.connect("realize", self.__class__.__on_realize)
        set_on_scroll(self, self.__class__.__on_scroll)

        if self.__niri.is_available:
            self.__niri.connect("notify::workspaces", self.__on_change)

        if self.__hypr.is_available:
            self.__hypr.connect("notify::workspaces", self.__on_change)

    def __new_item(self, niri_ws: NiriWorkspace | None = None, hypr_ws: HyprlandWorkspace | None = None):
        item = self.WorkspaceItem()
        if niri_ws:
            item.niri_ws = niri_ws
        if hypr_ws:
            item.hypr_ws = hypr_ws
        return item

    def __on_realize(self):
        monitor = get_widget_monitor(self)
        if monitor:
            self.__connector = monitor.get_connector()

    def __on_change(self, *_):
        for item in self.__childs:
            self.remove(item)
            item.run_dispose()
        self.__childs = []

        if self.__niri.is_available:
            self.__childs = [
                self.__new_item(niri_ws=ws) for ws in self.__niri.workspaces if ws.output == self.__connector
            ]
        if self.__hypr.is_available:
            self.__childs = [
                self.__new_item(hypr_ws=ws) for ws in self.__hypr.workspaces if ws.monitor == self.__connector
            ]
        for item in self.__childs:
            self.append(item)

    def __on_scroll(self, dx: float, dy: float):
        if self.__niri.is_available:
            niri_action(f"FocusWorkspace{'Up' if dx + dy < 0 else 'Down'}")
        if self.__hypr.is_available:
            self.__hypr.send_command(f"dispatch workspace {'r-1' if dx + dy < 0 else 'r+1'}")
