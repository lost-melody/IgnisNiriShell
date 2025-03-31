from typing import Any, Callable
from gi.repository import GLib, Gio, GObject, Gtk
from ignis.app import IgnisApp
from ignis.widgets import Widget
from ignis.services.applications import Application, ApplicationAction, ApplicationsService
from .backdrop import overlay_window
from .constants import WindowName
from .template import gtk_template, gtk_template_callback, gtk_template_child
from .useroptions import user_options, UserOptions
from .utils import Pool, b64enc, connect_window, gproperty, set_on_click


app = IgnisApp.get_default()


@gtk_template(filename="applauncher-item")
class AppLauncherGridItem(Gtk.Box):
    __gtype_name__ = "IgnisAppLauncherGridItem"

    icon: Gtk.Image = gtk_template_child()
    label: Gtk.Label = gtk_template_child()
    menu: Gtk.PopoverMenu = gtk_template_child()

    def __init__(self):
        super().__init__()

        self._pos: int | None = None
        self._app: Application | None = None
        self._menu = Gio.Menu()
        self.menu.set_menu_model(self._menu)

        set_on_click(self, left=self.__on_left_click, right=self.__on_right_click)

    def __on_left_click(self, *_):
        if self._pos is not None:
            pos = GLib.Variant.new_uint32(self._pos)
            self.activate_action("list.activate-item", pos)

    def __on_right_click(self, *_):
        self.menu.popup()

    def __add_menu_item(self, label: str, action: str):
        item = Gio.MenuItem.new(label=label, detailed_action=action)
        self._menu.append_item(item)

    @property
    def app_id(self) -> str:
        if self.application:
            return self.application.get_id() or ""
        return ""

    @property
    def position(self) -> int | None:
        return self._pos

    @position.setter
    def position(self, pos: int | None):
        self._pos = pos

    @property
    def application(self) -> Application | None:
        return self._app

    @application.setter
    def application(self, app: Application | None):
        self._app = app
        self._menu.remove_all()

        if app is None:
            return

        self.icon.set_from_icon_name(app.get_icon())
        self.label.set_text(app.get_name())
        self.set_tooltip_text(app.get_description())

        if app.get_id() is None:
            return

        app_id_b64 = b64enc(app.get_id())
        self.__add_menu_item("Launch", f"app_grid.{app_id_b64}")
        actions: list[ApplicationAction] = app.get_actions()
        for act in actions:
            app_act_b64 = b64enc(act.action)
            self.__add_menu_item(act.get_name(), f"app_grid.{app_id_b64}.{app_act_b64}")


