"""Formas inteligentes: segure a caneta parada no fim de um traço e ele vira
uma linha reta, um círculo/elipse, um retângulo ou um triângulo."""
from __future__ import annotations

import math

HOLD_SECONDS = 0.6     # tempo parado com a caneta encostada
STILL_RADIUS = 4.0     # quanto a caneta pode tremer e ainda contar como parada (unidades de página)


def _dist_to_segment(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _resample(pts, step):
    out = [pts[0]]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(bx - ax, by - ay) / step))
        out += [(ax + (bx - ax) * i / n, ay + (by - ay) * i / n) for i in range(1, n + 1)]
    return out


def _snap_angle(ax, ay, bx, by, tol=6.0):
    """Linha quase horizontal/vertical/45° vira exatamente isso."""
    ang = math.degrees(math.atan2(by - ay, bx - ax))
    snap = round(ang / 45) * 45
    if abs(ang - snap) <= tol:
        r = math.hypot(bx - ax, by - ay)
        return ax + r * math.cos(math.radians(snap)), ay + r * math.sin(math.radians(snap))
    return bx, by


def _polygon_error(pts, corners):
    """Distância média dos pontos ao polígono fechado, relativa ao tamanho."""
    edges = list(zip(corners, corners[1:] + corners[:1]))
    total = 0.0
    for x, y in pts:
        total += min(_dist_to_segment(x, y, *a, *b) for a, b in edges)
    return total / len(pts)


