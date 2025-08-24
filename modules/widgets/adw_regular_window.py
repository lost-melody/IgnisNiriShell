from gi.repository import Adw
from ignis.exceptions import WindowNotFoundError
from ignis.window_manager import WindowManager

from ..utils import GProperty

wm = WindowManager.get_default()


class AdwRegularWindow(Adw.Window):
    __gtype_name__ = "AdwRegularWindow"

    def __init__(self, namespace: str, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._namespace = namespace
        wm.add_window(namespace, self)

        self.connect("close-request", self.__class__.__on_close_request)

    @GProperty
    def namespace(self) -> str:
        return self._namespace

    def __remove(self):
        try:
            wm.remove_window(self.namespace)
        except WindowNotFoundError:
            pass

    def __on_close_request(self, *_):
        if not self.get_hide_on_close():
            self.__remove()

    def destroy(self):
        self.__remove()
        super().destroy()

    def do_unrealize(self):
        self.__remove()
        super().unrealize()
