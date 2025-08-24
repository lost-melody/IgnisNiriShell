from gi.repository import Gtk
from ignis.widgets import Window

from ..constants import WindowName
from ..services import FcitxStateService
from ..useroptions import user_options
from ..utils import GProperty, connect_option, gtk_template, gtk_template_child


class FcitxKimPopup(Window):
    __gtype_name__ = "IgnisFcitxKimPopup"

    @gtk_template("kimpopup/view")
    class View(Gtk.Box):
        __gtype_name__ = "FcitxKimPopupView"

        @gtk_template("kimpopup/candidate")
        class Candidate(Gtk.FlowBoxChild):
            __gtype_name__ = "FcitxKimPopupCandidate"

            box: Gtk.Box = gtk_template_child()
            index_label: Gtk.Label = gtk_template_child()
            text_label: Gtk.Label = gtk_template_child()

            def __init__(self):
                super().__init__()

            def do_dispose(self):
                self.dispose_template(self.__class__)
                super().do_dispose()  # type: ignore

            @GProperty
            def label(self) -> str:
                return self.index_label.get_label()

            @label.setter
            def label(self, label: str):
                self.index_label.set_label(label)

            @GProperty
            def text(self) -> str:
                return self.text_label.get_label()

            @text.setter
            def text(self, label: str):
                self.text_label.set_label(label)

        preedit: Gtk.Label = gtk_template_child()
        candidates: Gtk.FlowBox = gtk_template_child()

        def __init__(self):
            super().__init__()

            self.__childs: list[FcitxKimPopup.View.Candidate] = []

            self.__options = user_options and user_options.fcitx_kimpanel
            if self.__options:
                connect_option(self.__options, "vertical_list", self.__on_vertical_list_changed)
                self.__on_vertical_list_changed()

            self.__fcitx = FcitxStateService.get_default()
            self.__fcitx.kimpanel.connect("notify::preedit", self.__on_preedit_changed)
            self.__fcitx.kimpanel.connect("notify::lookup", self.__on_lookup_changed)

        def __on_vertical_list_changed(self, *_):
            if not self.__options:
                return
            items_per_line = 100
            if self.__options.vertical_list:
                items_per_line = 1
            self.candidates.set_min_children_per_line(items_per_line)
            self.candidates.set_max_children_per_line(items_per_line)

        def __on_preedit_changed(self, *_):
            self.preedit.set_label(self.__fcitx.kimpanel.preedit)

        def __on_lookup_changed(self, *_):
            for c in self.__childs:
                self.candidates.remove(c)
                c.run_dispose()
            self.__childs.clear()

            lookup = self.__fcitx.kimpanel.lookup
            for idx, cand in enumerate(lookup.label):
                candidate = self.Candidate()
                candidate.label = cand
                candidate.text = lookup.text[idx]
                self.candidates.append(candidate)
                self.__childs.append(candidate)

                css_class = "kim-popup-candidate-selected"
                if idx == lookup.cursor:
                    candidate.box.add_css_class(css_class)
                else:
                    candidate.box.remove_css_class(css_class)

    def __init__(self):
        super().__init__(
            namespace=WindowName.kim_popup.value,
            anchor=[],
            exclusivity="ignore",
            layer="overlay",
            kb_mode="none",
            visible=False,
        )
        self.add_css_class("kim-popup-window")

        self.__view = self.View()
        self.set_child(self.__view)

        self.__options = user_options and user_options.fcitx_kimpanel

        self.__fcitx = FcitxStateService.get_default()
        self.__fcitx.kimpanel.connect("notify::show-preedit", self.__on_show_preedit)
        self.__fcitx.kimpanel.connect("notify::show-lookup", self.__on_show_lookup)

    def __on_show_preedit(self, *_):
        self.__view.preedit.set_visible(self.__fcitx.kimpanel.show_preedit)

    def __on_show_lookup(self, *_):
        self.set_visible(self.__options and self.__options.show_popup_window and self.__fcitx.kimpanel.show_lookup)
