"""As 6 ferramentas personalizáveis e a barra flutuante (como a do Journal)."""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from .render import hex_rgb  # noqa: E402
from .i18n import _  # noqa: E402

CONFIG = Path(GLib.get_user_config_dir()) / "caderno" / "ferramentas.json"

PEN_COLORS = ["#1a1a1a", "#1e56c8", "#7b3fc4", "#d32f2f", "#2e8b57", "#1597a5",
              "#e8762b", "#c2185b", "#795548", "#607d8b", "#f2c200", "#ffffff"]
HL_COLORS = ["#ffe94d", "#9ef06a", "#7fd8ff", "#ff9ecf", "#ffb35c", "#c9a6ff"]
PEN_WIDTHS = [1.2, 2.0, 3.0, 4.5, 7.0]
HL_WIDTHS = [10.0, 16.0, 22.0, 30.0]
ERASER_SIZES = [6.0, 12.0, 24.0]


@dataclass
class Tool:
    kind: str        # "pen" | "hl" | "eraser" | "ruler"
    color: str = "#1a1a1a"
    width: float = 2.0


DEFAULT_TOOLS = [
    Tool("pen", "#1e56c8", 2.0),
    Tool("pen", "#7b3fc4", 2.0),
    Tool("pen", "#1a1a1a", 2.0),
    Tool("hl", "#ffe94d", 16.0),
    Tool("eraser", "#f28b9b", 12.0),
    Tool("ruler", "#e9d39a", 0),
]


def load_tools() -> list[Tool]:
    try:
        data = json.loads(CONFIG.read_text())
        tools = [Tool(**t) for t in data["tools"]]
        if len(tools) == 6:
            return tools
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return [Tool(**asdict(t)) for t in DEFAULT_TOOLS]


def save_tools(tools):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({"tools": [asdict(t) for t in tools]}, indent=1))


# ── ícones desenhados ─────────────────────────────────────────────────────────

def _rounded(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def draw_tool_icon(cr, tool: Tool, w, h):
    cx = w / 2
    if tool.kind == "pen":
        r, g, b = hex_rgb(tool.color)
        # corpo
        cr.set_source_rgb(r * 0.85, g * 0.85, b * 0.85)
        cr.move_to(cx - 9, h)
        cr.line_to(cx - 9, h * 0.55)
        cr.line_to(cx + 9, h * 0.55)
        cr.line_to(cx + 9, h)
        cr.fill()
        # cone até a ponta
        cr.set_source_rgb(0.12, 0.12, 0.14)
        cr.move_to(cx - 9, h * 0.56)
        cr.line_to(cx - 2.5, h * 0.12)
        cr.line_to(cx + 2.5, h * 0.12)
        cr.line_to(cx + 9, h * 0.56)
        cr.fill()
        cr.set_source_rgb(r, g, b)
        cr.move_to(cx - 2.5, h * 0.12)
        cr.line_to(cx, h * 0.02)
        cr.line_to(cx + 2.5, h * 0.12)
        cr.fill()
        # brilho
        cr.set_source_rgba(1, 1, 1, 0.18)
        cr.rectangle(cx - 6, h * 0.6, 3, h * 0.4)
        cr.fill()
    elif tool.kind == "hl":
        r, g, b = hex_rgb(tool.color)
        cr.set_source_rgb(0.2, 0.2, 0.22)
        _rounded(cr, cx - 10, h * 0.42, 20, h * 0.58, 3)
        cr.fill()
        cr.set_source_rgb(r, g, b)
        cr.move_to(cx - 10, h * 0.44)
        cr.line_to(cx - 6, h * 0.14)
        cr.line_to(cx + 7, h * 0.06)
        cr.line_to(cx + 10, h * 0.44)
        cr.fill()
        cr.rectangle(cx - 10, h * 0.62, 20, h * 0.16)
        cr.fill()
    elif tool.kind == "eraser":
        cr.set_source_rgb(0.25, 0.25, 0.27)
        _rounded(cr, cx - 10, h * 0.45, 20, h * 0.55, 3)
        cr.fill()
        cr.set_source_rgb(0.95, 0.55, 0.62)
        _rounded(cr, cx - 10, h * 0.12, 20, h * 0.4, 5)
        cr.fill()
    elif tool.kind == "ruler":
        cr.set_source_rgb(0.91, 0.83, 0.6)
        _rounded(cr, cx - 11, h * 0.18, 22, h * 0.82, 2)
        cr.fill()
        cr.set_source_rgb(0.55, 0.45, 0.25)
        cr.set_line_width(1)
        y = h * 0.26
        i = 0
        while y < h:
            ln = 8 if i % 2 == 0 else 4
            cr.move_to(cx - 11, y + 0.5)
            cr.line_to(cx - 11 + ln, y + 0.5)
            y += 4.5
            i += 1
        cr.stroke()


def _swatch(color, size=26, selected=False):
    da = Gtk.DrawingArea(content_width=size, content_height=size)

    def draw(_a, cr, w, h):
        r, g, b = hex_rgb(color)
        cr.arc(w / 2, h / 2, w / 2 - 3, 0, 2 * math.pi)
        cr.set_source_rgb(r, g, b)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 0.9 if selected else 0.15)
        cr.set_line_width(2.5 if selected else 1)
        cr.stroke()
    da.set_draw_func(draw)
    return da


