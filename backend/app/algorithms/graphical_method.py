"""
Método Gráfico (problemas com exatamente duas variáveis de decisão).

A região viável é calculada matematicamente, não desenhada à mão:
  1. Cada restrição (e cada condição de sinal) define um semiplano a1·x1 + a2·x2 (≤|≥|=) b.
  2. Todas as interseções entre pares de retas-fronteira são calculadas (regra de Cramer,
     aritmética exata). As que satisfazem TODAS as restrições são os vértices da região.
  3. O cone de recessão {d : a·d ≤ 0, ...} é testado nas direções das retas-fronteira para
     saber se a região é ilimitada e se Z melhora indefinidamente ao longo dela.
  4. Para o desenho, a região é recortada (Sutherland–Hodgman) por uma janela retangular;
     em regiões ilimitadas, a janela é apenas uma moldura de visualização.
  5. Z é avaliado em cada vértice; o melhor valor é o ótimo (se a região for limitada na
     direção de melhoria). Vértices empatados indicam um segmento de soluções ótimas.
As curvas de nível c1·x1 + c2·x2 = k são retas paralelas; a última que ainda toca a região
no sentido de melhoria (vetor gradiente c para MAX, −c para MIN) passa pelo ponto ótimo.

NumPy é utilizado para as amostragens em ponto flutuante destinadas à visualização.
"""
from __future__ import annotations

import math
from fractions import Fraction
from typing import List, Optional, Tuple

import numpy as np

from app.algorithms.lp_model import LPModel
from app.utils.numerical_utils import OP_SYMBOL, ZERO, fmt, fmt_dec, linear_text

Point = Tuple[Fraction, Fraction]
MAX_LATTICE = 6000


def _halfplanes(model: LPModel):
    hp = []
    for i in range(model.m):
        hp.append({"a": (model.A[i][0], model.A[i][1]), "op": model.ops[i], "b": model.b[i],
                   "name": model.con_names[i], "label": model.constraint_text(i), "kind": "constraint",
                   "index": i})
    for j, s in enumerate(model.var_signs):
        a = (Fraction(1), ZERO) if j == 0 else (ZERO, Fraction(1))
        nm = model.var_names[j]
        if s == "nonneg":
            hp.append({"a": a, "op": ">=", "b": ZERO, "name": f"{nm} ≥ 0", "label": f"{nm} ≥ 0", "kind": "sign"})
        elif s == "nonpos":
            hp.append({"a": a, "op": "<=", "b": ZERO, "name": f"{nm} ≤ 0", "label": f"{nm} ≤ 0", "kind": "sign"})
    return hp


def _sat(h, p: Point) -> bool:
    v = h["a"][0] * p[0] + h["a"][1] * p[1]
    if h["op"] == "<=":
        return v <= h["b"]
    if h["op"] == ">=":
        return v >= h["b"]
    return v == h["b"]


def _sat_dir(h, d: Point) -> bool:
    v = h["a"][0] * d[0] + h["a"][1] * d[1]
    if h["op"] == "<=":
        return v <= 0
    if h["op"] == ">=":
        return v >= 0
    return v == 0


def _intersect(h1, h2) -> Optional[Point]:
    a1, b1 = h1["a"]
    a2, b2 = h2["a"]
    det = a1 * b2 - b1 * a2
    if det == 0:
        return None
    x = (h1["b"] * b2 - b1 * h2["b"]) / det
    y = (a1 * h2["b"] - h1["b"] * a2) / det
    return (x, y)


def _clip(poly: List[Point], h) -> List[Point]:
    """Sutherland–Hodgman: recorta um polígono convexo por um semiplano (exato)."""
    def inside(p, op):
        v = h["a"][0] * p[0] + h["a"][1] * p[1]
        return v <= h["b"] if op == "<=" else v >= h["b"]

    def cut(p, q):
        a, b = h["a"]
        vp = a * p[0] + b * p[1] - h["b"]
        vq = a * q[0] + b * q[1] - h["b"]
        t = vp / (vp - vq)
        return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))

    ops = ["<=", ">="] if h["op"] == "=" else [h["op"]]
    for op in ops:
        if not poly:
            return []
        out = []
        for idx in range(len(poly)):
            cur, prev = poly[idx], poly[idx - 1]
            cin, pin = inside(cur, op), inside(prev, op)
            if cin:
                if not pin:
                    out.append(cut(prev, cur))
                out.append(cur)
            elif pin:
                out.append(cut(prev, cur))
        dedup = []
        for p in out:
            if not dedup or dedup[-1] != p:
                dedup.append(p)
        if len(dedup) > 1 and dedup[0] == dedup[-1]:
            dedup.pop()
        poly = dedup
    return poly


