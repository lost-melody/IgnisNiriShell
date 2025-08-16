import weakref
from typing import Any, Callable

from gi.repository import GObject

from .misc import is_instance_method, unpack_instance_method


class SignalSpec:
    """
    Keeps a signal connection spec and disconnects on ``__del__``.
    """

    def __init__(self, gobject: GObject.Object, spec: int):
        self.__gobject = gobject
        self.__spec = spec

    def __del__(self):
        self.disconnect()

    def disconnect(self):
        if self.__gobject and self.__spec:
            self.__gobject.disconnect(self.__spec)
            self.__gobject = None
            self.__spec = None


class WeakCallback:
    """
    Creates a weak reference to ``obj`` and pass it to ``func`` on invoked.

    Args:
        obj: A class instance.
        func: A callback function, with ``obj`` and ``gobject`` as the first two arguments.
        swap: Whether to swap positions of ``obj`` and ``gobject``.
        default_callback: Invoked when ``obj`` is lost.

    Example:

    .. code-block:: python

        class MyBox(Gtk.Box):
            def __init__(self):
                super().__init__()
                WeakCallback(self, lambda self, stream, *_: self.do_something()).connect(stream, "notify::change")

            def do_something(self):
                pass
    """

    def __init__(self, obj: Any, func: Callable, swap: bool = False, default_callback: Callable | None = None):
        self.__obj = weakref.ref(obj)
        self.__func = func
        self.__swap = swap
        self.__default = default_callback
        self.__spec: int | None = None

    def __call__(self, gobject: GObject.Object, *args):
        # If ``obj`` lost, disconnect from signal on invoked.
        obj = self.__obj()
        if obj:
            if self.__swap:
                return self.__func(gobject, obj, *args)
            else:
                return self.__func(obj, gobject, *args)
        else:
            self.disconnect(gobject)
            if self.__default:
                return self.__default(gobject, *args)

    def connect(self, gobject: GObject.Object, signal: str, *args: Any):
        """
        Connects to the signal ``signal`` of object ``gobject``,
        keeping the ``spec`` for disconnecting.
        """
        if not self.__spec and self.__obj():
            self.__spec = gobject.connect(signal, self, *args)
        else:
            raise Exception("weak method already connected")

    def disconnect(self, gobject: GObject.Object):
        """
        Disconnects from the signal previously connected to ``gobject``.
        """
        if self.__spec:
            gobject.disconnect(self.__spec)
            self.__spec = None


class WeakMethod(WeakCallback):
    """
    Creates a weak reference to ``object.method``.

    Args:
        method: An instance method with a bound object.

    Example:

    .. code-block:: python

        class MyBox(Gtk.Box):
            def __init__(self):
                super().__init__()
                WeakMethod(self.on_change).connect(stream, "notify::change")

            def on_change(self, sender, *_):
                pass
    """

    def __init__(self, method: Callable):
        obj, func = unpack_instance_method(method)
        super().__init__(obj, func, True)


def connect_signal(gobject: GObject.Object, signal: str, callback: Callable, *args: Any):
    """
    Connects to a signal and returns a ``SignalSpec``.
    """
    spec = gobject.connect(signal, callback, *args)
    return SignalSpec(gobject, spec)


def weak_connect_callback(gobject: GObject.Object, signal: str, obj: Any, callback: Callable, *args: Any):
    """
    A wrapper to ``WeakCallback``.
    The first two arguments to ``func`` are signal sender ``gobject`` and object ``obj``.

    Example:

    .. code-block:: python

        weak_connect_callback(stream, "notify::change", self, lambda stream, self, *_: self.on_change())
    """
    weak = WeakCallback(obj, callback)
    weak.connect(gobject, signal, *args)
    return weak


def weak_connect_method(gobject: GObject.Object, signal: str, method: Callable, *args: Any):
    """
    A wrapper to ``WeakMethod``.
    The first argument to ``method`` is the signal sender ``gobject``.

    Example:

    .. code-block:: python

        weak_connect_method(stream, "notify::change", self.on_change)
    """
    weak = WeakMethod(method)
    weak.connect(gobject, signal, *args)
    return weak


def weak_connect(gobject: GObject.Object, signal: str, callback: Callable, *args):
    """
    Like ``weak_connect_method``, but fallbacks to trivial ``connect``.
    """
    if is_instance_method(callback):
        return weak_connect_method(gobject, signal, callback, *args)
    else:
        return gobject.connect(signal, callback, *args)
