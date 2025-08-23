from ignis.options import options
from ignis.widgets import Box, Icon
from ignis.window_manager import WindowManager

from ..constants import WindowName
from ..utils import connect_option, set_on_click

wm = WindowManager.get_default()


class DndIndicator(Box):
    __gtype_name__ = "IgnisDndIndicator"

    def __init__(self):
        self.__options = options and options.notifications
        super().__init__(
            css_classes=["hover", "px-1", "rounded", "warning"],
            tooltip_text="Do Not Disturb enabled",
            child=[Icon(image="notifications-disabled-symbolic")],
        )

        if self.__options:
            connect_option(self.__options, "dnd", self.__on_changed)
            set_on_click(self, left=self.__class__.__on_clicked, right=self.__class__.__on_right_clicked)
        self.__on_changed()

    def __on_changed(self, *_):
        self.set_visible(self.__options and self.__options.dnd or False)

    def __on_clicked(self, *_):
        if self.__options:
            self.__options.dnd = not self.__options.dnd

    def __on_right_clicked(self, *_):
        wm.toggle_window(WindowName.control_center.value)
