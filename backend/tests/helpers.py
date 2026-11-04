from fractions import Fraction as F

from app.algorithms.lp_model import LPModel


def mk(sense, c, A, ops, b, signs=None, domains=None):
    n = len(c)
    return LPModel(
        sense, [F(v) for v in c], [[F(v) for v in r] for r in A], list(ops), [F(v) for v in b],
        [f"X{j + 1}" for j in range(n)], domains or ["continuous"] * n, signs or ["nonneg"] * n,
    )


def sol(res):
    return [F(v["exact"]) for v in res["solution"]]


def z(res):
    return F(res["objective_value"]["exact"])
