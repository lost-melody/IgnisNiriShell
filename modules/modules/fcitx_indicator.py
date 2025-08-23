import asyncio

from ignis.menu_model import IgnisMenuItem, IgnisMenuModel, IgnisMenuSeparator, ItemsType
from ignis.variable import Variable
from ignis.widgets import Box, Icon, Label, PopoverMenu

from ..services import FcitxStateService
from ..utils import set_on_click


class FcitxIndicator(Box):
    __gtype_name__ = "IgnisFcitxIndicator"

    def __init__(self):
        self.__text = Label(hexpand=True, visible=False)
        self.__icon = Icon(hexpand=True, visible=False)
        self.__menu = PopoverMenu()
        super().__init__(
            width_request=32,
            visible=False,
            css_classes=["hover", "px-1", "rounded"],
            child=[self.__text, self.__icon, self.__menu],
        )

        self.__fcitx = FcitxStateService.get_default()
        self.__fcitx.kimpanel.connect("notify::enabled", self.__on_fcitx_enabled)
        self.__fcitx.kimpanel.connect("notify::fcitx-im", self.__on_fcitx_state_changed)
        self.__fcitx.kimpanel.connect("exec-menu", self.__on_fcitx_exec_menu)

        set_on_click(self, left=self.__class__.__on_clicked, right=self.__class__.__on_right_clicked)

    def __on_fcitx_enabled(self, *_):
        self.set_visible(self.__fcitx.kimpanel.enabled)

    def __on_fcitx_state_changed(self, *_):
        prop = self.__fcitx.kimpanel.fcitx_im
        if prop.icon:
            self.__icon.set_from_icon_name(prop.icon)
        else:
            self.__text.set_label(prop.label)
        self.set_tooltip_text(prop.text)
        self.__text.set_visible(not prop.icon)
        self.__icon.set_visible(True if prop.icon else False)

    def __on_fcitx_exec_menu(self, _, properties: Variable):
        self.__menu.model = IgnisMenuModel(*self.__menu_items_from_properties(properties.value))
        self.__menu.popup()

    def __on_clicked(self, *_):
        asyncio.create_task(self.__fcitx.toggle_activate())

    def __on_right_clicked(self, *_):
        menu_items = self.__menu_items_from_properties(self.__fcitx.kimpanel.fcitx_properties)

        menu_items.append(IgnisMenuSeparator())
        menu_items.append(
            IgnisMenuItem(
                label="Configure", enabled=True, on_activate=lambda _: self.__fcitx.kimpanel.signal_configure()
            )
        )
        menu_items.append(
            IgnisMenuItem(
                label="Restart", enabled=True, on_activate=lambda _: self.__fcitx.kimpanel.signal_reload_config()
            )
        )
        menu_items.append(
            IgnisMenuItem(label="Exit", enabled=True, on_activate=lambda _: self.__fcitx.kimpanel.signal_exit())
        )

        self.__menu.model = IgnisMenuModel(*menu_items)
        self.__menu.popup()

    def __trigger_property(self, property: str):
        self.__fcitx.kimpanel.signal_trigger_property(property)

    def __menu_items_from_properties(self, properties: list[FcitxStateService.KIMPanel.Property]) -> ItemsType:
        menu_items: ItemsType = []

        for property in properties:
            label = ("＋" if "menu" in property.hint else "　") + property.label.split(" - ")[-1]
            menu_items.append(
                IgnisMenuItem(
                    label=label, enabled=True, on_activate=lambda _, key=property.key: self.__trigger_property(key)
                )
            )

        return menu_items
