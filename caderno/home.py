"""Tela inicial: pastas e cadernos em cartões, como a do Journal."""
from __future__ import annotations

import math
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import store  # noqa: E402
from .render import hex_rgb  # noqa: E402

CARD_W, COVER_H = 150, 118


def _lighten(rgb, k):
    return tuple(c + (1 - c) * k for c in rgb)


def _darken(rgb, k):
    return tuple(c * (1 - k) for c in rgb)


def _rounded(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def draw_cover(cr, w, h, entry: store.Entry):
    rgb = hex_rgb(entry.color)
    if entry.kind == "folder":
        # aba de trás, folhas brancas e frente da pasta
        cr.set_source_rgb(*_darken(rgb, 0.18))
        _rounded(cr, 0, 22, w, h - 22, 6)
        cr.fill()
        cr.move_to(4, 30)
        cr.line_to(8, 18)
        cr.line_to(w * 0.38, 18)
        cr.line_to(w * 0.45, 26)
        cr.close_path()
        cr.fill()
        cr.set_source_rgb(0.97, 0.97, 0.96)
        cr.rectangle(6, 30, w - 12, 10)
        cr.fill()
        cr.set_source_rgb(*rgb)
        _rounded(cr, 0, 36, w, h - 36, 6)
        cr.fill()
    else:
        cr.set_source_rgb(*rgb)
        _rounded(cr, 0, 0, w, h, 8)
        cr.fill()
        # ícone de caderno no canto
        cr.set_source_rgba(1, 1, 1, 0.85)
        cr.set_line_width(1.6)
        cr.rectangle(14.5, 12.5, 14, 17)
        cr.stroke()
        cr.move_to(18.5, 12.5)
        cr.line_to(18.5, 29.5)
        cr.stroke()
        cr.move_to(21, 18.5)
        cr.line_to(26, 18.5)
        cr.stroke()


_BG_CLASSES: dict[str, str] = {}
_BG_PROVIDER = None


def _bg_class(rgb) -> str:
    """Classe CSS com essa cor de fundo (um provedor só para todas as cores)."""
    global _BG_PROVIDER
    key = "%02x%02x%02x" % tuple(int(c * 255) for c in rgb)
    if key not in _BG_CLASSES:
        _BG_CLASSES[key] = f"bg-{key}"
        css = "".join(f".{cls} {{ background: #{k}; }}\n" for k, cls in _BG_CLASSES.items())
        from gi.repository import Gdk
        if _BG_PROVIDER is None:
            _BG_PROVIDER = Gtk.CssProvider()
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), _BG_PROVIDER,
                                                      Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        _BG_PROVIDER.load_from_string(css)
    return _BG_CLASSES[key]


