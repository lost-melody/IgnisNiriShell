from typing import Callable

from gi.repository import GObject
from ignis.options_manager import OptionsGroup
from ignis.utils import debounce


def connect_option(group: OptionsGroup, option: str, callback: Callable):
    binding = group.bind(option)
    source: GObject.Object = binding.target
    source_property: str = binding.target_properties[0]
    source.connect(f"notify::{source_property.replace('-', '_')}", debounce(500)(callback))


def bind_option(
    group: OptionsGroup,
    option: str,
    target: GObject.Object,
    target_property: str,
    flags: GObject.BindingFlags = GObject.BindingFlags.BIDIRECTIONAL,
    transform_to: Callable | None = None,
    transform_from: Callable | None = None,
):
    # target.property = transform_to(group.option)
    def on_option_changed(*_):
        value = getattr(group, option)
        if transform_to:
            value = transform_to(value)
        if target.get_property(target_property) != value:
            target.set_property(target_property, value)

    connect_option(group, option, on_option_changed)
    on_option_changed()

    if flags | GObject.BindingFlags.BIDIRECTIONAL == flags:
        # group.option = transform_from(target.property)
        def on_option_set(*_):
            value = target.get_property(target_property)
            if transform_from:
                value = transform_from(value)
            if getattr(group, option) != value:
                setattr(group, option, value)

        target.connect(f"notify::{target_property}", on_option_set)
