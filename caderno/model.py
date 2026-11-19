"""Dados do caderno: páginas, traços e imagens, e como ficam no disco.

Um caderno é uma pasta `<nome>.caderno/` com `caderno.json` e `imagens/`.
As coordenadas são em unidades de página (A4 a 96 dpi: 794 x 1123).
"""
from __future__ import annotations

import json
import math
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

PAGE_W, PAGE_H = 794.0, 1123.0
PAPERS = ("pautado", "quadriculado", "pontilhado", "liso")
FORMAT_VERSION = 1


@dataclass(eq=False)
class Stroke:
    kind: str                 # "pen" | "hl" (marca-texto)
    color: str                # "#rrggbb"
    width: float
    points: list              # [[x, y, pressão], ...]
    shape: str | None = None  # forma inteligente que este traço virou ("círculo", ...)
    _bbox: tuple | None = field(default=None, repr=False, compare=False)

    def bbox(self):
        if self._bbox is None:
            xs = [p[0] for p in self.points]
            ys = [p[1] for p in self.points]
            m = self.width
            self._bbox = (min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)
        return self._bbox

    def to_json(self):
        d = {"k": self.kind, "c": self.color, "w": round(self.width, 2),
             "p": [[round(x, 1), round(y, 1), round(p, 3)] for x, y, p in self.points]}
        if self.shape:
            d["s"] = self.shape
        return d

    @classmethod
    def from_json(cls, d):
        return cls(d["k"], d["c"], d["w"], [list(p) for p in d["p"]], d.get("s"))

    def hit(self, x, y, r):
        """O ponto (x, y) com raio r encosta neste traço?"""
        x0, y0, x1, y1 = self.bbox()
        if x < x0 - r or x > x1 + r or y < y0 - r or y > y1 + r:
            return False
        reach = r + self.width / 2
        pts = self.points
        if len(pts) == 1:
            return math.hypot(x - pts[0][0], y - pts[0][1]) <= reach
        for (ax, ay, _), (bx, by, _) in zip(pts, pts[1:]):
            dx, dy = bx - ax, by - ay
            l2 = dx * dx + dy * dy
            t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / l2))
            if math.hypot(x - (ax + t * dx), y - (ay + t * dy)) <= reach:
                return True
        return False


def _reversals(values, min_move):
    """Quantas vezes a sequência muda de sentido, contando só idas de pelo menos min_move."""
    count, direction = 0, 0
    lo = hi = values[0]
    for v in values[1:]:
        if direction == 0:
            lo, hi = min(lo, v), max(hi, v)
            if hi - v >= min_move:
                direction = -1
                lo = v
            elif v - lo >= min_move:
                direction = 1
                hi = v
        elif direction == 1:
            if v > hi:
                hi = v
            elif hi - v >= min_move:
                count, direction, lo = count + 1, -1, v
        else:
            if v < lo:
                lo = v
            elif v - lo >= min_move:
                count, direction, hi = count + 1, 1, v
    return count


def is_scribble(s: Stroke) -> bool:
    """Um rabisco de "riscar fora": vai e volta várias vezes (na horizontal ou na vertical),
    com um caminho bem mais longo que a área que cobre."""
    if s.kind != "pen" or len(s.points) < 12:
        return False
    x0, y0, x1, y1 = s.bbox()
    w, h = x1 - x0 - 2 * s.width, y1 - y0 - 2 * s.width
    if max(w, h) < 12:
        return False
    xs = [p[0] for p in s.points]
    ys = [p[1] for p in s.points]
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(s.points, s.points[1:]))
    rx = _reversals(xs, max(8.0, 0.3 * w))
    ry = _reversals(ys, max(8.0, 0.5 * h))
    # vai e volta na horizontal por cima da palavra
    if rx >= 4 and length >= 3.2 * max(w, h):
        return True
    # zigue-zague vertical (WWWW) atravessando a palavra: mais idas e voltas, de altura cheia
    return ry >= 6 and length >= 2.4 * max(w, h) and h >= 0.15 * w