def _line_box(a1: float, a2: float, b: float, box) -> Optional[List[List[float]]]:
    xlo, xhi, ylo, yhi = box
    pts = []
    eps = 1e-9 * max(1.0, abs(xhi - xlo), abs(yhi - ylo))
    if abs(a2) > 1e-15:
        for x in (xlo, xhi):
            y = (b - a1 * x) / a2
            if ylo - eps <= y <= yhi + eps:
                pts.append((x, y))
    if abs(a1) > 1e-15:
        for y in (ylo, yhi):
            x = (b - a2 * y) / a1
            if xlo - eps <= x <= xhi + eps:
                pts.append((x, y))
    if len(pts) < 2:
        return None
    pts.sort()
    return [[pts[0][0], pts[0][1]], [pts[-1][0], pts[-1][1]]]


def _box(core: List[Tuple[float, float]], extra: List[Tuple[float, float]], unbounded: bool):
    xs = [p[0] for p in core] or [0.0]
    ys = [p[1] for p in core] or [0.0]
    xmin, xmax, ymin, ymax = min(xs + [0.0]), max(xs + [0.0]), min(ys + [0.0]), max(ys + [0.0])
    w0, h0 = max(xmax - xmin, 1.0), max(ymax - ymin, 1.0)
    for (x, y) in extra:  # interceptos próximos, para que as retas fiquem visíveis
        if xmin - 1.5 * w0 <= x <= xmax + 1.5 * w0 and ymin - 1.5 * h0 <= y <= ymax + 1.5 * h0:
            xmin, xmax, ymin, ymax = min(xmin, x), max(xmax, x), min(ymin, y), max(ymax, y)
    w, h = max(xmax - xmin, 1.0), max(ymax - ymin, 1.0)
    pad = 0.45 if unbounded else 0.15
    return [xmin - 0.08 * w if xmin >= 0 else xmin - pad * w, xmax + pad * w,
            ymin - 0.08 * h if ymin >= 0 else ymin - pad * h, ymax + pad * h]


