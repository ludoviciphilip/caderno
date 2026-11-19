"""Opções do app, num popover usado na tela inicial e no caderno."""
from __future__ import annotations

from gi.repository import Gtk

from . import i18n
from .i18n import _

PRESSURE_MODES = (("full", "Pela pressão"), ("soft", "Pressão suave"), ("off", "Uniforme"))


def _radio_group(box, title, options, current, on_pick):
    box.append(Gtk.Label(label=title, xalign=0, css_classes=["heading"], margin_top=2))
    group = None
    for code, name in options:
        check = Gtk.CheckButton(label=name, group=group)
        group = group or check
        check.set_active(current == code)
        check.connect("toggled", lambda c, code=code: c.get_active() and on_pick(code))
        box.append(check)


def build(on_language=None) -> Gtk.Box:
    """on_language(code): chamado depois de trocar o idioma (None = sem a seção de idioma)."""
    cfg = i18n.read_config()
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    for m in ("top", "bottom", "start", "end"):
        getattr(box, f"set_margin_{m}")(8)
    if on_language is not None:
        langs = [(c, n or _("Automático (sistema)")) for c, n in i18n.LANGUAGES.items()]
        _radio_group(box, _("Idioma"), langs, i18n.chosen(), on_language)
        box.append(Gtk.Separator(margin_top=4, margin_bottom=4))
    _radio_group(box, _("Traço da caneta"), [(c, _(n)) for c, n in PRESSURE_MODES],
                 cfg.get("pressure", "full"), lambda code: i18n.write_config(pressure=code))
    box.append(Gtk.Separator(margin_top=4, margin_bottom=4))
    row = Gtk.Box(spacing=12)
    row.append(Gtk.Label(label=_("Formas inteligentes"), xalign=0, hexpand=True))
    sw = Gtk.Switch(active=cfg.get("shapes", True), valign=Gtk.Align.CENTER)
    sw.connect("notify::active", lambda w, _p: i18n.write_config(shapes=w.get_active()))
    row.append(sw)
    box.append(row)
    return box
