from gi.repository import GLib, Pango


def escape_pango_markup(text: str) -> str:
    return GLib.markup_escape_text(text)


def verify_pango_markup(markup: str) -> bool:
    try:
        valid, _, _, _ = Pango.parse_markup(markup, -1, "\0")
        return valid
    except GLib.Error:
        return False
