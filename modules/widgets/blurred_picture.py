from gi.repository import Gtk


class BlurredPicture(Gtk.Picture):
    __gtype_name__ = "IgnisBlurredPicture"

    def __init__(self, blur_radius: float = 0, **kvargs):
        self.__blur_radius = blur_radius
        super().__init__(**kvargs)

    def do_snapshot(self, snapshot: Gtk.Snapshot):
        snapshot.push_blur(self.blur_radius)
        Gtk.Picture.do_snapshot(self, snapshot)
        snapshot.pop()

    @property
    def blur_radius(self) -> float:
        return self.__blur_radius

    @blur_radius.setter
    def blur_radius(self, radius: float):
        self.__blur_radius = radius
