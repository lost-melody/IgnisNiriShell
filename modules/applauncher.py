from typing import Any, Callable
from gi.repository import Gio, GObject, Gtk
from ignis.app import IgnisApp
from ignis.menu_model import IgnisMenuItem, IgnisMenuModel, IgnisMenuSeparator, ItemsType
from ignis.widgets import Widget
from ignis.services.applications import Application, ApplicationAction, ApplicationsService
from .backdrop import overlay_window
from .constants import WindowName
from .template import gtk_template, gtk_template_callback, gtk_template_child
from .useroptions import user_options
from .utils import Pool, connect_window, get_app_icon_name, launch_application, set_on_click
from .widgets import RevealerWindow


app = IgnisApp.get_default()


@gtk_template(filename="applauncher-item")
class AppLauncherGridItem(Gtk.Box):
    __gtype_name__ = "IgnisAppLauncherGridItem"

    icon: Gtk.Image = gtk_template_child()
    label: Gtk.Label = gtk_template_child()
    menu: Gtk.PopoverMenu = gtk_template_child()

    def __init__(self):
        super().__init__()

        self._app: Application | None = None
        self._menu = IgnisMenuModel()
        self.__app_signals: list[tuple[Application, int]] = []

        set_on_click(self, left=self.__on_left_click, right=self.__on_right_click)

    def __on_left_click(self, *_):
        self.__launch_app()

    def __on_right_click(self, *_):
        self.menu.popup()

    def __launch_app(self):
        if not self.application:
            return

        view = self.get_ancestor(AppLauncherView)
        if isinstance(view, AppLauncherView):
            view.launch_application(self.application)
            view.on_search_stop()

    def __launch_action(self, action: ApplicationAction):
        action.launch()
        view = self.get_ancestor(AppLauncherView)
        if isinstance(view, AppLauncherView):
            view.on_search_stop()

    def __rebuild_menu(self):
        self.menu.set_menu_model()
        self._menu.clean_gmenu()

        if not self.application:
            return

        app = self.application
        items: ItemsType = []
        items.append(IgnisMenuItem("Launch", True, lambda _: self.__launch_app()))
        items.append(
            IgnisMenuItem(
                label="Unpin" if app.is_pinned else "Pin",
                enabled=True,
                on_activate=lambda _: app.unpin() if app.is_pinned else app.pin(),
            )
        )

        if app.actions:
            items.append(IgnisMenuSeparator())
        for action in app.actions:
            items.append(IgnisMenuItem(action.name, True, lambda _, act=action: self.__launch_action(act)))

        self._menu.items = items
        self.menu.set_menu_model(self._menu.gmenu)

    def __connect_app_signals(self):
        for obj, id in self.__app_signals:
            obj.disconnect(id)
        self.__app_signals.clear()

        if not self.application:
            return

        app = self.application
        id = app.connect("notify::is-pinned", lambda *_: self.__rebuild_menu())
        self.__app_signals.append((app, id))

    @property
    def application(self) -> Application | None:
        return self._app

    @application.setter
    def application(self, app: Application | None):
        self._app = app
        self.__rebuild_menu()
        self.__connect_app_signals()

        if app is None:
            return

        self.icon.set_from_icon_name(get_app_icon_name(app_info=app))
        self.label.set_text(app.name)
        self.set_tooltip_text(app.description)


