"""
Figura estática do método gráfico (Matplotlib), para relatório e slides.

O gráfico interativo do site é desenhado no navegador (Plotly). Esta rotina gera a
mesma informação em PNG (300 dpi), SVG ou PDF, a partir dos dados exatos calculados
por ``graphical_method.solve_graphical``. Nenhum cálculo de otimização é feito aqui.

Boas práticas seguidas:
* interface orientada a objetos (``Figure``/``Axes``), sem o estado global do pyplot,
  o que também evita acúmulo de figuras em memória no servidor;
* ``constrained_layout`` para legenda e rótulos não se sobreporem;
* paleta segura para daltônicos (Okabe-Ito) e um estilo de traço diferente por
  restrição, de modo que a leitura não dependa só da cor;
* fundo branco e 300 dpi para impressão.
"""
from __future__ import annotations

import io
from typing import Dict, List, Tuple

FORMATS: Dict[str, str] = {
    "png": "image/png",
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
}

# Okabe-Ito (sem o amarelo, que não tem contraste em fundo branco)
LINE_COLORS = ["#0072B2", "#CC79A7", "#009E73", "#56B4E9", "#7F3C8D", "#5F6B00", "#000000"]
LINE_STYLES = ["-", (0, (7, 3)), (0, (7, 3, 1.5, 3)), (0, (3, 2)), (0, (10, 3, 2, 3, 2, 3))]
C_OPT = "#C42B31"       # curva de nível ótima e seta de melhoria
C_LEVEL = "#8F5300"     # demais curvas de nível
C_REGION = "#6B7280"
C_OK = "#0D7F50"
C_BAD = "#C42B31"

MARKERS = {
    "continuous": dict(marker="*", s=330, color="#E69F00"),
    "rounded": dict(marker="D", s=85, color="#D55E00"),
    "adjusted": dict(marker="^", s=110, color="#56B4E9"),
    "integer": dict(marker="s", s=95, color=C_OK),
}


class FigureUnavailable(Exception):
    """Matplotlib não está instalado no ambiente."""


def _seg(segment) -> Tuple[List[float], List[float]]:
    return [segment[0][0], segment[1][0]], [segment[0][1], segment[1][1]]


def _inside(p, box, pad=0.0) -> bool:
    return box[0] - pad <= p[0] <= box[1] + pad and box[2] - pad <= p[1] <= box[3] + pad


