"""O caderno aberto: folhas em sequência, caneta com pressão, imagens, desfazer."""
from __future__ import annotations

import math
import time
import uuid
from pathlib import Path

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Adw, Gdk, GdkPixbuf, Gio, GLib, Graphene, Gtk  # noqa: E402

from . import render  # noqa: E402
from .model import (PAGE_H, PAGE_W, PAPERS, ImageItem, Journal, Page, Stroke,  # noqa: E402
                    is_scribble, scribble_targets)
from .toolbar import Toolbar  # noqa: E402
from . import shapes  # noqa: E402
from .i18n import _, read_config  # noqa: E402

MOUSE_PRESSURE = 0.55
HANDLE = 14            # alça de redimensionar (unidades de página)
MAX_IMAGE_SIDE = 1800  # pixels guardados por imagem
SNAP_DEG = 4           # régua: gruda em múltiplos de 15° a menos de 4°
PAPER_NAMES = {"pautado": "Pautado", "quadriculado": "Quadriculado",
               "pontilhado": "Pontilhado", "liso": "Liso"}


class PageView(Gtk.DrawingArea):
    """Uma folha. Guarda uma imagem pronta do que já está desenhado e só
    desenha por cima o traço em andamento."""

    def __init__(self, editor: "Editor", page: Page):
        super().__init__()
        self.editor = editor
        self.page = page
        self.cache = None
        self.cache_key = None
        self.add_css_class("caderno-page")
        self.set_cursor(Gdk.Cursor.new_from_name("crosshair"))
        self.set_draw_func(self._draw)
        self.update_size()

        drag = Gtk.GestureDrag(button=0)
        drag.connect("drag-begin", self._begin)
        drag.connect("drag-update", self._update)
        drag.connect("drag-end", self._end)
        self.add_controller(drag)
        self.drag = drag

        drop = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop.set_gtypes([Gdk.FileList, Gdk.Texture])
        drop.connect("drop", self._drop)
        self.add_controller(drop)

    # ── tamanho e cache ────────────────────────────────────────────────────────
    def update_size(self):
        z = self.editor.zoom
        self.set_content_width(int(PAGE_W * z))
        self.set_content_height(int(PAGE_H * z))
        self.invalidate()

    def invalidate(self):
        self.cache = None
        self.queue_draw()

    def _ensure_cache(self, w, h):
        scale = self.get_scale_factor()
        key = (w, h, scale)
        if self.cache is not None and self.cache_key == key:
            return
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, int(w * scale), int(h * scale))
        surf.set_device_scale(scale, scale)
        cr = cairo.Context(surf)
        cr.set_antialias(cairo.ANTIALIAS_GOOD)
        cr.scale(w / PAGE_W, h / PAGE_H)
        render.render_page(cr, self.page, self.editor.images)
        self.cache, self.cache_key = surf, key

    def add_stroke_to_cache(self, s: Stroke):
        """Traço de caneta novo: pinta direto na imagem pronta (marca-texto refaz tudo,
        porque fica por baixo da tinta)."""
        if self.cache is None or s.kind == "hl":
            self.invalidate()
            return
        w, h, _scale = self.cache_key
        cr = cairo.Context(self.cache)
        cr.scale(w / PAGE_W, h / PAGE_H)
        render.draw_stroke(cr, s)
        self.queue_draw()

    def _draw(self, _area, cr, w, h):
        self._ensure_cache(w, h)
        cr.set_source_surface(self.cache, 0, 0)
        cr.paint()
        ed = self.editor
        cr.scale(w / PAGE_W, h / PAGE_H)
        live = ed.live
        if live and live["view"] is self:
            if live["mode"] == "draw" and live["stroke"].points:
                render.draw_stroke(cr, live["stroke"])
            elif live["mode"] == "line":
                self._draw_ruler(cr, live)
            elif live["mode"] == "erase":
                x, y = live["pos"]
                cr.arc(x, y, ed.toolbar.tool.width, 0, 2 * math.pi)
                cr.set_source_rgba(0.2, 0.2, 0.2, 0.35)
                cr.set_line_width(1.2)
                cr.stroke()
        sel = ed.selected
        if sel and sel[0] is self:
            it = sel[1]
            cr.set_source_rgba(0.25, 0.55, 1.0, 0.9)
            cr.set_line_width(2)
            cr.set_dash([6, 4])
            cr.rectangle(it.x, it.y, it.w, it.h)
            cr.stroke()
            cr.set_dash([])
            cr.rectangle(it.x + it.w - HANDLE, it.y + it.h - HANDLE, HANDLE, HANDLE)
            cr.fill()

    def _draw_ruler(self, cr, live):
        (x0, y0), (x1, y1) = live["a"], live["b"]
        ang = math.atan2(y1 - y0, x1 - x0)
        cr.save()
        cr.translate(x0, y0)
        cr.rotate(ang)
        length = math.hypot(x1 - x0, y1 - y0)
        cr.set_source_rgba(0.91, 0.83, 0.6, 0.55)
        cr.rectangle(-40, 3, length + 80, 46)
        cr.fill()
        cr.set_source_rgba(0.45, 0.36, 0.18, 0.7)
        cr.set_line_width(1)
        t = -40
        i = 0
        while t < length + 40:
            ln = 14 if i % 10 == 0 else (9 if i % 5 == 0 else 5)
            cr.move_to(t, 3)
            cr.line_to(t, 3 + ln)
            t += 7.56   # 2 mm
            i += 1
        cr.stroke()
        deg = (-math.degrees(ang)) % 180
        cr.move_to(length / 2 - 14, 40)
        cr.set_font_size(13)
        cr.show_text(f"{deg:.0f}°")
        cr.restore()
        render.draw_stroke(cr, live["stroke"])

    # ── entrada ────────────────────────────────────────────────────────────────
    def _to_page(self, x, y):
        z = self.editor.zoom
        return x / z, y / z

    def _begin(self, gesture, x, y):
        ed = self.editor
        ev = gesture.get_current_event()
        tool_dev = ev.get_device_tool() if ev else None
        is_pen = tool_dev is not None
        button = gesture.get_current_button()
        px, py = self._to_page(x, y)
        state = ev.get_modifier_state() if ev else 0
        if is_pen and (button in (2, 3) or state & (Gdk.ModifierType.BUTTON2_MASK |
                                                    Gdk.ModifierType.BUTTON3_MASK)):
            gesture.set_state(Gtk.EventSequenceState.DENIED)   # botões da caneta: o Editor cuida
            return
        eraser_end = is_pen and tool_dev.get_tool_type() == Gdk.DeviceToolType.ERASER

        # mouse em cima de uma imagem: seleciona / move / redimensiona
        if not is_pen and button == 1:
            hit = next((it for it in reversed(self.page.images) if it.contains(px, py)), None)
            if hit is not None:
                ed.select_image(self, hit)
                resize = px > hit.x + hit.w - HANDLE * 1.5 and py > hit.y + hit.h - HANDLE * 1.5
                ed.live = {"view": self, "mode": "resize" if resize else "move", "item": hit,
                           "start": (hit.x, hit.y, hit.w, hit.h), "p0": (px, py)}
                return
        ed.select_image(None, None)

        tool = ed.toolbar.tool
        if eraser_end or (not is_pen and button == 3) or tool.kind == "eraser":
            ed.live = {"view": self, "mode": "erase", "pos": (px, py), "removed": []}
            self._erase_at(px, py)
            return
        if not is_pen and button != 1:
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            return
        p = self._pressure(ev)
        if tool.kind == "ruler":
            pen = ed.toolbar.pen_for_ruler()
            s = Stroke("pen", pen.color, pen.width, [[px, py, 0.7], [px, py, 0.7]])
            ed.live = {"view": self, "mode": "line", "a": (px, py), "b": (px, py), "stroke": s}
        else:
            kind = "hl" if tool.kind == "hl" else "pen"
            s = Stroke(kind, tool.color, tool.width, [[px, py, p]])
            ed.live = {"view": self, "mode": "draw", "stroke": s, "smooth": [px, py, p],
                       "origin": (x, y), "pen": is_pen, "last_widget": (x, y),
                       "still": (px, py, time.monotonic()), "snapped": None}
            if read_config().get("shapes", True):
                live = ed.live
                GLib.timeout_add(80, self._hold_tick, live)
        self.queue_draw()

    @staticmethod
    def _pressure(ev):
        if ev is None:
            return MOUSE_PRESSURE
        ok, p = ev.get_axis(Gdk.AxisUse.PRESSURE)
        if ok and ev.get_device_tool() is not None:
            return max(0.05, p)
        return MOUSE_PRESSURE

    def _samples(self, gesture, dx, dy):
        """Pontos desde o último evento, incluindo o histórico que o GTK junta
        num quadro só (sem ele, escrita rápida sai em linhas retas)."""
        x0, y0 = self.editor.live["origin"]
        x, y = x0 + dx, y0 + dy
        ev = gesture.get_current_event()
        out = []
        if ev is not None and ev.get_event_type() == Gdk.EventType.MOTION_NOTIFY:
            ok, ex, ey = ev.get_position()
            if ok:
                ox, oy = x - ex, y - ey
                need = Gdk.AxisFlags.X | Gdk.AxisFlags.Y
                has_p = bool(Gdk.AxisFlags.PRESSURE)
                for tc in ev.get_history() or []:
                    # Na mesa, o histórico às vezes vem sem X/Y (zerados): esses pontos
                    # puxavam uma linha do canto superior esquerdo.
                    if (tc.flags & need) != need:
                        continue
                    a = tc.axes
                    hx, hy = a[int(Gdk.AxisUse.X)] + ox, a[int(Gdk.AxisUse.Y)] + oy
                    hp = MOUSE_PRESSURE
                    if self.editor.live["pen"] and has_p and tc.flags & Gdk.AxisFlags.PRESSURE:
                        hp = a[int(Gdk.AxisUse.PRESSURE)] or MOUSE_PRESSURE
                    out.append((hx, hy, hp))
        out.append((x, y, self._pressure(ev)))
        # descarta pontos do histórico fora do caminho entre o ponto anterior e o atual
        prev = self.editor.live.get("last_widget", out[0][:2])
        span = math.hypot(x - prev[0], y - prev[1]) + 40
        out = [q for q in out if math.hypot(q[0] - prev[0], q[1] - prev[1]) <= span
               and math.hypot(q[0] - x, q[1] - y) <= span]
        self.editor.live["last_widget"] = (x, y)
        return out

    def _update(self, gesture, dx, dy):
        ed = self.editor
        live = ed.live
        if not live or live["view"] is not self:
            return
        mode = live["mode"]
        if mode in ("move", "resize"):
            ok, sx, sy = gesture.get_start_point()
            px, py = self._to_page(sx + dx, sy + dy)
            it = live["item"]
            x0, y0, w0, h0 = live["start"]
            ddx, ddy = px - live["p0"][0], py - live["p0"][1]
            if mode == "move":
                it.x = max(-w0 + 20, min(PAGE_W - 20, x0 + ddx))
                it.y = max(-h0 + 20, min(PAGE_H - 20, y0 + ddy))
            else:
                k = max(0.05, (w0 + ddx) / w0)
                it.w, it.h = w0 * k, h0 * k
            self.invalidate()
            return
        ok, sx, sy = gesture.get_start_point()
        if mode == "erase":
            px, py = self._to_page(sx + dx, sy + dy)
            live["pos"] = (px, py)
            self._erase_at(px, py)
            self.queue_draw()
            return
        if mode == "line":
            px, py = self._to_page(sx + dx, sy + dy)
            ax, ay = live["a"]
            ang = math.degrees(math.atan2(py - ay, px - ax))
            snap = round(ang / 15) * 15
            if abs(ang - snap) < SNAP_DEG:
                r = math.hypot(px - ax, py - ay)
                px, py = ax + r * math.cos(math.radians(snap)), ay + r * math.sin(math.radians(snap))
            live["b"] = (px, py)
            live["stroke"].points = [[ax, ay, 0.7], [px, py, 0.7]]
            self.queue_draw()
            return
        # desenho livre, com suavização leve (média móvel exponencial)
        s = live["stroke"]
        if live.get("snapped"):
            return            # já virou forma: o resto do movimento até soltar é ignorado
        sm = live["smooth"]
        for wx, wy, p in self._samples(gesture, dx, dy):
            px, py = self._to_page(wx, wy)
            a = 0.5
            sm[0] += (px - sm[0]) * a
            sm[1] += (py - sm[1]) * a
            sm[2] += (p - sm[2]) * 0.35
            last = s.points[-1]
            if math.hypot(sm[0] - last[0], sm[1] - last[1]) >= 0.5:
                s.points.append([sm[0], sm[1], sm[2]])
                s._bbox = None
        sx_, sy_, _t = live["still"]
        if math.hypot(sm[0] - sx_, sm[1] - sy_) > shapes.STILL_RADIUS:
            live["still"] = (sm[0], sm[1], time.monotonic())
        self.queue_draw()

    def _hold_tick(self, live):
        """Caneta parada no fim do traço por um instante: troca o traço pela forma."""
        if self.editor.live is not live or live.get("snapped"):
            return False
        if time.monotonic() - live["still"][2] < shapes.HOLD_SECONDS:
            return True
        s = live["stroke"]
        found = shapes.recognize(s.points)
        if not found:
            return False         # não é forma: segue como traço normal
        _kind, pts = found
        pressure = sum(p[2] for p in s.points) / len(s.points)
        s.points = [[x, y, pressure] for x, y in pts]
        s._bbox = None
        live["snapped"] = _kind
        self.queue_draw()
        return False

    def _end(self, gesture, dx, dy):
        ed = self.editor
        live = ed.live
        ed.live = None
        if not live or live["view"] is not self:
            return
        mode = live["mode"]
        if mode in ("move", "resize"):
            it = live["item"]
            before, after = live["start"], (it.x, it.y, it.w, it.h)
            if before != after:
                def setr(r, it=it):
                    it.x, it.y, it.w, it.h = r
                    self.invalidate()
                ed.push(lambda: setr(before), lambda: setr(after))
            return
        if mode == "erase":
            removed = live["removed"]
            if removed:
                page = self.page

                def undo():
                    for idx, st in sorted(removed, key=lambda t: t[0]):
                        page.strokes.insert(idx, st)
                    self.invalidate()

                def redo():
                    for _idx, st in removed:
                        if st in page.strokes:
                            page.strokes.remove(st)
                    self.invalidate()
                ed.push(undo, redo, done=True)
            self.queue_draw()
            return
        s = live["stroke"]
        if mode == "draw" and not live.get("snapped"):
            ok, sx, sy = gesture.get_start_point()
            px, py = self._to_page(sx + dx, sy + dy)
            if math.hypot(px - s.points[-1][0], py - s.points[-1][1]) > 0.5:
                s.points.append([px, py, live["smooth"][2]])
        if mode == "line" and math.hypot(*(a - b for a, b in zip(live["a"], live["b"]))) < 2:
            self.queue_draw()
            return
        s._bbox = None
        page = self.page
        if mode == "draw" and not live.get("snapped") and is_scribble(s):
            targets = scribble_targets(page, s)
            if targets:   # riscou por cima de algo já escrito: apaga isso e some com o rabisco
                self._scratch_out(targets)
                return
        page.strokes.append(s)
        self.add_stroke_to_cache(s)

        def undo():
            if s in page.strokes:
                page.strokes.remove(s)
            self.invalidate()

        def redo():
            page.strokes.append(s)
            self.add_stroke_to_cache(s)
        ed.push(undo, redo, done=True)
        ed.ensure_blank_last_page(page)

    def _scratch_out(self, targets):
        page = self.page
        for _i, st in targets:
            page.strokes.remove(st)
        self.invalidate()

        def undo():
            for idx, st in sorted(targets, key=lambda t: t[0]):
                page.strokes.insert(idx, st)
            self.invalidate()

        def redo():
            for _idx, st in targets:
                if st in page.strokes:
                    page.strokes.remove(st)
            self.invalidate()
        self.editor.push(undo, redo, done=True)

    def _erase_at(self, x, y):
        live = self.editor.live
        r = self.editor.toolbar.tool.width if self.editor.toolbar.tool.kind == "eraser" else 12.0
        hit = False
        for i in range(len(self.page.strokes) - 1, -1, -1):
            st = self.page.strokes[i]
            if st.hit(x, y, r):
                live["removed"].append((i, st))
                del self.page.strokes[i]
                hit = True
        if hit:
            self.invalidate()
            self.editor.mark_dirty()

    def _drop(self, _target, value, x, y):
        px, py = self._to_page(x, y)
        if isinstance(value, Gdk.Texture):
            self.editor.insert_image(value, self, (px, py))
            return True
        files = value.get_files() if hasattr(value, "get_files") else []
        ok = False
        for i, f in enumerate(files):
            if f.get_path():
                ok = self.editor.insert_image(Path(f.get_path()), self, (px + 20 * i, py + 20 * i)) or ok
        return ok