@gtk_template(filename="applauncher")
class AppLauncherView(Gtk.Box):
    __gtype_name__ = "IgnisAppLauncherView"

    revealer: Gtk.Revealer = gtk_template_child()
    search_bar: Gtk.SearchBar = gtk_template_child()
    search_entry: Gtk.SearchEntry = gtk_template_child()
    app_grid: Gtk.ListView = gtk_template_child()
    selection: Gtk.SingleSelection = gtk_template_child()
    sort_list: Gtk.SortListModel = gtk_template_child()
    filter_list: Gtk.FilterListModel = gtk_template_child()
    list_store: Gio.ListStore = gtk_template_child()

    class Factory(Gtk.SignalListItemFactory):
        def __init__(self):
            super().__init__()

            self.__pool = Pool(AppLauncherGridItem)
            # we don't connect to "setup" or "teardown" signals
            # instead we acquire and release childs in "bind" and "unbind"
            self.connect("bind", self.__item_bind)
            self.connect("unbind", self.__item_unbind)

        def __item_bind(self, _, item: Gtk.ListItem):
            self.__item_unbind(_, item)

            grid_item = self.__pool.acquire()
            app = item.get_item()
            if isinstance(app, Application):
                grid_item.application = app
                item.set_child(grid_item)

        def __item_unbind(self, _, item: Gtk.ListItem):
            grid_item = item.get_child()
            if isinstance(grid_item, AppLauncherGridItem):
                grid_item.application = None
                self.__pool.release(grid_item)

    def __init__(self):
        self.__service = ApplicationsService.get_default()
        super().__init__()

        self.__filter = Gtk.CustomFilter()
        self.__sorter = Gtk.CustomSorter()
        self.app_grid.set_factory(self.Factory())
        self.filter_list.set_filter(self.__filter)
        self.sort_list.set_sorter(self.__sorter)

        self.__service.connect("notify::apps", self.__on_apps_changed)
        connect_window(self, "notify::visible", self.__on_window_visible_change)

        self.__app_options = user_options and user_options.applauncher

    def __on_apps_changed(self, *_):
        self.list_store.remove_all()

        apps = self.__service.apps
        for app in apps:
            self.list_store.append(app)

    def launch_application(self, app: Application):
        command_format = self.__app_options and self.__app_options.command_format
        terminal_format = self.__app_options and self.__app_options.terminal_format
        launch_application(app, command_format=command_format, terminal_format=terminal_format)

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

    def __apps_filter(self, app: Application, result: dict[str, int]) -> bool:
        return app.id in result

    def __apps_sorter(self, a: Application, b: Application, result: dict[str, int]) -> int:
        pa, pb = a.id and result.get(a.id), b.id and result.get(b.id)
        return (pa or 0) - (pb or 0)

    @gtk_template_callback
    def on_items_changed(self, *_):
        self.selection.set_selected(0)
        self.__move_selection(0)

    @gtk_template_callback
    def on_item_activate(self, _: Gtk.ListView, pos: int):
        item = self.selection.get_item(pos)
        if isinstance(item, Application):
            self.launch_application(item)
        self.on_search_stop()

    @gtk_template_callback
    def on_search_activate(self, *_):
        self.on_item_activate(self.app_grid, self.selection.get_selected())
        # pos = GLib.Variant.new_uint32(self.selection.get_selected())
        # self.app_grid.activate_action("list.activate-item", pos)

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

            if not self.search_bar.get_search_mode():
                self.search_bar.set_search_mode(True)
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


class AppLauncher(RevealerWindow):
    __gtype_name__ = "IgnisAppLauncher"

    def __init__(self):
        self.__view = AppLauncherView()

        super().__init__(
            namespace=WindowName.app_launcher.value,
            kb_mode="exclusive",
            layer="overlay",
            popup=True,
            visible=False,
            revealer=self.__view.revealer,
        )
        self.add_css_class("rounded")

        self.set_child(self.__view)

        self.__view.search_bar.set_key_capture_widget(self)
        self.__add_shortcut("<Control>f", self.__toggle_search_mode)
        self.__add_shortcut("<Control>bracketleft", self.__on_search_stop)
        self.__add_shortcut("<Control>n", self.__view.on_search_next)
        self.__add_shortcut("<Control>p", self.__view.on_search_previous)
        self.__add_shortcut("<Control>j", self.__view.on_search_next)
        self.__add_shortcut("<Control>k", self.__view.on_search_previous)

        self.__view.connect("search-stop", self.__on_search_stop)

    def set_property(self, property_name: str, value: Any):
        if property_name == "visible":
            overlay_window.update_window_visible(self.namespace, value)
        super().set_property(property_name, value)

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