class Card(Gtk.Box):
    def __init__(self, home: "HomePage", entry: store.Entry):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.entry = entry
        self.home = home
        self.add_css_class("caderno-card")
        self.set_size_request(CARD_W, -1)
        cover = Gtk.DrawingArea(content_width=CARD_W, content_height=COVER_H)
        cover.set_draw_func(lambda _a, cr, w, h: draw_cover(cr, w, h, entry))
        rgb = hex_rgb(entry.color)
        label_bg = _lighten(rgb, 0.85) if entry.kind == "journal" else (0.93, 0.89, 0.83)
        name = Gtk.Label(label=entry.name, wrap=True, justify=Gtk.Justification.CENTER,
                         max_width_chars=16, lines=2, ellipsize=3)
        name.add_css_class("card-label")
        label_box = Gtk.Box(height_request=48)
        label_box.add_css_class("card-label-box")
        label_box.append(name)
        name.set_hexpand(True)
        label_box.add_css_class(_bg_class(label_bg))

        over = Gtk.Overlay()
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        col.append(cover)
        col.append(label_box)
        over.set_child(col)
        menu = Gtk.MenuButton(icon_name="view-more-symbolic", halign=Gtk.Align.END, valign=Gtk.Align.START)
        menu.add_css_class("flat")
        menu.add_css_class("card-menu")
        menu.set_margin_top(28 if entry.kind == "folder" else 6)
        menu.set_create_popup_func(self._menu)
        over.add_overlay(menu)
        self.append(over)

        click = Gtk.GestureClick(button=1)
        click.connect("released", lambda g, n, x, y: self.home.open(self.entry))
        cover.add_controller(click)
        click2 = Gtk.GestureClick(button=1)
        click2.connect("released", lambda g, n, x, y: self.home.open(self.entry))
        label_box.add_controller(click2)
        self.set_cursor_from_name("pointer")

    def _menu(self, mb):
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for m in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{m}")(6)

        def item(label, cb, icon):
            b = Gtk.Button()
            row = Gtk.Box(spacing=10)
            row.append(Gtk.Image(icon_name=icon))
            row.append(Gtk.Label(label=label, xalign=0))
            b.set_child(row)
            b.add_css_class("flat")
            b.connect("clicked", lambda *_: (pop.popdown(), cb()))
            box.append(b)
        item("Renomear…", lambda: self.home.rename(self.entry), "document-edit-symbolic")
        item("Mover para…", lambda: self.home.move(self.entry), "folder-symbolic")
        colors = Gtk.Box(spacing=4, halign=Gtk.Align.CENTER)
        palette = store.FOLDER_COLORS if self.entry.kind == "folder" else store.JOURNAL_COLORS
        for c in palette:
            b = Gtk.Button()
            b.add_css_class("flat")
            b.add_css_class("swatch")
            da = Gtk.DrawingArea(content_width=20, content_height=20)
            da.set_draw_func(lambda _a, cr, w, h, c=c: (cr.set_source_rgb(*hex_rgb(c)),
                                                         cr.arc(w / 2, h / 2, w / 2 - 1, 0, 2 * math.pi),
                                                         cr.fill()))
            b.set_child(da)
            b.connect("clicked", lambda *_, c=c: (pop.popdown(), self.home.recolor(self.entry, c)))
            colors.append(b)
        box.append(colors)
        box.append(Gtk.Separator())
        item("Mover para a lixeira", lambda: self.home.delete(self.entry), "user-trash-symbolic")
        pop.set_child(box)
        mb.set_popover(pop)


