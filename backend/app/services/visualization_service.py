"""
Preparação dos dados gráficos: combina o resultado do método gráfico com as soluções
contínua, arredondada e inteira, para que o front-end desenhe tudo no mesmo gráfico.
"""
from __future__ import annotations

from typing import Optional


def overlay_solutions(graph: dict, simplex: Optional[dict], integer: Optional[dict]) -> dict:
    if not graph or not graph.get("available"):
        return graph
    markers = []
    if simplex and simplex.get("solution"):
        s = simplex["solution"]
        markers.append({"type": "continuous", "label": "Ótimo contínuo (Simplex)",
                        "x": s[0]["value"], "y": s[1]["value"], "text": f"({s[0]['exact']}, {s[1]['exact']})",
                        "z": simplex["objective_value"]["exact"]})
    if integer:
        r = integer.get("rounding") or {}
        if r.get("available"):
            rv = r["rounded"]
            markers.append({"type": "rounded", "label": "Arredondamento" + (" (viável)" if r["feasible"] else
                                                                           " (inviável)"),
                            "x": rv[0]["value"], "y": rv[1]["value"], "text": f"({rv[0]['exact']}, {rv[1]['exact']})",
                            "z": r["objective"]["exact"], "feasible": r["feasible"]})
            adj = r.get("adjusted")
            if adj and adj.get("found"):
                av = adj["solution"]
                markers.append({"type": "adjusted", "label": "Arredondamento ajustado",
                                "x": av[0]["value"], "y": av[1]["value"], "text": f"({av[0]['exact']}, {av[1]['exact']})",
                                "z": adj["objective"]["exact"]})
        bb = integer.get("branch_and_bound") or {}
        if bb.get("solution"):
            iv = bb["solution"]
            markers.append({"type": "integer", "label": "Ótimo inteiro (B&B)" if bb.get("proven_optimal")
                            else "Melhor inteira encontrada",
                            "x": iv[0]["value"], "y": iv[1]["value"], "text": f"({iv[0]['exact']}, {iv[1]['exact']})",
                            "z": bb["objective_value"]["exact"]})
    graph = dict(graph)
    graph["markers"] = markers
    return graph