def scribble_targets(page: "Page", scribble: Stroke) -> list:
    """Traços que o rabisco cobre: a maior parte dos pontos dentro da área do rabisco
    e cruzados por ele. Lista de (índice, traço)."""
    x0, y0, x1, y1 = scribble.bbox()
    pad = 4
    probe = scribble.points[::2]
    out = []
    for i, st in enumerate(page.strokes):
        if st is scribble or not st.points:
            continue
        sx0, sy0, sx1, sy1 = st.bbox()
        if sx1 < x0 or sx0 > x1 or sy1 < y0 or sy0 > y1:
            continue
        inside = sum(1 for x, y, _ in st.points if x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad)
        if inside / len(st.points) < 0.6:
            continue
        if any(st.hit(x, y, scribble.width) for x, y, _ in probe):
            out.append((i, st))
    return out


@dataclass(eq=False)
class ImageItem:
    file: str                 # nome do arquivo em imagens/
    x: float
    y: float
    w: float
    h: float

    def to_json(self):
        return {"f": self.file, "x": round(self.x, 1), "y": round(self.y, 1),
                "w": round(self.w, 1), "h": round(self.h, 1)}

    @classmethod
    def from_json(cls, d):
        return cls(d["f"], d["x"], d["y"], d["w"], d["h"])

    def contains(self, x, y):
        return self.x <= x <= self.x + self.w and self.y <= y <= self.y + self.h


@dataclass(eq=False)
class Heading:
    """Um título: a faixa de uma linha (y0..y1) a partir do marcador em x."""
    x: float
    y0: float
    y1: float

    MARK = 20.0   # largura do marcador "#"

    def to_json(self):
        return {"x": round(self.x, 1), "y0": round(self.y0, 1), "y1": round(self.y1, 1)}

    @classmethod
    def from_json(cls, d):
        return cls(d["x"], d["y0"], d["y1"])

    def marker_rect(self):
        h = min(self.MARK, self.y1 - self.y0 - 6)
        cy = (self.y0 + self.y1) / 2
        return self.x, cy - h / 2, self.MARK, h

    def title_strokes(self, page: "Page"):
        """Os traços escritos na faixa do título, à direita do marcador."""
        out = []
        for st in page.strokes:
            x0, y0, x1, y1 = st.bbox()
            cy = (y0 + y1) / 2
            if self.y0 - 6 <= cy <= self.y1 + 6 and x1 > self.x + self.MARK:
                out.append(st)
        return out


@dataclass(eq=False)
class Page:
    paper: str = "pautado"
    strokes: list = field(default_factory=list)
    images: list = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    headings: list = field(default_factory=list)

    def is_empty(self):
        return not self.strokes and not self.images and not self.headings

    def to_json(self):
        d = {"id": self.id, "paper": self.paper,
             "strokes": [s.to_json() for s in self.strokes],
             "images": [i.to_json() for i in self.images]}
        if self.headings:
            d["headings"] = [h.to_json() for h in self.headings]
        return d

    @classmethod
    def from_json(cls, d):
        return cls(d.get("paper", "pautado"),
                   [Stroke.from_json(s) for s in d.get("strokes", [])],
                   [ImageItem.from_json(i) for i in d.get("images", [])],
                   d.get("id") or uuid.uuid4().hex[:10],
                   [Heading.from_json(h) for h in d.get("headings", [])])


class Journal:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.pages: list[Page] = []
        self.meta = {"color": "#c47bdc", "paper": "pautado", "created": time.time()}

    @property
    def name(self):
        return self.path.name.removesuffix(".caderno")

    @property
    def images_dir(self):
        return self.path / "imagens"

    @classmethod
    def load(cls, path: Path) -> "Journal":
        j = cls(path)
        f = j.path / "caderno.json"
        if f.exists():
            d = json.loads(f.read_text())
            j.meta.update(d.get("meta", {}))
            j.pages = [Page.from_json(p) for p in d.get("pages", [])]
        if not j.pages:
            j.pages = [Page(j.meta.get("paper", "pautado"))]
        return j

    def save(self):
        self.path.mkdir(parents=True, exist_ok=True)
        d = {"version": FORMAT_VERSION, "meta": self.meta,
             "pages": [p.to_json() for p in self.pages]}
        tmp = self.path / "caderno.json.tmp"
        tmp.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")))
        os.replace(tmp, self.path / "caderno.json")

    def new_page(self):
        return Page(self.meta.get("paper", "pautado"))
