"""Caderno: um caderno digital para escrever com a mesa digitalizadora."""
from __future__ import annotations

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from . import store  # noqa: E402
from .home import HomePage  # noqa: E402

APP_ID = "io.github.ludoviciphilip.Caderno"

CSS = """
window, .caderno-bg { background: #202020; }
.caderno-toolbar {
  background: #2c2c2c; border-radius: 14px; padding: 6px 10px;
  box-shadow: 0 4px 18px rgba(0,0,0,.45); border: 1px solid rgba(255,255,255,.06);
}
.tool-slot { padding: 2px 4px; border-radius: 10px; min-width: 0; min-height: 0; }
.tool-slot.selected { background: rgba(255,255,255,.10); }
.bar-btn { min-width: 40px; min-height: 40px; border-radius: 10px; }
.swatch { padding: 2px; min-width: 0; min-height: 0; border-radius: 99px; }
.page-frame { box-shadow: 0 2px 10px rgba(0,0,0,.5); border-radius: 3px; }
.page-number { color: rgba(0,0,0,.45); font-size: 11px; margin-top: 2px; }
.page-menu { color: rgba(0,0,0,.55); min-width: 24px; min-height: 24px; padding: 0; }
.add-page { border: 2px dashed rgba(255,255,255,.18); border-radius: 6px; background: transparent;
  color: rgba(255,255,255,.65); font-weight: 600; }
.add-page:hover { background: rgba(255,255,255,.05); color: #fff; }
.caderno-card { border-radius: 8px; }
.caderno-card:hover { background: rgba(255,255,255,.05); }
.card-label-box { border-radius: 0 0 8px 8px; }
.card-label { color: #222; font-weight: 600; font-size: 12.5px; margin: 6px; }
.card-menu { color: rgba(255,255,255,.9); min-width: 26px; min-height: 26px; padding: 0; }
"""


class Window(Adw.ApplicationWindow):
    def __init__(self, app, root: Path):
        super().__init__(application=app, title="Caderno", default_width=1280, default_height=880)
        self.toasts = Adw.ToastOverlay()
        self.nav = Adw.NavigationView()
        self.toasts.set_child(self.nav)
        self.set_content(self.toasts)
        self.nav.add(HomePage(self, root))
        self.connect("close-request", self._closing)

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=3))

    def _closing(self, *_args):
        page = self.nav.get_visible_page()
        if hasattr(page, "save_now"):
            page.save_now()
        return False


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.root = store.default_root()

    def do_startup(self):
        Adw.Application.do_startup(self)
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        css = Gtk.CssProvider()
        css.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        win = self.get_active_window() or Window(self, self.root)
        win.present()


def main():
    return App().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
