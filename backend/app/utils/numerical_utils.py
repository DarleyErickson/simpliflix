"""
Utilitários numéricos do SimpliFlix.

O núcleo do Simplex trabalha com aritmética racional EXATA (``fractions.Fraction``).
Isso elimina decisões baseadas em pequenas diferenças de ponto flutuante: um custo
reduzido é zero quando é exatamente zero, uma razão empata quando é exatamente igual,
e a degenerescência/multiplicidade de soluções é detectada sem tolerâncias arbitrárias.

As entradas do usuário (números JSON) são convertidas pela sua representação decimal
mais curta (``repr(float)``), de modo que 0.1 vira exatamente 1/10.

Também é definido ``MValue``: um número da forma ``c + m·M`` usado no Método do Grande M,
onde M é tratado simbolicamente (M → +∞), sem recorrer a um valor numérico enorme.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable, Union

ZERO = Fraction(0)
ONE = Fraction(1)

Number = Union[int, float, str, Fraction]


def to_frac(value: Number) -> Fraction:
    """Converte um valor numérico em Fraction exata."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise ValueError("valor booleano não é numérico")
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("valor não finito")
        return Fraction(repr(value))
    if isinstance(value, str):
        txt = value.strip().replace(",", ".")
        return Fraction(txt)
    raise ValueError(f"tipo numérico não suportado: {type(value)!r}")


def fmt(value: Fraction) -> str:
    """Representação textual exata: inteiro ("5") ou fração irredutível ("5/2")."""
    value = to_frac(value)
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def fmt_dec(value: Fraction, places: int = 4) -> str:
    """Representação decimal arredondada (apenas para exibição)."""
    f = float(value)
    txt = f"{f:.{places}f}".rstrip("0").rstrip(".")
    if txt in ("-0", ""):
        txt = "0"
    return txt


def num_json(value: Fraction) -> dict:
    """Número para a API: valor float + texto exato + texto decimal."""
    return {"value": float(value), "exact": fmt(value), "decimal": fmt_dec(value)}


def is_integer(value: Fraction) -> bool:
    return to_frac(value).denominator == 1


def floor_frac(value: Fraction) -> int:
    return math.floor(value)


def ceil_frac(value: Fraction) -> int:
    return math.ceil(value)


def sign(value: Fraction) -> int:
    return (value > 0) - (value < 0)


@dataclass(frozen=True)
class MValue:
    """Número simbólico c + m·M (M arbitrariamente grande).

    A comparação é lexicográfica: primeiro o coeficiente de M, depois a constante.
    Para problemas sem Grande M, ``m`` é sempre zero e MValue se comporta como Fraction.
    """

    c: Fraction = ZERO
    m: Fraction = ZERO

    @staticmethod
    def of(x: Union["MValue", Number]) -> "MValue":
        if isinstance(x, MValue):
            return x
        return MValue(to_frac(x), ZERO)

    def __add__(self, other):
        o = MValue.of(other)
        return MValue(self.c + o.c, self.m + o.m)

    __radd__ = __add__

    def __sub__(self, other):
        o = MValue.of(other)
        return MValue(self.c - o.c, self.m - o.m)

    def __rsub__(self, other):
        return MValue.of(other) - self

    def __neg__(self):
        return MValue(-self.c, -self.m)

    def scale(self, k: Fraction) -> "MValue":
        return MValue(self.c * k, self.m * k)

    def sign(self) -> int:
        if self.m != 0:
            return sign(self.m)
        return sign(self.c)

    def is_zero(self) -> bool:
        return self.c == 0 and self.m == 0

    def key(self):
        """Chave de ordenação lexicográfica (M domina)."""
        return (self.m, self.c)

    def to_json(self):
        if self.m == 0:
            return fmt(self.c)
        return {"c": fmt(self.c), "m": fmt(self.m)}

    def text(self) -> str:
        if self.m == 0:
            return fmt(self.c)
        parts = []
        if self.c != 0:
            parts.append(fmt(self.c))
        mcoef = self.m
        if mcoef == 1:
            mt = "M"
        elif mcoef == -1:
            mt = "−M"
        else:
            mt = f"{fmt(mcoef)}M".replace("-", "−")
        if parts:
            if mcoef < 0:
                parts.append("− " + (mt[1:] if mt.startswith("−") else fmt(-mcoef) + "M"))
            else:
                parts.append("+ " + mt)
            return " ".join(parts)
        return mt


def msum(values: Iterable[MValue]) -> MValue:
    total = MValue()
    for v in values:
        total = total + v
    return total


def linear_text(coeffs, names, zero_terms: bool = False) -> str:
    """Formata uma expressão linear: [3, -1, 0], [X1, X2, X3] -> '3X1 − X2'."""
    terms = []
    for coef, name in zip(coeffs, names):
        coef = MValue.of(coef)
        if coef.is_zero() and not zero_terms:
            continue
        if coef.m != 0:
            body = f"({coef.text()}){name}"
            neg = False
        else:
            c = coef.c
            neg = c < 0
            a = -c if neg else c
            body = (name if a == 1 else f"{fmt(a)}{name}")
            if a == 0:
                body = f"0{name}"
        if not terms:
            terms.append(("−" if neg else "") + body)
        else:
            terms.append(("− " if neg else "+ ") + body)
    return " ".join(terms) if terms else "0"


OP_SYMBOL = {"<=": "≤", ">=": "≥", "=": "="}
FLIP_OP = {"<=": ">=", ">=": "<=", "=": "="}
