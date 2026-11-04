"""
Representação interna (exata) de um Problema de Programação Linear.

    otimizar   Z = c·x
    sujeito a  A_i·x  (≤ | ≥ | =)  b_i      i = 1..m
               x_j ≥ 0 | x_j ≤ 0 | x_j livre

Os limites diferentes de zero informados pelo usuário (ex.: X1 ≥ 2, X2 ≤ 10) são
convertidos em restrições explícitas pelo ``model_service``; aqui as variáveis possuem
apenas uma condição de sinal.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import List

from app.utils.numerical_utils import OP_SYMBOL, fmt, linear_text

SIGN_TEXT = {"nonneg": "≥ 0", "nonpos": "≤ 0", "free": "livre"}


@dataclass
class LPModel:
    sense: str                      # "max" | "min"
    c: List[Fraction]
    A: List[List[Fraction]]
    ops: List[str]                  # "<=" | ">=" | "="
    b: List[Fraction]
    var_names: List[str]
    var_domains: List[str]          # "continuous" | "integer"
    var_signs: List[str]            # "nonneg" | "nonpos" | "free"
    con_names: List[str] = field(default_factory=list)
    con_origin: List[str] = field(default_factory=list)   # "user" | "bound" | "branch"
    name: str = "Problema"

    def __post_init__(self):
        if not self.con_names:
            self.con_names = [f"R{i + 1}" for i in range(len(self.A))]
        if not self.con_origin:
            self.con_origin = ["user"] * len(self.A)

    @property
    def n(self) -> int:
        return len(self.c)

    @property
    def m(self) -> int:
        return len(self.A)

    def copy(self) -> "LPModel":
        return replace(
            self,
            c=list(self.c),
            A=[list(r) for r in self.A],
            ops=list(self.ops),
            b=list(self.b),
            var_names=list(self.var_names),
            var_domains=list(self.var_domains),
            var_signs=list(self.var_signs),
            con_names=list(self.con_names),
            con_origin=list(self.con_origin),
        )

    def add_constraint(self, coeffs, op, rhs, name=None, origin="user") -> "LPModel":
        new = self.copy()
        new.A.append(list(coeffs))
        new.ops.append(op)
        new.b.append(rhs)
        new.con_names.append(name or f"R{new.m}")
        new.con_origin.append(origin)
        return new

    # ----------------------------------------------------------- avaliação
    def objective_at(self, x: List[Fraction]) -> Fraction:
        return sum((ci * xi for ci, xi in zip(self.c, x)), Fraction(0))

    def lhs_at(self, i: int, x: List[Fraction]) -> Fraction:
        return sum((a * xi for a, xi in zip(self.A[i], x)), Fraction(0))

    def constraint_ok(self, i: int, x: List[Fraction]) -> bool:
        lhs = self.lhs_at(i, x)
        op = self.ops[i]
        if op == "<=":
            return lhs <= self.b[i]
        if op == ">=":
            return lhs >= self.b[i]
        return lhs == self.b[i]

    def sign_ok(self, j: int, v: Fraction) -> bool:
        s = self.var_signs[j]
        if s == "nonneg":
            return v >= 0
        if s == "nonpos":
            return v <= 0
        return True

    def is_feasible(self, x: List[Fraction]) -> bool:
        return all(self.constraint_ok(i, x) for i in range(self.m)) and all(
            self.sign_ok(j, x[j]) for j in range(self.n)
        )

    def better(self, a: Fraction, b: Fraction) -> bool:
        """a é estritamente melhor que b no sentido do problema."""
        return a > b if self.sense == "max" else a < b

    # ----------------------------------------------------------- textos
    def objective_text(self) -> str:
        return f"{self.sense.upper()} Z = {linear_text(self.c, self.var_names)}"

    def constraint_text(self, i: int) -> str:
        return f"{linear_text(self.A[i], self.var_names)} {OP_SYMBOL[self.ops[i]]} {fmt(self.b[i])}"

    def sign_texts(self) -> List[str]:
        groups = {}
        for name, s in zip(self.var_names, self.var_signs):
            groups.setdefault(s, []).append(name)
        out = []
        for s in ("nonneg", "nonpos", "free"):
            if s in groups:
                out.append(f"{', '.join(groups[s])} {SIGN_TEXT[s]}")
        return out

    def integer_text(self) -> str:
        ints = [n for n, d in zip(self.var_names, self.var_domains) if d == "integer"]
        return f"{', '.join(ints)} inteiras" if ints else ""

    def formulation(self) -> dict:
        return {
            "objective": self.objective_text(),
            "constraints": [
                {"name": self.con_names[i], "text": self.constraint_text(i), "origin": self.con_origin[i]}
                for i in range(self.m)
            ],
            "signs": self.sign_texts(),
            "integrality": self.integer_text(),
        }

    def to_dict(self) -> dict:
        """Serializa no mesmo formato JSON aceito pela API."""
        def num(v: Fraction):
            return int(v) if v.denominator == 1 else float(v)

        lb = {"nonneg": 0, "nonpos": None, "free": None}
        ub = {"nonneg": None, "nonpos": 0, "free": None}
        return {
            "name": self.name,
            "objective": {"type": self.sense, "coefficients": [num(v) for v in self.c]},
            "variables": [
                {"name": n, "domain": d, "sign": s, "lower_bound": lb[s], "upper_bound": ub[s]}
                for n, d, s in zip(self.var_names, self.var_domains, self.var_signs)
            ],
            "constraints": [
                {"name": self.con_names[i], "coefficients": [num(v) for v in self.A[i]],
                 "operator": self.ops[i], "rhs": num(self.b[i])}
                for i in range(self.m)
            ],
        }
