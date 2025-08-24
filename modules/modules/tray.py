import asyncio
from typing import Coroutine

from gi.repository import Gio, GLib, Gtk
from ignis.dbus_menu import DBusMenu
from ignis.services.system_tray import SystemTrayItem, SystemTrayService
from ignis.widgets import Icon

from ..utils import SpecsBase, set_on_click, set_on_scroll


class Tray(Gtk.FlowBox):
    __gtype_name__ = "IgnisTray"

    class TrayItem(Gtk.FlowBoxChild, SpecsBase):
        __gtype_name__ = "IgnisTrayItem"

        def __init__(self, item: SystemTrayItem):
            self.__icon = Icon()
            self.__box = Gtk.Box()
            self.__box.append(self.__icon)
            super().__init__(css_classes=["px-1"], child=self.__box)
            SpecsBase.__init__(self)
            set_on_click(
                self,
                left=self.__class__.__on_clicked,
                middle=self.__class__.__on_middlet_clicked,
                right=self.__class__.__on_right_clicked,
            )
            set_on_scroll(self, self.__class__.__on_scroll)

            self.__item: SystemTrayItem = item
            self.signal(item, "notify::tooltip", self.__on_changed)
            self.signal(item, "notify::icon", self.__on_changed)
            self.__on_changed()

            self.__menu: DBusMenu | None = None
            if item.menu:
                self.__menu = item.menu.copy()
                self.__box.append(self.__menu)

        def do_dispose(self):
            self.clear_specs()
            super().do_dispose()  # type: ignore

        @property
        def tray_item(self) -> SystemTrayItem | None:
            return self.__item

        @classmethod
        async def try_async(cls, coro: Coroutine):
            """
            Wraps an async function and catches the ``GLib.Error``.
            """
            try:
                return await coro
            except GLib.Error as e:
                from loguru import logger

                logger.warning(f"GLib.Error: {e}")

        @classmethod
        def create_task(cls, coro: Coroutine):
            """
            Creates an async task and catches the ``GLib.Error``.
            """

            asyncio.create_task(cls.try_async(coro))

        def __on_changed(self, *_):
            if self.__item:
                self.__icon.image = self.__item.icon or ""
                self.set_tooltip_text(self.__item.tooltip)

        def __on_clicked(self):
            if self.__item:
                self.create_task(self.__item.activate_async())

        def __on_middlet_clicked(self):
            if self.__item:
                self.create_task(self.__item.secondary_activate_async())

        def __on_scroll(self, dx: float, dy: float):
            if not self.__item:
                return

            if dx != 0:
                self.__item.scroll(int(dx), orientation="horizontal")
            elif dy != 0:
                self.__item.scroll(int(dy), orientation="vertical")

        def __on_right_clicked(self):
            if self.__menu:
                self.__menu.popup()

    def __init__(self):
        self.__service = SystemTrayService.get_default()
        super().__init__()
        self.add_css_class("hover")
        self.add_css_class("rounded")

        self.__service.connect("added", self.__on_item_added)
        self.__list_store = Gio.ListStore()
        self.bind_model(self.__list_store, lambda item: item)
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_min_children_per_line(100)
        self.set_max_children_per_line(100)

    def __on_item_added(self, _, tray_item: SystemTrayItem):
        item = self.TrayItem(tray_item)
        self.__list_store.insert(0, item)
        tray_item.connect("removed", self.__on_item_removed)

    def __on_item_removed(self, tray_item: SystemTrayItem):
        found, pos = self.__list_store.find_with_equal_func(tray_item, lambda i, t: i.tray_item == t)
        if found:
            item = self.__list_store.get_item(pos)
            self.__list_store.remove(pos)
            if isinstance(item, self.TrayItem):
                item.run_dispose()