@gtk_template(filename="applauncher")
class AppLauncherView(Gtk.Box):
    __gtype_name__ = "IgnisAppLauncherView"

    revealer: Widget.Revealer = gtk_template_child()
    search_bar: Gtk.SearchBar = gtk_template_child()
    search_entry: Gtk.SearchEntry = gtk_template_child()
    app_grid: Gtk.ListView = gtk_template_child()
    selection: Gtk.SingleSelection = gtk_template_child()
    sort_list: Gtk.SortListModel = gtk_template_child()
    filter_list: Gtk.FilterListModel = gtk_template_child()
    list_store: Gio.ListStore = gtk_template_child()

    def __init__(self):
        self.__service = ApplicationsService.get_default()
        super().__init__()
        self.__group = Gio.SimpleActionGroup()
        self.insert_action_group(name="app_grid", group=self.__group)

        self.__filter = Gtk.CustomFilter()
        self.__sorter = Gtk.CustomSorter()
        self.filter_list.set_filter(self.__filter)
        self.sort_list.set_sorter(self.__sorter)

        self.__pool = Pool(AppLauncherGridItem)
        self.__service.connect("notify::apps", self.__on_apps_changed)
        connect_window(self, "notify::visible", self.__on_window_visible_change)

        self.__app_options: UserOptions.AppLauncher | None = None
        if user_options and user_options.applauncher:
            self.__app_options = user_options.applauncher

    def __on_apps_changed(self, *_):
        for item in self.list_store:
            if isinstance(item, AppLauncherGridItem):
                self.__pool.release(item)
        self.list_store.remove_all()

        apps: list[Application] = self.__service.get_apps()
        for app in apps:
            item = self.__pool.acquire()
            item.application = app
            self.list_store.append(item)

            if app.get_id() is None:
                continue

            app_id_b64 = b64enc(app.get_id())
            self.__add_action(app_id_b64, lambda app=app: self.__launch_app(app))
            actions: list[ApplicationAction] = app.get_actions()
            for act in actions:
                app_act_b64 = b64enc(act.action)
                self.__add_action(f"{app_id_b64}.{app_act_b64}", act.launch)

    def __launch_app(self, app: Application):
        command_format: str | None = None
        terminal_format: str | None = None
        if self.__app_options:
            command_format = self.__app_options.command_format
            terminal_format = self.__app_options.terminal_format
        app.launch(command_format=command_format, terminal_format=terminal_format)

    def __add_action(self, name: str, callback: Callable[[], Any]):
        def do_action(*_):
            callback()
            self.on_search_stop()

        action = Gio.SimpleAction(name=name)
        action.connect("activate", do_action)
        self.__group.add_action(action)

    def __move_selection(self, delta: int):
        pos, count = self.selection.get_selected(), self.selection.get_n_items()
        if count == 0:
            return

        pos = (pos + delta) % count
        if pos >= count:
            self.selection.set_selected(pos)

        self.app_grid.scroll_to(pos, Gtk.ListScrollFlags.FOCUS | Gtk.ListScrollFlags.SELECT)

        if not self.search_bar.get_search_mode():
            self.app_grid.grab_focus()

    def __on_window_visible_change(self, window: Widget.Window, _):
        if not window.get_visible():
            self.search_bar.set_search_mode(False)

    def __apps_filter(self, app: AppLauncherGridItem, result: dict[str, int]) -> bool:
        return app.app_id in result

    def __apps_sorter(self, a: AppLauncherGridItem, b: Application, result: dict[str, int]) -> int:
        pa, pb = result.get(a.app_id), result.get(b.app_id)
        return (pa or 0) - (pb or 0)

    @gtk_template_callback
    def on_items_changed(self, *_):
        self.selection.set_selected(0)
        self.__move_selection(0)

        pos = 0
        for item in self.selection:
            if isinstance(item, AppLauncherGridItem):
                item.position = pos
            pos += 1

    @gtk_template_callback
    def on_item_activate(self, _: Gtk.ListView, pos: int):
        item = self.selection.get_item(pos)
        if isinstance(item, AppLauncherGridItem) and item.application:
            self.__launch_app(item.application)
        self.on_search_stop()

    @gtk_template_callback
    def on_search_activate(self, *_):
        pos = GLib.Variant.new_uint32(self.selection.get_selected())
        self.app_grid.activate_action("list.activate-item", pos)

    @gtk_template_callback
    def on_search_changed(self, *_):
        search_text = self.search_entry.get_text()
        if search_text != "":
            search_result = {
                app_id: priority
                for priority, result in enumerate(Gio.DesktopAppInfo.search(search_text))
                for app_id in result
            }
            self.__filter.set_filter_func(self.__apps_filter, search_result)
            self.__sorter.set_sort_func(self.__apps_sorter, search_result)
        else:
            self.__filter.set_filter_func(None)
            self.__sorter.set_sort_func(None)

    @gtk_template_callback
    def on_search_next(self, *_):
        self.__move_selection(1)

    @gtk_template_callback
    def on_search_previous(self, *_):
        self.__move_selection(-1)

    @gtk_template_callback
    def on_search_stop(self, *_):
        self.emit("search-stop")

    @GObject.Signal
    def search_stop(self):
        pass


class AppLauncher(Widget.RevealerWindow):
    __gtype_name__ = "IgnisAppLauncher"

    def __init__(self):
        super().__init__(
            namespace=WindowName.app_launcher.value,
            kb_mode="exclusive",
            layer="overlay",
            popup=True,
            visible=False,
            revealer=Widget.Revealer(),
        )
        self.add_css_class("rounded")

        self.__view = AppLauncherView()
        self.set_child(self.__view)
        self.set_revealer(self.__view.revealer)

        self.__view.search_bar.set_key_capture_widget(self)
        self.__add_shortcut("<Control>f", self.__toggle_search_mode)
        self.__add_shortcut("<Control>bracketleft", self.__on_search_stop)
        self.__add_shortcut("<Control>n", self.__view.on_search_next)
        self.__add_shortcut("<Control>p", self.__view.on_search_previous)
        self.__add_shortcut("<Control>j", self.__view.on_search_next)
        self.__add_shortcut("<Control>k", self.__view.on_search_previous)

        self.__view.connect("search-stop", self.__on_search_stop)
        self.connect("notify::visible", self.__on_visible_changed)

    def __add_shortcut(self, trigger: str, callback: Callable[[], Any]):
        def cb(*_) -> bool:
            callback()
            return True

        shortcut = Gtk.Shortcut.new(
            trigger=Gtk.ShortcutTrigger.parse_string(trigger), action=Gtk.CallbackAction.new(cb)
        )
        self.add_shortcut(shortcut)

    def __toggle_search_mode(self, *_):
        search_mode = not self.__view.search_bar.get_search_mode()
        self.__view.search_bar.set_search_mode(search_mode)

        if not search_mode:
            self.__view.app_grid.grab_focus()

    def __on_search_stop(self, *_):
        self.set_visible(False)

    def __on_visible_changed(self, *_):
        if self.get_visible():
            overlay_window.set_window(self.get_namespace())
        else:
            overlay_window.unset_window(self.get_namespace())
