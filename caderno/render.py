"""Desenho com Cairo: o papel, os traços com pressão, as imagens e a exportação em PDF."""
from __future__ import annotations

import math
from pathlib import Path

import cairo

from .model import PAGE_H, PAGE_W, Journal, Page, Stroke

PAPER = (0.925, 0.918, 0.910)        # cinza-claro quente, como o Journal
LINE = (0.93, 0.76, 0.69)            # pauta salmão clara
MARGIN_TOP = 96
LINE_GAP = 34
GRID = 26


def hex_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def draw_paper(cr, paper: str):
    cr.set_source_rgb(*PAPER)
    cr.paint()
    cr.set_line_width(1.0)
    if paper == "pautado":
        cr.set_source_rgb(*LINE)
        y = MARGIN_TOP
        while y < PAGE_H - 20:
            cr.move_to(0, y + 0.5)
            cr.line_to(PAGE_W, y + 0.5)
            y += LINE_GAP
        cr.stroke()
    elif paper == "quadriculado":
        cr.set_source_rgba(*LINE, 0.75)
        x = 0
        while x <= PAGE_W:
            cr.move_to(x + 0.5, 0)
            cr.line_to(x + 0.5, PAGE_H)
            x += GRID
        y = 0
        while y <= PAGE_H:
            cr.move_to(0, y + 0.5)
            cr.line_to(PAGE_W, y + 0.5)
            y += GRID
        cr.stroke()
    elif paper == "pontilhado":
        cr.set_source_rgb(*LINE)
        y = GRID
        while y < PAGE_H:
            x = GRID
            while x < PAGE_W:
                cr.arc(x, y, 1.3, 0, 2 * math.pi)
                cr.fill()
                x += GRID
            y += GRID


def pen_width(base: float, pressure: float) -> float:
    return base * (0.3 + 0.7 * max(0.0, min(1.0, pressure)) ** 0.75)


def stroke_path(cr, s: Stroke):
    """Contorno de um traço de caneta com largura variável pela pressão."""
    pts = s.points
    n = len(pts)
    if n == 1:
        x, y, p = pts[0]
        cr.arc(x, y, pen_width(s.width, p) / 2, 0, 2 * math.pi)
        return
    left, right = [], []
    for i in range(n):
        x, y, p = pts[i]
        ax, ay = pts[max(0, i - 1)][:2]
        bx, by = pts[min(n - 1, i + 1)][:2]
        dx, dy = bx - ax, by - ay
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        r = pen_width(s.width, p) / 2
        left.append((x + nx * r, y + ny * r))
        right.append((x - nx * r, y - ny * r))
    cr.move_to(*left[0])
    for pt in left[1:]:
        cr.line_to(*pt)
    # ponta final arredondada
    x, y, p = pts[-1]
    ang = math.atan2(left[-1][1] - y, left[-1][0] - x)
    cr.arc_negative(x, y, pen_width(s.width, p) / 2, ang, ang - math.pi)
    for pt in reversed(right[:-1]):
        cr.line_to(*pt)
    x, y, p = pts[0]
    ang = math.atan2(right[0][1] - y, right[0][0] - x)
    cr.arc_negative(x, y, pen_width(s.width, p) / 2, ang, ang - math.pi)
    cr.close_path()


def draw_stroke(cr, s: Stroke):
    r, g, b = hex_rgb(s.color)
    if s.kind == "hl":
        cr.save()
        cr.set_operator(cairo.OPERATOR_MULTIPLY)
        cr.set_source_rgba(r, g, b, 0.85)
        cr.set_line_width(s.width)
        cr.set_line_cap(cairo.LINE_CAP_SQUARE)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        pts = s.points
        cr.move_to(pts[0][0], pts[0][1])
        for x, y, _ in pts[1:]:
            cr.line_to(x, y)
        if len(pts) == 1:
            cr.line_to(pts[0][0] + 0.1, pts[0][1])
        cr.stroke()
        cr.restore()
    else:
        cr.set_source_rgb(r, g, b)
        cr.set_fill_rule(cairo.FILL_RULE_WINDING)
        stroke_path(cr, s)
        cr.fill()


class ImageCache:
    """Superfícies Cairo das imagens do caderno, carregadas uma vez."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.cache = {}

    def get(self, name: str):
        if name not in self.cache:
            try:
                self.cache[name] = cairo.ImageSurface.create_from_png(str(self.folder / name))
            except (cairo.Error, OSError, MemoryError):
                self.cache[name] = None
        return self.cache[name]


def draw_image(cr, item, images: ImageCache):
    surf = images.get(item.file)
    cr.save()
    if surf is None:
        cr.set_source_rgb(0.8, 0.8, 0.8)
        cr.rectangle(item.x, item.y, item.w, item.h)
        cr.fill()
    else:
        cr.translate(item.x, item.y)
        cr.scale(item.w / surf.get_width(), item.h / surf.get_height())
        cr.set_source_surface(surf, 0, 0)
        cr.get_source().set_filter(cairo.FILTER_GOOD)
        cr.paint()
    cr.restore()


HEADING_COLOR = "#8a4fc7"


def draw_heading(cr, hd):
    """Marcador de título: uma etiqueta roxa com "#" no lugar onde o # foi desenhado."""
    x, y, w, h = hd.marker_rect()
    r = min(5.0, h / 2)
    cr.save()
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()
    cr.set_source_rgb(*hex_rgb(HEADING_COLOR))
    cr.fill()
    # o "#" desenhado à mão, em branco
    cr.set_source_rgb(1, 1, 1)
    cr.set_line_width(1.8)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    for k in (0.38, 0.64):
        cr.move_to(x + w * k + 1.2, y + h * 0.22)
        cr.line_to(x + w * k - 1.2, y + h * 0.78)
        cr.move_to(x + w * 0.2, y + h * (k + 0.0))
        cr.line_to(x + w * 0.82, y + h * (k + 0.0))
    cr.stroke()
    cr.restore()


def render_page(cr, page: Page, images: ImageCache, paper=True):
    if paper:
        draw_paper(cr, page.paper)
    for item in page.images:
        draw_image(cr, item, images)
    for s in page.strokes:        # marca-texto por baixo da tinta
        if s.kind == "hl":
            draw_stroke(cr, s)
    for s in page.strokes:
        if s.kind != "hl":
            draw_stroke(cr, s)
    for hd in page.headings:
        draw_heading(cr, hd)


def export_pdf(journal: Journal, out: Path):
    # A4 em pontos (72 dpi): a página tem 794x1123 unidades a 96 dpi
    k = 72 / 96
    surf = cairo.PDFSurface(str(out), PAGE_W * k, PAGE_H * k)
    images = ImageCache(journal.images_dir)
    cr = cairo.Context(surf)
    pages = list(journal.pages)
    while len(pages) > 1 and pages[-1].is_empty():   # sem a folha em branco do fim
        pages.pop()
    for page in pages:
        cr.save()
        cr.scale(k, k)
        render_page(cr, page, images)
        cr.restore()
        cr.show_page()
    surf.finish()
