import weakref
from typing import Any, Callable, TypeAlias

from gi.repository import GObject

from .misc import is_instance_method, unpack_instance_method


SpecType: TypeAlias = "SignalSpec | BindingSpec"


class SignalSpec:
    """
    Keeps a signal connection spec and disconnects on ``__del__``.
    """

    def __init__(self, gobject: GObject.Object, spec: int):
        self.__gobject = gobject
        self.__spec = spec

    def __del__(self):
        self.disconnect()

    @classmethod
    def new(cls, gobject: GObject.Object, signal: str, callback: Callable, *args):
        """
        Connects to a signal and returns a ``SignalSpec``.
        """
        spec = gobject.connect(signal, callback, *args)
        return cls(gobject, spec)

    def disconnect(self):
        if self.__gobject and self.__spec:
            self.__gobject.disconnect(self.__spec)
            self.__gobject = None
            self.__spec = None


class BindingSpec:
    def __init__(self, binding: GObject.Binding):
        self.__binding = binding

    def __del__(self):
        self.unbind()

    @classmethod
    def new(
        cls,
        source: GObject.Object,
        source_prop: str,
        target: GObject.Object,
        target_prop: str,
        flags: GObject.BindingFlags = GObject.BindingFlags.DEFAULT,
        transform_to: Callable | None = None,
        transform_from: Callable | None = None,
        user_data: Any = None,
    ):
        binding = source.bind_property(source_prop, target, target_prop, flags, transform_to, transform_from, user_data)
        return cls(binding)

    def unbind(self):
        if self.__binding:
            self.__binding.unbind()
            self.__binding = None


class SpecsBase:
    def __init__(self):
        self._specs: list[SpecType] = []

    def __del__(self):
        self.clear_specs()

    def clear_specs(self):
        self._specs.clear()

    def bind(
        self,
        source: GObject.Object,
        source_prop: str,
        target: GObject.Object,
        target_prop: str,
        flags: GObject.BindingFlags = GObject.BindingFlags.DEFAULT,
        transform_to: Callable | None = None,
        transform_from: Callable | None = None,
        user_data: Any = None,
    ):
        spec = BindingSpec.new(source, source_prop, target, target_prop, flags, transform_to, transform_from, user_data)
        self._specs.append(spec)
        return spec

    def signal(self, gobject: GObject.Object, signal: str, callback: Callable, *args):
        spec = SignalSpec.new(gobject, signal, callback, *args)
        self._specs.append(spec)
        return spec


class WeakCallback:
    """
    Creates a weak reference to ``obj`` and pass it to ``func`` on invoked.

    Args:
        obj: A class instance.
        func: A callback function, with ``gobject`` and ``obj`` as the first two arguments.
        swap: Whether to swap positions of ``gobject`` and ``obj``.
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
            if not self.__swap:
                return self.__func(gobject, obj, *args)
            else:
                return self.__func(obj, gobject, *args)
        else:
            self.disconnect(gobject)
            if self.__default:
                return self.__default(gobject, *args)

    @property
    def spec(self) -> int | None:
        return self.__spec

    def connect(self, gobject: GObject.Object, signal: str, *args: Any):
        """
        Connects to the signal ``signal`` of object ``gobject``,
        keeping the ``spec`` for disconnecting.
        """
        if not self.__spec and self.__obj():
            self.__spec = gobject.connect(signal, self, *args)
            return self
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


def weak_connect_callback(gobject: GObject.Object, signal: str, obj: Any, callback: Callable, *args: Any):
    """
    A wrapper to ``WeakCallback``.
    The first two arguments to ``func`` are signal sender ``gobject`` and object ``obj``.

    Example:

    .. code-block:: python

        weak_connect_callback(stream, "notify::change", self, lambda stream, self, *_: self.on_change())
    """
    return WeakCallback(obj, callback).connect(gobject, signal, *args)


def weak_connect_method(gobject: GObject.Object, signal: str, method: Callable, *args: Any):
    """
    A wrapper to ``WeakMethod``.
    The first argument to ``method`` is the signal sender ``gobject``.

    Example:

    .. code-block:: python

        weak_connect_method(stream, "notify::change", self.on_change)
    """
    return WeakMethod(method).connect(gobject, signal, *args)


def weak_connect(gobject: GObject.Object, signal: str, callback: Callable, *args):
    """
    Like ``weak_connect_method``, but fallbacks to trivial ``connect``.
    """
    if is_instance_method(callback):
        return weak_connect_method(gobject, signal, callback, *args)
    else:
        return gobject.connect(signal, callback, *args)