class HomePage(Adw.NavigationPage):
    def __init__(self, app_window, root: Path, folder: Path | None = None):
        self.root = root
        self.folder = folder or root
        title = "Cadernos" if self.folder == root else self.folder.name
        super().__init__(title=title)
        self.win = app_window

        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.search = Gtk.SearchEntry(placeholder_text="Pesquisar", width_chars=30)
        self.search.connect("search-changed", lambda *_: self.reload())
        header.set_title_widget(self.search)
        view.add_top_bar(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for m in ("top", "start", "end"):
            getattr(content, f"set_margin_{m}")(28)
        heading = Gtk.Label(label=title, xalign=0, css_classes=["title-1"])
        content.append(heading)
        actions = Gtk.Box(spacing=8)
        new_j = Gtk.Button()
        nj = Gtk.Box(spacing=8)
        nj.append(Gtk.Image(icon_name="list-add-symbolic"))
        nj.append(Gtk.Label(label="Novo caderno"))
        new_j.set_child(nj)
        new_j.add_css_class("flat")
        new_j.connect("clicked", lambda *_: self.ask_name("Novo caderno", "Criar", "", self._create_journal))
        new_f = Gtk.Button(icon_name="folder-new-symbolic", tooltip_text="Nova pasta")
        new_f.add_css_class("flat")
        new_f.connect("clicked", lambda *_: self.ask_name("Nova pasta", "Criar", "", self._create_folder))
        actions.append(new_j)
        actions.append(new_f)
        content.append(actions)

        self.flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                column_spacing=20, row_spacing=20, max_children_per_line=12,
                                valign=Gtk.Align.START)
        self.empty = Gtk.Label(label="Nada aqui ainda — crie um caderno ou uma pasta.",
                               css_classes=["dim-label"], margin_top=40)
        content.append(self.flow)
        content.append(self.empty)
        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_child(content)
        view.set_content(scroller)
        self.set_child(view)
        self.connect("showing", lambda *_: self.reload())
        self.reload()

    def reload(self):
        while (child := self.flow.get_first_child()) is not None:
            self.flow.remove(child)
        text = self.search.get_text().strip()
        entries = store.search(self.folder, text) if text else store.list_dir(self.folder)
        for e in entries:
            self.flow.append(Card(self, e))
        self.empty.set_visible(not entries)
        self.empty.set_label("Nada encontrado." if text else
                             "Nada aqui ainda — crie um caderno ou uma pasta.")

    def open(self, entry: store.Entry):
        if entry.kind == "folder":
            self.win.nav.push(HomePage(self.win, self.root, entry.path))
        else:
            from .editor import Editor
            self.win.nav.push(Editor(entry.path))

    # ── ações ─────────────────────────────────────────────────────────────────
    def ask_name(self, heading, verb, initial, callback):
        dlg = Adw.AlertDialog(heading=heading)
        entry = Gtk.Entry(text=initial, activates_default=True)
        dlg.set_extra_child(entry)
        dlg.add_response("cancel", "Cancelar")
        dlg.add_response("ok", verb)
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("ok")
        dlg.set_close_response("cancel")

        def resp(_d, r):
            if r == "ok" and entry.get_text().strip():
                callback(entry.get_text())
        dlg.connect("response", resp)
        dlg.present(self.win)
        GLib.idle_add(lambda: entry.grab_focus() and False)

    def _create_journal(self, name):
        path = store.create_journal(self.folder, name)
        self.reload()
        self.open(store.Entry(path, "journal", ""))

    def _create_folder(self, name):
        store.create_folder(self.folder, name)
        self.reload()

    def rename(self, entry):
        self.ask_name("Renomear", "Renomear", entry.name,
                      lambda n: (store.rename(entry, n), self.reload()))

    def recolor(self, entry, color):
        store.set_color(entry, color)
        self.reload()

    def delete(self, entry):
        dlg = Adw.AlertDialog(heading=f"Mover “{entry.name}” para a lixeira?",
                              body="Dá para recuperar pela lixeira do sistema.")
        dlg.add_response("cancel", "Cancelar")
        dlg.add_response("del", "Mover para a lixeira")
        dlg.set_response_appearance("del", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_close_response("cancel")

        def resp(_d, r):
            if r == "del":
                try:
                    Gio.File.new_for_path(str(entry.path)).trash(None)
                except GLib.Error as e:
                    self.win.toast(f"Não consegui mover para a lixeira: {e.message}")
                self.reload()
        dlg.connect("response", resp)
        dlg.present(self.win)

    def move(self, entry):
        """Lista as pastas da biblioteca para escolher o destino."""
        folders = [self.root] + sorted(
            (p for p in self.root.rglob("*") if p.is_dir() and not p.name.endswith(store.SUFFIX)
             and not any(part.endswith(store.SUFFIX) or part.startswith(".")
                         for part in p.relative_to(self.root).parts)
             and p != entry.path and entry.path not in p.parents),
            key=lambda p: str(p).casefold())
        dlg = Adw.AlertDialog(heading=f"Mover “{entry.name}” para…")
        lst = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.SINGLE)
        for f in folders:
            label = "Cadernos (início)" if f == self.root else str(f.relative_to(self.root))
            row = Gtk.ListBoxRow(child=Gtk.Label(label=label, xalign=0, margin_start=10,
                                                 margin_end=10, margin_top=8, margin_bottom=8))
            row.folder = f
            lst.append(row)
        sc = Gtk.ScrolledWindow(min_content_height=min(320, 44 * len(folders)), child=lst)
        dlg.set_extra_child(sc)
        dlg.add_response("cancel", "Cancelar")
        dlg.add_response("ok", "Mover")
        dlg.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_close_response("cancel")

        def resp(_d, r):
            row = lst.get_selected_row()
            if r == "ok" and row is not None and row.folder != entry.path.parent:
                store.move(entry, row.folder)
                self.reload()
        dlg.connect("response", resp)
        dlg.present(self.win)