class Editor(Adw.NavigationPage):
    def __init__(self, journal_path: Path):
        self.journal = Journal.load(journal_path)
        super().__init__(title=self.journal.name, tag="editor")
        self.images = render.ImageCache(self.journal.images_dir)
        self.zoom = 1.0
        self.live = None
        self.selected = None
        self.undo_stack, self.redo_stack = [], []
        self.dirty = False
        self.save_source = 0
        self.views: list[PageView] = []

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text=_("Caderno"))
        menu_btn.set_create_popup_func(self._journal_menu)
        header.pack_end(menu_btn)
        zoom_out = Gtk.Button(icon_name="zoom-out-symbolic", tooltip_text=_("Diminuir (Ctrl+-)"))
        zoom_in = Gtk.Button(icon_name="zoom-in-symbolic", tooltip_text=_("Aumentar (Ctrl+=)"))
        zoom_out.connect("clicked", lambda *_: self.set_zoom(self.zoom / 1.15))
        zoom_in.connect("clicked", lambda *_: self.set_zoom(self.zoom * 1.15))
        header.pack_end(zoom_in)
        header.pack_end(zoom_out)
        toolbar_view.add_top_bar(header)

        self.pages_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
        self.pages_box.set_halign(Gtk.Align.CENTER)
        self.pages_box.set_margin_top(20)
        self.pages_box.set_margin_bottom(120)
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_child(self.pages_box)
        # Sem isso, o primeiro toque de caneta numa folha dava foco a ela e o viewport
        # rolava para "mostrar" o widget focado no meio do traço (saía uma reta).
        viewport = self.scroller.get_child()
        if isinstance(viewport, Gtk.Viewport):
            viewport.set_scroll_to_focus(False)
        self.scroller.set_kinetic_scrolling(False)
        zoom_scroll = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        zoom_scroll.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        zoom_scroll.connect("scroll", self._on_scroll)
        self.scroller.add_controller(zoom_scroll)

        self.toolbar = Toolbar(self._tool_changed, self._insert_menu, self.undo, self.redo)
        overlay = Gtk.Overlay()
        overlay.set_child(self.scroller)
        overlay.add_overlay(self.toolbar)
        toolbar_view.set_content(overlay)
        self.set_child(toolbar_view)

        self.add_page_btn = Gtk.Button(halign=Gtk.Align.CENTER)
        lab = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
        lab.append(Gtk.Image(icon_name="list-add-symbolic"))
        lab.append(Gtk.Label(label=_("Nova folha")))
        self.add_page_btn.set_child(lab)
        self.add_page_btn.add_css_class("add-page")
        self.add_page_btn.connect("clicked", lambda *_: self._add_page_at_end())
        self.add_page_btn.set_size_request(int(PAGE_W * self.zoom), 56)
        self.pages_box.append(self.add_page_btn)

        for page in self.journal.pages:
            self._add_view(page)
        self._renumber()
        self._update_history()
        self._shortcuts()
        self._pen_buttons()
        self._pad()
        self.connect("hidden", lambda *_: self.save_now())
        self.connect("realize", lambda *_: GLib.idle_add(self._fit_zoom))

    # ── páginas ───────────────────────────────────────────────────────────────
    def _add_view(self, page: Page, index=None):
        view = PageView(self, page)
        frame = Gtk.Overlay()
        frame.set_child(view)
        frame.add_css_class("page-frame")
        head = Gtk.Box(spacing=2, halign=Gtk.Align.END, valign=Gtk.Align.START)
        head.set_margin_top(6)
        head.set_margin_end(6)
        num = Gtk.Label(css_classes=["page-number"])
        menu = Gtk.MenuButton(icon_name="view-more-symbolic", css_classes=["flat", "page-menu"])
        menu.set_create_popup_func(lambda mb, v=view: self._page_menu(mb, v))
        head.append(num)
        head.append(menu)
        frame.add_overlay(head)
        frame.set_clip_overlay(head, False)
        view.frame, view.number = frame, num
        if index is None or index >= len(self.views):
            last = self.views[-1].frame if self.views else None
            self.pages_box.insert_child_after(frame, last)
            self.views.append(view)
        else:
            sibling = self.views[index - 1].frame if index > 0 else None
            self.pages_box.insert_child_after(frame, sibling)
            self.views.insert(index, view)
        return view

    def _renumber(self):
        for i, v in enumerate(self.views):
            v.number.set_label(str(i + 1))

    def insert_page(self, index, page=None, record=True):
        page = page or self.journal.new_page()
        self.journal.pages.insert(index, page)
        self._add_view(page, index)
        self._renumber()
        self.mark_dirty()
        if record:
            self.push(lambda: self.delete_page(page, record=False),
                      lambda: self.insert_page(index, page, record=False), done=True)
        return page

    def delete_page(self, page, record=True):
        if page not in self.journal.pages:
            return
        index = self.journal.pages.index(page)
        if len(self.journal.pages) == 1:
            # a única folha: em vez de sumir com ela, apaga o conteúdo
            strokes, images = list(page.strokes), list(page.images)
            view = self.views[0]

            def clear():
                page.strokes.clear()
                page.images.clear()
                view.invalidate()

            def restore():
                page.strokes[:] = strokes
                page.images[:] = images
                view.invalidate()
            clear()
            if record:
                self.push(restore, clear, done=True)
            return
        self.journal.pages.pop(index)
        view = self.views.pop(index)
        self.pages_box.remove(view.frame)
        if self.selected and self.selected[0] is view:
            self.selected = None
        self._renumber()
        self.mark_dirty()
        if record:
            self.push(lambda: self.insert_page(index, page, record=False),
                      lambda: self.delete_page(page, record=False), done=True)

    def _add_page_at_end(self):
        self.insert_page(len(self.journal.pages))
        GLib.idle_add(self._scroll_to_end)

    def _scroll_to_end(self):
        vadj = self.scroller.get_vadjustment()
        vadj.set_value(vadj.get_upper() - vadj.get_page_size())
        return False

    # ── botões da caneta e da mesa ────────────────────────────────────────────
    PEN_SCROLL_BUTTON = 2   # botão de baixo da caneta: segurar e mover = rolar
    PEN_UNDO_BUTTON = 3     # botão de cima: desfazer
    PAD_ZOOM_OUT = 2        # botões da mesa, da esquerda (0) para a direita (3)
    PAD_ZOOM_IN = 3

    def _pen_buttons(self):
        """Na área toda (folhas e fundo), antes das folhas: os botões laterais da caneta."""
        g = Gtk.GestureDrag(button=0)
        g.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        g.connect("drag-begin", self._pen_btn_begin)
        g.connect("drag-update", self._pen_btn_update)
        g.connect("drag-end", lambda *_: setattr(self, "_pan", None))
        self.scroller.add_controller(g)
        self._pan = None

    def _pen_btn_begin(self, g, x, y):
        ev = g.get_current_event()
        if ev is None or ev.get_device_tool() is None:
            g.set_state(Gtk.EventSequenceState.DENIED)
            return
        button = g.get_current_button()
        state = ev.get_modifier_state()
        scroll = button == self.PEN_SCROLL_BUTTON or (
            state & getattr(Gdk.ModifierType, f"BUTTON{self.PEN_SCROLL_BUTTON}_MASK"))
        undo = button == self.PEN_UNDO_BUTTON or (
            state & getattr(Gdk.ModifierType, f"BUTTON{self.PEN_UNDO_BUTTON}_MASK"))
        if scroll:
            g.set_state(Gtk.EventSequenceState.CLAIMED)
            self._pan = (y, x, self.scroller.get_vadjustment().get_value(),
                         self.scroller.get_hadjustment().get_value())
        elif undo:
            g.set_state(Gtk.EventSequenceState.CLAIMED)
            self.undo()
        else:
            g.set_state(Gtk.EventSequenceState.DENIED)

    def _pen_btn_update(self, g, dx, dy):
        if self._pan is None:
            return
        y0, x0, v0, h0 = self._pan
        # coordenadas do próprio ScrolledWindow: não mudam quando o conteúdo rola
        self.scroller.get_vadjustment().set_value(v0 - dy)
        self.scroller.get_hadjustment().set_value(h0 - dx)

    def _pad(self):
        """Botões da mesa (ExpressKeys): os dois da direita dão zoom."""
        group = Gio.SimpleActionGroup()
        for name, cb in (("zoom-in", lambda *_: self.set_zoom(self.zoom * 1.15)),
                         ("zoom-out", lambda *_: self.set_zoom(self.zoom / 1.15))):
            a = Gio.SimpleAction.new(name, None)
            a.connect("activate", cb)
            group.add_action(a)
        self.insert_action_group("pad", group)
        self._pad_group = group
        self.connect("map", self._attach_pad)

    def _attach_pad(self, *_args):
        if getattr(self, "_pad_ctrl", None) is not None:
            return
        win = self.get_root()
        if win is None:
            return
        ctrl = Gtk.PadController.new(self._pad_group, None)
        entries = []
        for idx, act, label in ((self.PAD_ZOOM_OUT, "zoom-out", _("Diminuir zoom")),
                                (self.PAD_ZOOM_IN, "zoom-in", _("Aumentar zoom"))):
            e = Gtk.PadActionEntry()
            e.type = Gtk.PadActionType.BUTTON
            e.index = idx
            e.mode = -1
            e.label = label
            e.action_name = act
            entries.append(e)
        for e in entries:
            ctrl.set_action(e.type, e.index, e.mode, e.label, e.action_name)
        win.add_controller(ctrl)
        self._pad_ctrl = ctrl
        self.connect("unmap", self._detach_pad)

    def _detach_pad(self, *_args):
        ctrl = getattr(self, "_pad_ctrl", None)
        if ctrl is not None and ctrl.get_widget() is not None:
            ctrl.get_widget().remove_controller(ctrl)
        self._pad_ctrl = None

    def ensure_blank_last_page(self, page):
        """Escreveu na última folha: abre uma folha nova no fim, como um caderno."""
        if page is self.journal.pages[-1]:
            new = self.journal.new_page()
            new.paper = page.paper
            self.journal.pages.append(new)
            self._add_view(new)
            self._renumber()

    def current_view(self) -> PageView:
        vadj = self.scroller.get_vadjustment()
        mid = vadj.get_value() + vadj.get_page_size() / 2
        best, dist = self.views[0], float("inf")
        for v in self.views:
            ok, b = v.frame.compute_bounds(self.pages_box)
            if not ok:
                continue
            c = b.get_y() + b.get_height() / 2
            if b.get_y() <= mid <= b.get_y() + b.get_height():
                return v
            if abs(c - mid) < dist:
                best, dist = v, abs(c - mid)
        return best

    # ── zoom ──────────────────────────────────────────────────────────────────
    def _fit_zoom(self):
        w = self.scroller.get_width() or 1100
        self.set_zoom(min(1.4, max(0.5, (w - 80) / PAGE_W)) if w < 1100 else 1.0, keep=False)
        return False

    def set_zoom(self, z, keep=True):
        z = max(0.4, min(3.0, z))
        if abs(z - self.zoom) < 0.001 and keep:
            return
        vadj = self.scroller.get_vadjustment()
        frac = vadj.get_value() / max(1, vadj.get_upper())
        self.zoom = z
        for v in self.views:
            v.update_size()
        self.add_page_btn.set_size_request(int(PAGE_W * z), 56)
        if keep:
            GLib.idle_add(lambda: vadj.set_value(frac * vadj.get_upper()) and False)

    def _on_scroll(self, ctrl, dx, dy):
        state = ctrl.get_current_event_state()
        if state & Gdk.ModifierType.CONTROL_MASK:
            self.set_zoom(self.zoom * (0.9 if dy > 0 else 1.1))
            return True
        return False

    # ── desfazer ──────────────────────────────────────────────────────────────
    def push(self, undo, redo, done=True):
        self.undo_stack.append((undo, redo))
        del self.undo_stack[:-300]
        self.redo_stack.clear()
        self.mark_dirty()
        self._update_history()

    def undo(self):
        if self.undo_stack:
            u, r = self.undo_stack.pop()
            u()
            self.redo_stack.append((u, r))
            self.mark_dirty()
            self._update_history()

    def redo(self):
        if self.redo_stack:
            u, r = self.redo_stack.pop()
            r()
            self.undo_stack.append((u, r))
            self.mark_dirty()
            self._update_history()

    def _update_history(self):
        self.toolbar.set_history(bool(self.undo_stack), bool(self.redo_stack))

    # ── salvar ────────────────────────────────────────────────────────────────
    def mark_dirty(self):
        self.dirty = True
        if self.save_source:
            GLib.source_remove(self.save_source)
        self.save_source = GLib.timeout_add(1200, self._autosave)

    def _autosave(self):
        self.save_source = 0
        self.save_now()
        return False

    def save_now(self):
        if self.dirty:
            try:
                self.journal.save()
                self.dirty = False
            except OSError as e:
                print("caderno: falha ao salvar:", e)

    # ── imagens ───────────────────────────────────────────────────────────────
    def select_image(self, view, item):
        old = self.selected
        self.selected = (view, item) if item is not None else None
        if old and old[0] is not view:
            old[0].queue_draw()
        if view:
            view.queue_draw()

    def delete_selected(self):
        if not self.selected:
            return
        view, item = self.selected
        page = view.page
        idx = page.images.index(item)
        page.images.remove(item)
        self.selected = None
        view.invalidate()

        def undo():
            page.images.insert(idx, item)
            view.invalidate()

        def redo():
            if item in page.images:
                page.images.remove(item)
            view.invalidate()
        self.push(undo, redo, done=True)

    def _store_image(self, source) -> tuple[str, int, int] | None:
        """Copia a imagem para imagens/ como PNG (no máximo 1800 px no lado maior)."""
        self.journal.images_dir.mkdir(parents=True, exist_ok=True)
        name = uuid.uuid4().hex[:12] + ".png"
        dest = self.journal.images_dir / name
        try:
            if isinstance(source, Gdk.Texture):
                tmp = self.journal.images_dir / (name + ".tmp.png")
                source.save_to_png(str(tmp))
                pix = GdkPixbuf.Pixbuf.new_from_file(str(tmp))
                tmp.unlink(missing_ok=True)
            else:
                pix = GdkPixbuf.Pixbuf.new_from_file(str(source))
                pix = pix.apply_embedded_orientation() or pix
        except GLib.Error as e:
            self._toast(_("Não consegui abrir a imagem: {err}", err=e.message))
            return None
        w, h = pix.get_width(), pix.get_height()
        k = min(1.0, MAX_IMAGE_SIDE / max(w, h))
        if k < 1:
            pix = pix.scale_simple(int(w * k), int(h * k), GdkPixbuf.InterpType.HYPER)
        pix.savev(str(dest), "png", [], [])
        return name, pix.get_width(), pix.get_height()

    def insert_image(self, source, view=None, pos=None):
        stored = self._store_image(source)
        if not stored:
            return False
        name, pw, ph = stored
        view = view or self.current_view()
        maxw = PAGE_W * 0.7
        w = min(maxw, pw * 0.75)          # px da imagem em unidades de página (96 dpi)
        h = w * ph / pw
        if h > PAGE_H * 0.6:
            h = PAGE_H * 0.6
            w = h * pw / ph
        if pos is None:
            x, y = (PAGE_W - w) / 2, 110
        else:
            x, y = pos[0] - w / 2, pos[1] - h / 2
        x = max(10, min(PAGE_W - w - 10, x))
        y = max(10, min(PAGE_H - h - 10, y))
        item = ImageItem(name, x, y, w, h)
        page = view.page
        page.images.append(item)
        view.invalidate()
        self.select_image(view, item)

        def undo():
            if item in page.images:
                page.images.remove(item)
            if self.selected and self.selected[1] is item:
                self.selected = None
            view.invalidate()

        def redo():
            page.images.append(item)
            view.invalidate()
        self.push(undo, redo, done=True)
        self.ensure_blank_last_page(page)
        return True

    def paste(self):
        cb = self.get_clipboard()
        formats = cb.get_formats()
        if formats.contain_gtype(Gdk.Texture):
            def done(c, res):
                try:
                    tex = c.read_texture_finish(res)
                except GLib.Error:
                    tex = None
                if tex:
                    self.insert_image(tex)
            cb.read_texture_async(None, done)
        elif formats.contain_gtype(Gdk.FileList):
            def done_files(c, res):
                try:
                    val = c.read_value_finish(res)
                except GLib.Error:
                    return
                for f in val.get_files():
                    if f.get_path():
                        self.insert_image(Path(f.get_path()))
            cb.read_value_async(Gdk.FileList, GLib.PRIORITY_DEFAULT, None, done_files)
        else:
            self._toast(_("A área de transferência não tem imagem"))

    def choose_image(self):
        dlg = Gtk.FileDialog(title=_("Inserir imagem"))
        filt = Gtk.FileFilter(name=_("Imagens"))
        filt.add_pixbuf_formats()
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filt)
        dlg.set_filters(store)

        def done(d, res):
            try:
                files = d.open_multiple_finish(res)
            except GLib.Error:
                return
            view = self.current_view()
            for i in range(files.get_n_items()):
                f = files.get_item(i)
                if f.get_path():
                    self.insert_image(Path(f.get_path()), view,
                                      (PAGE_W / 2 + 20 * i, 300 + 20 * i))
        dlg.open_multiple(self.get_root(), None, done)

    # ── menus ─────────────────────────────────────────────────────────────────
    def _popover_box(self, mb):
        pop = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for m in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{m}")(6)
        pop.set_child(box)
        mb.set_popover(pop)

        def item(label, cb, icon=None):
            b = Gtk.Button()
            row = Gtk.Box(spacing=10)
            if icon:
                row.append(Gtk.Image(icon_name=icon))
            row.append(Gtk.Label(label=label, xalign=0))
            b.set_child(row)
            b.add_css_class("flat")
            b.connect("clicked", lambda *_: (pop.popdown(), cb()))
            box.append(b)
        return box, item

    def _insert_menu(self, mb):
        _box, item = self._popover_box(mb)
        item(_("Imagem de um arquivo…"), self.choose_image, "image-x-generic-symbolic")
        item(_("Colar imagem (Ctrl+V)"), self.paste, "edit-paste-symbolic")
        item(_("Nova folha depois desta"), lambda: self.insert_page(self.views.index(self.current_view()) + 1),
             "document-new-symbolic")

    def _page_menu(self, mb, view):
        box, item = self._popover_box(mb)
        idx = lambda: self.views.index(view)
        item(_("Nova folha antes"), lambda: self.insert_page(idx()), "go-up-symbolic")
        item(_("Nova folha depois"), lambda: self.insert_page(idx() + 1), "go-down-symbolic")
        box.append(Gtk.Separator())
        for paper in PAPERS:
            mark = "  ✓" if view.page.paper == paper else ""
            item(_(PAPER_NAMES[paper]) + mark, lambda p=paper: self._set_paper(view, p))
        box.append(Gtk.Separator())
        item(_("Excluir folha"), lambda: self.delete_page(view.page), "user-trash-symbolic")

    def _set_paper(self, view, paper):
        old = view.page.paper

        def setp(p):
            view.page.paper = p
            view.invalidate()
        setp(paper)
        self.journal.meta["paper"] = paper
        self.push(lambda: setp(old), lambda: setp(paper), done=True)

    def _journal_menu(self, mb):
        _box, item = self._popover_box(mb)
        item(_("Exportar como PDF…"), self.export_pdf, "document-save-as-symbolic")
        item(_("Abrir a pasta do caderno"), lambda: Gtk.FileLauncher.new(
            Gio.File.new_for_path(str(self.journal.path))).launch(self.get_root(), None, None),
            "folder-open-symbolic")

    def export_pdf(self):
        self.save_now()
        dlg = Gtk.FileDialog(title=_("Exportar PDF"), initial_name=f"{self.journal.name}.pdf")

        def done(d, res):
            try:
                f = d.save_finish(res)
            except GLib.Error:
                return
            try:
                render.export_pdf(self.journal, Path(f.get_path()))
                self._toast(_("PDF exportado"))
            except Exception as e:  # noqa: BLE001
                self._toast(_("Falha ao exportar: {err}", err=e))
        dlg.save(self.get_root(), None, done)

    def _toast(self, text):
        root = self.get_root()
        if root and hasattr(root, "toast"):
            root.toast(text)

    def _tool_changed(self):
        for v in self.views:
            v.queue_draw()

    # ── atalhos ───────────────────────────────────────────────────────────────
    def _shortcuts(self):
        ctrl = Gtk.ShortcutController(scope=Gtk.ShortcutScope.GLOBAL)

        def add(trigger, cb):
            ctrl.add_shortcut(Gtk.Shortcut.new(Gtk.ShortcutTrigger.parse_string(trigger),
                                               Gtk.CallbackAction.new(lambda *_: (cb(), True)[1])))
        add("<Control>z", self.undo)
        add("<Control><Shift>z", self.redo)
        add("<Control>y", self.redo)
        add("<Control>v", self.paste)
        add("Delete", self.delete_selected)
        add("BackSpace", self.delete_selected)
        add("Escape", lambda: self.select_image(None, None))
        add("<Control>equal", lambda: self.set_zoom(self.zoom * 1.15))
        add("<Control>plus", lambda: self.set_zoom(self.zoom * 1.15))
        add("<Control>minus", lambda: self.set_zoom(self.zoom / 1.15))
        add("<Control>0", lambda: self._fit_zoom())
        add("<Control>s", self.save_now)
        for i in range(6):
            add(str(i + 1), lambda i=i: self.toolbar.select(i))
        self.add_controller(ctrl)