def _triangle_corners(pts):
    """Três cantos: os dois pontos mais distantes e o mais longe da reta entre eles."""
    best, a, b = -1, 0, 0
    step = max(1, len(pts) // 60)
    sample = pts[::step]
    for i, p in enumerate(sample):
        for q in sample[i + 1:]:
            d = math.hypot(p[0] - q[0], p[1] - q[1])
            if d > best:
                best, a, b = d, p, q
    c = max(pts, key=lambda p: _dist_to_segment(p[0], p[1], *a, *b))
    return [a, b, c]


def _covers(pts, corners, tol):
    """Cada lado do polígono tem traço perto em pelo menos 85% do comprimento."""
    step = max(1, len(pts) // 150)
    sample = pts[::step]
    for a, b in zip(corners, corners[1:] + corners[:1]):
        marks = _resample([a, b], max(3.0, math.hypot(b[0] - a[0], b[1] - a[1]) / 20))
        hit = sum(1 for mx, my in marks if any(math.hypot(mx - x, my - y) <= tol for x, y in sample))
        if hit < 0.85 * len(marks):
            return False
    return True


def recognize(points):
    """points: [(x, y), ...]. Devolve (nome, pontos_da_forma) ou None."""
    pts = [(p[0], p[1]) for p in points]
    if len(pts) < 6:
        return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    w, h = x1 - x0, y1 - y0
    size = max(w, h)
    if size < 15:
        return None
    # comprimento medido em pontos espaçados: o tremor da mão não infla o caminho
    coarse = [pts[0]]
    for p in pts[1:]:
        if math.hypot(p[0] - coarse[-1][0], p[1] - coarse[-1][1]) >= 8:
            coarse.append(p)
    coarse.append(pts[-1])
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(coarse, coarse[1:]))
    (ax, ay), (bx, by) = pts[0], pts[-1]
    gap = math.hypot(bx - ax, by - ay)

    # ── linha: aberta e quase sem desvio da reta entre as pontas ──
    if gap > 0.6 * size:
        if gap < 40:          # traços curtos (letras) não viram linha
            return None
        dev = max(_dist_to_segment(x, y, ax, ay, bx, by) for x, y in pts)
        if dev <= max(5.0, 0.07 * gap) and length <= 1.25 * gap:
            bx, by = _snap_angle(ax, ay, bx, by)
            return "linha", _resample([(ax, ay), (bx, by)], 4)
        return None

    # ── formas fechadas: o traço volta perto do começo ──
    if gap > 0.3 * size or length < 2.2 * size or size < 30:
        return None
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, w / 2, h / 2
    if min(rx, ry) < 4:
        return None
    # elipse alinhada aos eixos (círculo se os raios são parecidos)
    ell_err = sum(abs(math.hypot((x - cx) / rx, (y - cy) / ry) - 1) for x, y in pts) / len(pts)
    rect = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    rect_err = _polygon_error(pts, rect) / size
    tri = _triangle_corners(pts)
    tri_err = _polygon_error(pts, tri) / size
    cands = []
    if ell_err < 0.13:
        cands.append((ell_err, "elipse"))
    if rect_err < 0.06 and _covers(pts, rect, 0.1 * size):   # o traço percorre os 4 lados
        cands.append((rect_err * 1.6, "retângulo"))   # comparável ao erro radial da elipse
    if tri_err < 0.06 and _covers(pts, tri, 0.1 * size):
        cands.append((tri_err * 1.6, "triângulo"))
    if not cands:
        return None
    _err, kind = min(cands)
    if kind == "elipse":
        if abs(rx - ry) / max(rx, ry) < 0.18:      # quase redondo: círculo perfeito
            rx = ry = (rx + ry) / 2
            kind = "círculo"
        n = max(32, int(2 * math.pi * max(rx, ry) / 3))
        # começa onde o traço começou, para o desenho "fechar" no mesmo lugar
        a0 = math.atan2((ay - cy) / ry, (ax - cx) / rx)
        ring = [(cx + rx * math.cos(a0 + 2 * math.pi * i / n), cy + ry * math.sin(a0 + 2 * math.pi * i / n))
                for i in range(n + 1)]
        return kind, ring
    corners = rect if kind == "retângulo" else tri
    if kind == "retângulo" and abs(w - h) / size < 0.1:   # quase quadrado: quadrado
        side = (w + h) / 2
        corners = [(cx - side / 2, cy - side / 2), (cx + side / 2, cy - side / 2),
                   (cx + side / 2, cy + side / 2), (cx - side / 2, cy + side / 2)]
    return kind, _resample(corners + corners[:1], 3)


# ── "#" para criar título ────────────────────────────────────────────────────

def _straight(points):
    """(ax, ay, bx, by) se o traço é quase reto, senão None."""
    pts = [(p[0], p[1]) for p in points]
    if len(pts) < 2:
        return None
    (ax, ay), (bx, by) = pts[0], pts[-1]
    ln = math.hypot(bx - ax, by - ay)
    if ln < 7:
        return None
    dev = max(_dist_to_segment(x, y, ax, ay, bx, by) for x, y in pts)
    return (ax, ay, bx, by) if dev <= max(3.5, 0.22 * ln) else None


def _segments_cross(a, b, inner=0.08):
    """Os segmentos se cruzam no meio (não nas pontas, como os cantos de uma caixa)?"""
    x1, y1, x2, y2 = a
    x3, y3, x4, y4 = b
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(d) < 1e-9:
        return False
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / d
    return inner <= t <= 1 - inner and inner <= u <= 1 - inner


def is_hash(strokes):
    """Quatro traços curtos e retos formando um "#": dois deitados, dois em pé,
    cada deitado cruzando os dois em pé. Devolve o bbox (x0, y0, x1, y1) ou None."""
    if len(strokes) != 4:
        return None
    segs = []
    for st in strokes:
        seg = _straight(st.points)
        if seg is None:
            return None
        segs.append(seg)
    xs = [v for s in segs for v in (s[0], s[2])]
    ys = [v for s in segs for v in (s[1], s[3])]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    if max(x1 - x0, y1 - y0) > 90 or max(x1 - x0, y1 - y0) < 10:
        return None

    def angle(s):
        a = abs(math.degrees(math.atan2(s[3] - s[1], s[2] - s[0]))) % 180
        return min(a, 180 - a)        # 0 = deitado, 90 = em pé
    flat = [s for s in segs if angle(s) <= 35]
    up = [s for s in segs if angle(s) >= 50]
    if len(flat) != 2 or len(up) != 2:
        return None
    if all(_segments_cross(f, u) for f in flat for u in up):
        return x0, y0, x1, y1
    return None
