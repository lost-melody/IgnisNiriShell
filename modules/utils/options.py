import weakref
from typing import Any, Callable

from gi.repository import GObject
from ignis.options_manager import OptionsGroup
from ignis.utils import debounce

from .misc import is_instance_method, unpack_instance_method
from .signal import WeakCallback


def connect_option(group: OptionsGroup, option: str, callback: Callable):
    if is_instance_method(callback):
        obj, method = unpack_instance_method(callback)

        def cb(group: OptionsGroup, obj: Any, option_name: str):
            if option_name == option:
                return method(obj, group, option_name)

        WeakCallback(obj, debounce(500)(cb)).connect(group, "changed")
    else:

        def cb2(group: OptionsGroup, option_name: str):
            if option_name == option:
                callback(group, option_name)

        group.connect("changed", debounce(500)(cb2))


def bind_option(
    group: OptionsGroup,
    option: str,
    target: GObject.Object,
    target_property: str,
    flags: GObject.BindingFlags = GObject.BindingFlags.BIDIRECTIONAL,
    transform_to: Callable | None = None,
    transform_from: Callable | None = None,
):
    ref_group = weakref.ref(group)
    ref_target = weakref.ref(target)

    # target.property = transform_to(group.option)
    def on_option_changed(group: OptionsGroup, *_):
        target = ref_target()
        if not target:
            return

        value = getattr(group, option)
        if transform_to:
            value = transform_to(value)
        if target.get_property(target_property) != value:
            target.set_property(target_property, value)

    connect_option(group, option, on_option_changed)
    on_option_changed(group)

    if flags | GObject.BindingFlags.BIDIRECTIONAL == flags:
        # group.option = transform_from(target.property)
        def on_option_set(target: GObject.Object, *_):
            group = ref_group()
            if not group:
                return

            value = target.get_property(target_property)
            if transform_from:
                value = transform_from(value)
            if getattr(group, option) != value:
                setattr(group, option, value)

        target.connect(f"notify::{target_property}", on_option_set)