def solve_graphical(model: LPModel, lp_result: Optional[dict] = None, integer_points: bool = True) -> dict:
    if model.n != 2:
        return {
            "available": False,
            "message": (f"O método gráfico bidimensional exige exatamente 2 variáveis de decisão; este modelo possui "
                        f"{model.n}. Uma projeção em 2D não representaria integralmente a região viável "
                        f"multidimensional. Utilize o Simplex Tabular."),
        }
    hp = _halfplanes(model)
    names = model.var_names
    c = model.c

    # ---- interseções entre todas as retas-fronteira
    inter = []
    for i in range(len(hp)):
        for j in range(i + 1, len(hp)):
            p = _intersect(hp[i], hp[j])
            if p is None:
                continue
            feas = all(_sat(h, p) for h in hp)
            inter.append({"p": p, "lines": [hp[i]["name"], hp[j]["name"]], "feasible": feas})
    # vértices (únicos)
    vmap = {}
    for it in inter:
        if it["feasible"]:
            v = vmap.setdefault(it["p"], set())
            v.update(it["lines"])
    vertices = [{"p": p, "lines": sorted(ls)} for p, ls in vmap.items()]

    lp_status = lp_result.get("status") if lp_result else None
    feasible = bool(vertices) or lp_status in ("optimal", "unbounded")

    # ---- cone de recessão
    dirs = [(Fraction(1), ZERO), (ZERO, Fraction(1)), (Fraction(-1), ZERO), (ZERO, Fraction(-1))]
    for h in hp:
        a1, a2 = h["a"]
        dirs += [(a2, -a1), (-a2, a1)]
    rec = []
    for d in dirs:
        if d == (ZERO, ZERO) or d in rec:
            continue
        if all(_sat_dir(h, d) for h in hp):
            rec.append(d)
    unbounded_region = feasible and bool(rec)
    sgn = 1 if model.sense == "max" else -1
    improving_dirs = [d for d in rec if sgn * (c[0] * d[0] + c[1] * d[1]) > 0]
    flat_dirs = [d for d in rec if c[0] * d[0] + c[1] * d[1] == 0]
    objective_unbounded = feasible and bool(improving_dirs)

    # ---- ótimo
    for v in vertices:
        v["z"] = c[0] * v["p"][0] + c[1] * v["p"][1]
    status = "infeasible"
    opt_z = None
    optimal_points: List[Point] = []
    if feasible:
        if objective_unbounded:
            status = "unbounded"
        elif vertices:
            status = "optimal"
            opt_z = max(v["z"] for v in vertices) if sgn > 0 else min(v["z"] for v in vertices)
            optimal_points = [v["p"] for v in vertices if v["z"] == opt_z]
        elif lp_result and lp_result.get("_x") is not None:
            status = "optimal"
            x = lp_result["_x"]
            optimal_points = [(x[0], x[1])]
            opt_z = model.objective_at(x)

    opt_set = None
    if status == "optimal":
        if len(optimal_points) >= 2:
            pts = sorted(optimal_points)
            opt_set = {"type": "segment", "points": [[float(p[0]), float(p[1])] for p in (pts[0], pts[-1])]}
        elif flat_dirs:
            d = flat_dirs[0]
            opt_set = {"type": "ray", "points": [[float(optimal_points[0][0]), float(optimal_points[0][1])]],
                       "direction": [float(d[0]), float(d[1])]}
        else:
            opt_set = {"type": "point", "points": [[float(optimal_points[0][0]), float(optimal_points[0][1])]]}

    # ---- janela de visualização
    core = [(float(v["p"][0]), float(v["p"][1])) for v in vertices]
    if lp_result and lp_result.get("_x") is not None:
        core.append((float(lp_result["_x"][0]), float(lp_result["_x"][1])))
    extra = []
    for h in hp:
        if h["kind"] != "constraint":
            continue
        a1, a2 = float(h["a"][0]), float(h["a"][1])
        b = float(h["b"])
        if a1:
            extra.append((b / a1, 0.0))
        if a2:
            extra.append((0.0, b / a2))
    if not core:
        core = [(float(it["p"][0]), float(it["p"][1])) for it in inter] + extra
    box = _box(core, extra, unbounded_region)
    xlo, xhi, ylo, yhi = box

    # ---- polígono da região (recortado pela janela)
    region = []
    if feasible:
        poly = [(Fraction(xlo), Fraction(ylo)), (Fraction(xhi), Fraction(ylo)),
                (Fraction(xhi), Fraction(yhi)), (Fraction(xlo), Fraction(yhi))]
        for h in hp:
            poly = _clip(poly, h)
        region = [[float(p[0]), float(p[1])] for p in poly]

    # ---- retas das restrições
    lines = []
    for h in hp:
        seg = _line_box(float(h["a"][0]), float(h["a"][1]), float(h["b"]), box)
        lines.append({"name": h["name"], "label": h["label"], "kind": h["kind"], "segment": seg,
                      "operator": h["op"], "equation": f"{linear_text(h['a'], names)} = {fmt(h['b'])}"})

    # ---- curvas de nível
    c1, c2 = float(c[0]), float(c[1])
    levels = []
    if feasible and region:
        zs = np.array([c1 * p[0] + c2 * p[1] for p in region])
        if status == "optimal":
            zstar = float(opt_z)
            zfar = float(zs.min()) if sgn > 0 else float(zs.max())
            if abs(zfar - zstar) < 1e-12:
                corners = np.array([c1 * x + c2 * y for x in (xlo, xhi) for y in (ylo, yhi)])
                zfar = float(corners.min()) if sgn > 0 else float(corners.max())
            ks = list(np.linspace(zfar, zstar, 5))
        else:
            zfrom = float(zs.min()) if sgn > 0 else float(zs.max())
            zto = float(zs.max()) if sgn > 0 else float(zs.min())
            ks = list(np.linspace(zfrom, zto, 5))
        for idx, k in enumerate(ks):
            seg = _line_box(c1, c2, float(k), box)
            if seg:
                is_opt = status == "optimal" and idx == len(ks) - 1
                levels.append({"z": float(k), "z_text": fmt(opt_z) if is_opt else fmt_dec(Fraction(k), 2),
                               "segment": seg, "optimal": is_opt})

    # ---- vetor gradiente (direção de melhoria)
    norm = math.hypot(c1, c2) or 1.0
    diag = math.hypot(xhi - xlo, yhi - ylo)
    if optimal_points:
        anchor = (float(optimal_points[0][0]), float(optimal_points[0][1]))
    elif region:
        anchor = (float(np.mean([p[0] for p in region])), float(np.mean([p[1] for p in region])))
    else:
        anchor = ((xlo + xhi) / 2, (ylo + yhi) / 2)
    L = 0.12 * diag
    gradient = {"from": list(anchor),
                "to": [anchor[0] + sgn * c1 / norm * L, anchor[1] + sgn * c2 / norm * L],
                "text": ("gradiente ∇Z = c (sentido de aumento de Z)" if sgn > 0 else
                         "−∇Z (sentido de diminuição de Z)")}

    # ---- pontos inteiros viáveis
    lattice = {"points": [], "sampled": False, "count": 0, "step": 1}
    if integer_points and feasible:
        ix0, ix1 = math.ceil(xlo), math.floor(xhi)
        iy0, iy1 = math.ceil(ylo), math.floor(yhi)
        total = max(0, ix1 - ix0 + 1) * max(0, iy1 - iy0 + 1)
        step = 1
        if total > MAX_LATTICE:
            step = math.ceil(math.sqrt(total / MAX_LATTICE))
            lattice["sampled"] = True
        pts = []
        for xi in range(ix0, ix1 + 1, step):
            for yi in range(iy0, iy1 + 1, step):
                p = (Fraction(xi), Fraction(yi))
                if all(_sat(h, p) for h in hp):
                    pts.append([xi, yi, float(c[0] * xi + c[1] * yi)])
        lattice.update({"points": pts, "count": len(pts), "step": step})

    def pjson(p):
        return {"x": float(p[0]), "y": float(p[1]), "x_text": fmt(p[0]), "y_text": fmt(p[1])}

    return {
        "available": True,
        "status": status,
        "feasible": feasible,
        "region_unbounded": unbounded_region,
        "objective_unbounded": objective_unbounded,
        "box": box,
        "region": region,
        "lines": lines,
        "vertices": [{**pjson(v["p"]), "z": float(v["z"]), "z_text": fmt(v["z"]), "lines": v["lines"],
                      "optimal": status == "optimal" and v["z"] == opt_z} for v in vertices],
        "intersections": [{**pjson(it["p"]), "lines": it["lines"], "feasible": it["feasible"]} for it in inter],
        "optimal": ({"points": [pjson(p) for p in optimal_points], "z": float(opt_z), "z_text": fmt(opt_z)}
                    if status == "optimal" else None),
        "optimal_set": opt_set,
        "levels": levels,
        "gradient": gradient,
        "objective": {"c": [c1, c2], "sense": model.sense, "text": model.objective_text()},
        "variables": names,
        "integer_points": lattice,
        "message": _message(status, unbounded_region, opt_set, opt_z),
    }


def _message(status, unbounded_region, opt_set, opt_z):
    if status == "infeasible":
        return "Não existe ponto que satisfaça todas as restrições simultaneamente: região viável vazia."
    if status == "unbounded":
        return ("A região viável é ilimitada e as curvas de nível podem ser deslocadas indefinidamente no sentido "
                "de melhoria: o problema é ilimitado.")
    txt = f"O ótimo é atingido com Z = {fmt(opt_z)}"
    if opt_set and opt_set["type"] == "segment":
        txt += (": a curva de nível ótima coincide com uma aresta da região, logo todo o segmento entre os dois "
                "vértices destacados é ótimo (soluções múltiplas).")
    elif opt_set and opt_set["type"] == "ray":
        txt += ": a curva de nível ótima contém uma semirreta da região (infinitas soluções ótimas)."
    else:
        txt += " em um único vértice, o último ponto da região tocado pela curva de nível no sentido de melhoria."
    if unbounded_region:
        txt += " A região viável é ilimitada, mas Z é limitado no sentido de otimização."
    return txt
