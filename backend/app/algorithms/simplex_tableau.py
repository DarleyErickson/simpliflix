"""
Tabela (tableau) do Método Simplex.

Convenção adotada (forma tabular clássica, "Cj − Zj"):

    Cj      : coeficiente de custo de cada coluna na função objetivo da fase corrente
    CB      : custos das variáveis básicas (coluna à esquerda)
    Zj      : Σ_i CB_i · a_ij    (custo de oportunidade de introduzir 1 unidade de j)
    Cj − Zj : custo reduzido (ganho líquido por unidade de j que entrar na base)
    Z       : Σ_i CB_i · b_i     (valor da função objetivo na solução básica atual)

Critério de otimalidade:
    MAX → ótimo quando todo Cj − Zj ≤ 0   (entra o maior Cj − Zj positivo)
    MIN → ótimo quando todo Cj − Zj ≥ 0   (entra o menor Cj − Zj negativo)

Todos os valores são Fractions (exatos). Os custos são ``MValue`` para permitir o
Método do Grande M de forma simbólica.
"""
from __future__ import annotations

from fractions import Fraction
from typing import List, Optional, Set

from app.utils.numerical_utils import ZERO, MValue, fmt, msum


class Tableau:
    def __init__(
        self,
        names: List[str],
        kinds: List[str],
        rows: List[List[Fraction]],
        rhs: List[Fraction],
        basis: List[int],
        costs: List[MValue],
        sense: str,
        row_origin: Optional[List[int]] = None,
        hidden: Optional[Set[int]] = None,
    ):
        self.names = names            # nome de cada coluna (variável da forma padrão)
        self.kinds = kinds            # decision | slack | surplus | artificial
        self.rows = rows              # matriz m × N
        self.rhs = rhs                # coluna b
        self.basis = basis            # índice da variável básica de cada linha
        self.costs = costs            # Cj (MValue)
        self.sense = sense            # "max" | "min"
        self.row_origin = row_origin if row_origin is not None else list(range(len(rows)))
        self.hidden = hidden if hidden is not None else set()   # colunas ocultas (artificiais na Fase 2)

    # ------------------------------------------------------------------ básicos
    @property
    def m(self) -> int:
        return len(self.rows)

    @property
    def N(self) -> int:
        return len(self.names)

    def copy(self) -> "Tableau":
        return Tableau(
            list(self.names), list(self.kinds), [list(r) for r in self.rows], list(self.rhs),
            list(self.basis), list(self.costs), self.sense, list(self.row_origin), set(self.hidden),
        )

    def visible(self) -> List[int]:
        return [j for j in range(self.N) if j not in self.hidden]

    def cb(self) -> List[MValue]:
        return [self.costs[b] for b in self.basis]

    def zj(self) -> List[MValue]:
        cb = self.cb()
        return [msum(cb[i].scale(self.rows[i][j]) for i in range(self.m)) for j in range(self.N)]

    def z(self) -> MValue:
        cb = self.cb()
        return msum(cb[i].scale(self.rhs[i]) for i in range(self.m))

    def reduced(self) -> List[MValue]:
        zj = self.zj()
        return [self.costs[j] - zj[j] for j in range(self.N)]

    def improving(self, r: MValue) -> bool:
        """O custo reduzido r indica melhoria da função objetivo?"""
        s = r.sign()
        return s > 0 if self.sense == "max" else s < 0

    def values(self) -> List[Fraction]:
        """Valor de cada variável da forma padrão na solução básica atual."""
        v = [ZERO] * self.N
        for i, bj in enumerate(self.basis):
            v[bj] = self.rhs[i]
        return v

    def is_degenerate(self) -> bool:
        return any(v == 0 for v in self.rhs)

    # ------------------------------------------------------------------ pivô
    def pivot(self, r: int, k: int) -> List[dict]:
        """Pivoteia no elemento (r, k). Retorna a descrição das operações elementares."""
        ops = []
        p = self.rows[r][k]
        if p == 0:
            raise ZeroDivisionError("Elemento pivô nulo")
        lr = f"L{r + 1}"
        if p != 1:
            self.rows[r] = [v / p for v in self.rows[r]]
            self.rhs[r] = self.rhs[r] / p
            ops.append({"row": r, "text": f"{lr} ← {lr} ÷ {_paren(p)}", "factor": fmt(p), "type": "scale"})
        else:
            ops.append({"row": r, "text": f"{lr} ← {lr} (pivô já é 1)", "factor": "1", "type": "scale"})
        for i in range(self.m):
            if i == r:
                continue
            f = self.rows[i][k]
            if f == 0:
                continue
            self.rows[i] = [a - f * c for a, c in zip(self.rows[i], self.rows[r])]
            self.rhs[i] = self.rhs[i] - f * self.rhs[r]
            li = f"L{i + 1}"
            if f > 0:
                txt = f"{li} ← {li} − {_coef(f)}{lr}"
            else:
                txt = f"{li} ← {li} + {_coef(-f)}{lr}"
            ops.append({"row": i, "text": txt, "factor": fmt(f), "type": "eliminate"})
        self.basis[r] = k
        return ops

    def delete_row(self, r: int):
        del self.rows[r]
        del self.rhs[r]
        del self.basis[r]
        del self.row_origin[r]

    # ------------------------------------------------------------------ exportação
    def snapshot(self) -> dict:
        vis = self.visible()
        zj = self.zj()
        red = self.reduced()
        return {
            "columns": [self.names[j] for j in vis],
            "kinds": [self.kinds[j] for j in vis],
            "cj": [self.costs[j].to_json() for j in vis],
            "basis": [self.names[b] for b in self.basis],
            "basis_cols": [vis.index(b) if b in vis else None for b in self.basis],
            "cb": [c.to_json() for c in self.cb()],
            "rows": [[fmt(self.rows[i][j]) for j in vis] for i in range(self.m)],
            "rhs": [fmt(v) for v in self.rhs],
            "zj": [zj[j].to_json() for j in vis],
            "reduced": [red[j].to_json() for j in vis],
            "z": self.z().to_json(),
            "sense": self.sense,
            "uses_m": any(c.m != 0 for c in self.costs),
        }

    def col_pos(self, j: int) -> int:
        """Posição de uma coluna real dentro das colunas visíveis."""
        return self.visible().index(j)


def _paren(v: Fraction) -> str:
    t = fmt(v)
    return f"({t})" if (v < 0 or "/" in t) else t


def _coef(v: Fraction) -> str:
    """Coeficiente multiplicativo para textos de operações elementares (omite 1)."""
    if v == 1:
        return ""
    t = fmt(v)
    return (f"({t})" if "/" in t else t) + "·"