def render_figure(graph: dict, fmt: str = "png", title: str = "") -> bytes:
    """Desenha o resultado de ``solve_graphical`` (já com ``markers``) e devolve o arquivo."""
    try:
        from matplotlib.figure import Figure
    except ImportError as exc:  # pragma: no cover - depende do ambiente
        raise FigureUnavailable() from exc

    box = graph["box"]
    xn, yn = graph["variables"]
    obj = graph["objective"]
    white_box = dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85)

    fig = Figure(figsize=(9, 7), layout="constrained", facecolor="white")
    ax = fig.add_subplot()

    # ---- região viável
    region = graph.get("region") or []
    if len(region) >= 3:
        ax.fill([p[0] for p in region], [p[1] for p in region], facecolor=C_REGION, alpha=0.22,
                edgecolor="none", zorder=1,
                label="Região viável" + (" (recortada)" if graph.get("region_unbounded") else ""))
    elif region:
        ax.plot([p[0] for p in region], [p[1] for p in region], color=C_REGION, lw=6, alpha=0.5,
                solid_capstyle="round", zorder=1, label="Região viável")

    # ---- restrições
    i = 0
    for ln in graph["lines"]:
        if ln["kind"] == "sign" or not ln.get("segment"):
            continue
        xs, ys = _seg(ln["segment"])
        ax.plot(xs, ys, color=LINE_COLORS[i % len(LINE_COLORS)], ls=LINE_STYLES[i % len(LINE_STYLES)],
                lw=2, zorder=3, label=f"{ln['name']}: {ln['label']}")
        i += 1

    # ---- curvas de nível, com o valor de Z escrito sobre cada uma
    first_level = True
    for lv in graph.get("levels") or []:
        xs, ys = _seg(lv["segment"])
        if lv["optimal"]:
            ax.plot(xs, ys, color=C_OPT, lw=2.4, zorder=4, label=f"Curva de nível ótima: Z* = {lv['z_text']}")
        else:
            ax.plot(xs, ys, color=C_LEVEL, lw=1.1, ls=(0, (4, 4)), zorder=2,
                    label="Curvas de nível de Z" if first_level else None)
            first_level = False
        # rótulo perto do início da reta; se cair colado na borda, vai para o meio ou é omitido
        mx, my = 0.08 * (box[1] - box[0]), 0.06 * (box[3] - box[2])
        for t in (0.12, 0.5):
            px, py = xs[0] + t * (xs[1] - xs[0]), ys[0] + t * (ys[1] - ys[0])
            if box[0] + mx <= px <= box[1] - mx and box[2] + my <= py <= box[3] - my:
                ax.text(px, py, ("Z* = " if lv["optimal"] else "Z = ") + lv["z_text"], fontsize=9,
                        color=C_OPT if lv["optimal"] else C_LEVEL, ha="center", va="center",
                        bbox=white_box, zorder=6, clip_on=True)
                break

    # ---- pontos inteiros viáveis
    lattice = graph.get("integer_points") or {}
    pts = lattice.get("points") or []
    if pts:
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=9, color="#374151", alpha=0.7, zorder=4,
                   label="Pontos inteiros viáveis" + (" (amostra)" if lattice.get("sampled") else ""))

    # ---- conjunto de soluções ótimas (segmento ou semirreta)
    opt_set = graph.get("optimal_set")
    if opt_set and opt_set["type"] == "segment":
        a, b = opt_set["points"]
        ax.plot([a[0], b[0]], [a[1], b[1]], color=C_OK, lw=6, alpha=0.75, solid_capstyle="round", zorder=5,
                label="Segmento de soluções ótimas")
    elif opt_set and opt_set["type"] == "ray":
        a, d = opt_set["points"][0], opt_set["direction"]
        far = 2 * ((box[1] - box[0]) ** 2 + (box[3] - box[2]) ** 2) ** 0.5
        ax.plot([a[0], a[0] + d[0] * far], [a[1], a[1] + d[1] * far], color=C_OK, lw=6, alpha=0.75, zorder=5,
                label="Semirreta de soluções ótimas")

    # ---- vértices, com as coordenadas exatas
    vertices = graph.get("vertices") or []
    if vertices:
        ax.scatter([v["x"] for v in vertices], [v["y"] for v in vertices], s=42, color="black",
                   edgecolor="white", linewidth=1.2, zorder=7, label="Vértices")
        if len(vertices) <= 12:
            for v in vertices:
                if not v["optimal"]:
                    ax.annotate(f"({v['x_text']}, {v['y_text']})", (v["x"], v["y"]), xytext=(6, 6),
                                textcoords="offset points", fontsize=9, color="#111827", bbox=white_box,
                                zorder=8, annotation_clip=True)

    # ---- soluções: contínua, arredondada, inteira
    markers = graph.get("markers") or []
    for mk in markers:
        st = dict(MARKERS.get(mk["type"], dict(marker="o", s=80, color=C_OPT)))
        if mk["type"] == "rounded" and not mk.get("feasible", True):
            st.update(marker="X", color=C_BAD)
        ax.scatter([mk["x"]], [mk["y"]], edgecolor="black", linewidth=0.9, zorder=9,
                   label=f"{mk['label']}: {mk['text']}, Z = {mk['z']}", **st)

    optimal = graph.get("optimal")
    if optimal:
        p = optimal["points"][0]
        if not any(m["type"] == "continuous" for m in markers):
            ax.scatter([p["x"]], [p["y"]], edgecolor="black", linewidth=0.9, zorder=9,
                       label="Ponto ótimo", **MARKERS["continuous"])
        # a anotação fica do lado oposto ao sentido de melhoria, para não cobrir a seta
        gx = graph["gradient"]["to"][0] - graph["gradient"]["from"][0]
        gy = graph["gradient"]["to"][1] - graph["gradient"]["from"][1]
        dx = -70 if gx >= 0 else 70
        dy = -44 if gy >= 0 else 44
        ax.annotate(f"Ótimo ({p['x_text']}, {p['y_text']})\nZ* = {optimal['z_text']}", (p["x"], p["y"]),
                    xytext=(dx, dy), textcoords="offset points", fontsize=10.5, fontweight="bold",
                    ha="center", va="center", zorder=10,
                    bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#111827", lw=0.8),
                    arrowprops=dict(arrowstyle="-", color="#111827", lw=0.8, shrinkB=9))

    # ---- sentido de melhoria de Z
    if graph.get("feasible"):
        g = graph["gradient"]
        ax.annotate("", xy=g["to"], xytext=g["from"], zorder=8,
                    arrowprops=dict(arrowstyle="-|>", color=C_OPT, lw=2.2, mutation_scale=18))
        if _inside(g["to"], box):
            ax.annotate("Z aumenta" if obj["sense"] == "max" else "Z diminui", g["to"], xytext=(7, 7),
                        textcoords="offset points", fontsize=9, color=C_OPT, bbox=white_box, zorder=8)

    # ---- eixos
    ax.set_xlim(box[0], box[1])
    ax.set_ylim(box[2], box[3])
    ax.axhline(0, color="black", lw=1, zorder=2)
    ax.axvline(0, color="black", lw=1, zorder=2)
    ax.grid(True, alpha=0.3, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xlabel(xn, fontsize=12)
    ax.set_ylabel(yn, fontsize=12)
    ax.tick_params(labelsize=10)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    status = {"optimal": "", "unbounded": "  (problema ilimitado)", "infeasible": "  (problema inviável)"}
    head = (title.strip() + "\n") if title and title.strip() else ""
    ax.set_title(f"{head}{obj['text']}{status.get(graph['status'], '')}", fontsize=13, fontweight="bold",
                 loc="left")
    if not graph.get("feasible"):
        ax.text(0.5, 0.5, "Região viável vazia:\nnenhum ponto satisfaz todas as restrições",
                transform=ax.transAxes, ha="center", va="center", fontsize=12, color=C_BAD, bbox=white_box)

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        fig.legend(handles, labels, loc="outside lower center", ncols=2, fontsize=9.5, frameon=False)

    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=300, facecolor="white",
                metadata={"Title": title or "SimpliFlix"} if fmt != "svg" else None)
    return buf.getvalue()