def _width_dot(width, kind, selected):
    da = Gtk.DrawingArea(content_width=34, content_height=34)

    def draw(_a, cr, w, h):
        if selected:
            cr.set_source_rgba(1, 1, 1, 0.15)
            _rounded(cr, 1, 1, w - 2, h - 2, 6)
            cr.fill()
        cr.set_source_rgb(0.92, 0.92, 0.92)
        d = width if kind != "eraser" else width * 1.2
        d = max(2.5, min(28, d * (1.6 if kind == "pen" else 0.9)))
        if kind == "hl":
            cr.rectangle(w / 2 - 3, h / 2 - d / 2, 6, d)
        else:
            cr.arc(w / 2, h / 2, d / 2, 0, 2 * math.pi)
        cr.fill()
    da.set_draw_func(draw)
    return da


class Toolbar(Gtk.Box):
    """Barra flutuante: 6 ferramentas + inserir, desfazer e refazer."""

    def __init__(self, on_change, on_insert_menu, on_undo, on_redo):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self.add_css_class("caderno-toolbar")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.END)
        self.set_margin_bottom(18)
        self.tools = load_tools()
        self.current = 0
        self.last_pen = 0
        self.on_change = on_change
        self.slot_buttons = []
        for i in range(len(self.tools)):
            btn = Gtk.Button()
            btn.add_css_class("flat")
            btn.add_css_class("tool-slot")
            icon = Gtk.DrawingArea(content_width=40, content_height=46)
            icon.set_draw_func(lambda _a, cr, w, h, i=i: draw_tool_icon(cr, self.tools[i], w, h))
            btn.set_child(icon)
            btn.set_tooltip_text(self._tooltip(i))
            btn.connect("clicked", self._clicked, i)
            self.append(btn)
            self.slot_buttons.append((btn, icon))
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.set_margin_start(6)
        sep.set_margin_end(6)
        self.append(sep)
        self.insert_btn = Gtk.MenuButton(icon_name="list-add-symbolic", tooltip_text=_("Inserir"))
        self.insert_btn.add_css_class("flat")
        self.insert_btn.add_css_class("bar-btn")
        self.insert_btn.set_create_popup_func(on_insert_menu)
        self.append(self.insert_btn)
        self.undo_btn = Gtk.Button(icon_name="edit-undo-symbolic", tooltip_text=_("Desfazer (Ctrl+Z)"))
        self.redo_btn = Gtk.Button(icon_name="edit-redo-symbolic", tooltip_text=_("Refazer (Ctrl+Shift+Z)"))
        for b, cb in ((self.undo_btn, on_undo), (self.redo_btn, on_redo)):
            b.add_css_class("flat")
            b.add_css_class("bar-btn")
            b.connect("clicked", lambda _b, cb=cb: cb())
            self.append(b)
        self._refresh()

    def _tooltip(self, i):
        t = self.tools[i]
        names = {"pen": "Caneta", "hl": "Marca-texto", "eraser": "Borracha", "ruler": "Régua (linha reta)"}
        return _("{tool} ({n}) — clique de novo para mudar cor e espessura", tool=_(names[t.kind]), n=i + 1)

    @property
    def tool(self) -> Tool:
        return self.tools[self.current]

    def pen_for_ruler(self) -> Tool:
        return self.tools[self.last_pen]

    def select(self, i):
        if 0 <= i < len(self.tools):
            self.current = i
            if self.tools[i].kind == "pen":
                self.last_pen = i
            self._refresh()
            self.on_change()

    def _clicked(self, _btn, i):
        if i == self.current and self.tools[i].kind != "ruler":
            self._open_settings(i)
        else:
            self.select(i)

    def _refresh(self):
        for i, (btn, icon) in enumerate(self.slot_buttons):
            if i == self.current:
                btn.add_css_class("selected")
            else:
                btn.remove_css_class("selected")
            icon.queue_draw()

    def set_history(self, can_undo, can_redo):
        self.undo_btn.set_sensitive(can_undo)
        self.redo_btn.set_sensitive(can_redo)

    # ── personalização ─────────────────────────────────────────────────────────
    def _open_settings(self, i):
        tool = self.tools[i]
        btn = self.slot_buttons[i][0]
        pop = Gtk.Popover()
        pop.set_parent(btn)
        pop.set_position(Gtk.PositionType.TOP)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for m in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{m}")(10)

        def changed():
            save_tools(self.tools)
            self._refresh()
            self.on_change()
            pop.popdown()

        if tool.kind in ("pen", "hl"):
            grid = Gtk.FlowBox(max_children_per_line=6, selection_mode=Gtk.SelectionMode.NONE,
                               column_spacing=2, row_spacing=2)
            for c in (PEN_COLORS if tool.kind == "pen" else HL_COLORS):
                b = Gtk.Button(child=_swatch(c, selected=c.lower() == tool.color.lower()))
                b.add_css_class("flat")
                b.add_css_class("swatch")
                b.connect("clicked", lambda _b, c=c: (setattr(tool, "color", c), changed()))
                grid.append(b)
            box.append(grid)
            custom = Gtk.Button(label=_("Outra cor…"))
            custom.add_css_class("flat")

            def pick(_b):
                pop.popdown()
                dlg = Gtk.ColorDialog(with_alpha=False)
                rgba = Gdk.RGBA()
                rgba.parse(tool.color)

                def done(d, res):
                    try:
                        c = d.choose_rgba_finish(res)
                    except GLib.Error:
                        return
                    tool.color = "#%02x%02x%02x" % (int(c.red * 255), int(c.green * 255), int(c.blue * 255))
                    changed()
                dlg.choose_rgba(self.get_root(), rgba, None, done)
            custom.connect("clicked", pick)
            box.append(custom)
        widths = {"pen": PEN_WIDTHS, "hl": HL_WIDTHS, "eraser": ERASER_SIZES}.get(tool.kind, [])
        if widths:
            row = Gtk.Box(spacing=4, halign=Gtk.Align.CENTER)
            for wv in widths:
                b = Gtk.Button(child=_width_dot(wv, tool.kind, abs(wv - tool.width) < 0.01))
                b.add_css_class("flat")
                b.connect("clicked", lambda _b, wv=wv: (setattr(tool, "width", wv), changed()))
                row.append(b)
            if tool.kind == "eraser":
                box.append(Gtk.Label(label=_("Tamanho da borracha"), css_classes=["dim-label"]))
            box.append(row)
        pop.set_child(box)
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        pop.popup()
