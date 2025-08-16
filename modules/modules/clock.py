import datetime
import math

from gi.repository import Gtk
from ignis.utils import Poll
from ignis.window_manager import WindowManager

from ..constants import WindowName
from ..utils import gtk_template, gtk_template_child, set_on_click

wm = WindowManager.get_default()


@gtk_template("modules/clock")
class Clock(Gtk.Box):
    __gtype_name__ = "IgnisClock"

    label: Gtk.Label = gtk_template_child()
    popover: Gtk.Popover = gtk_template_child()
    calendar: Gtk.Calendar = gtk_template_child()

    def __init__(self):
        super().__init__()

        set_on_click(self, left=self.__on_clicked, right=self.__on_right_clicked)

        Poll(timeout=1000, callback=self.__on_change)

    def __on_change(self, poll: Poll):
        now = datetime.datetime.now()

        self.label.set_label(now.strftime("%H:%M"))
        self.label.set_tooltip_text(now.strftime("%Y-%m-%d"))

        poll.set_timeout(60 * 1000 - math.floor(now.second * 1000 + now.microsecond / 1000))

    def __on_clicked(self, *_):
        now = datetime.datetime.now()
        self.calendar.set_year(now.year)
        self.calendar.set_month(now.month - 1)
        self.calendar.set_day(now.day)
        self.popover.popup()

    def __on_right_clicked(self, *_):
        wm.toggle_window(WindowName.control_center.value)
