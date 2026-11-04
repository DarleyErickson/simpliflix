"""
Rotinas matriciais exatas (Gauss-Jordan com Fraction).

Usadas no Método Algébrico (resolução de sistemas B·x_B = b para cada base candidata)
e em conferências. Para operações em ponto flutuante (gráficos), usa-se NumPy.
"""
from __future__ import annotations

from fractions import Fraction
from typing import List, Optional

Matrix = List[List[Fraction]]


def solve_exact(A: Matrix, b: List[Fraction]) -> Optional[List[Fraction]]:
    """Resolve A·x = b (A quadrada) por Gauss-Jordan exato. Retorna None se singular."""
    n = len(A)
    M = [list(row) + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        piv = None
        for r in range(col, n):
            if M[r][col] != 0:
                piv = r
                break
        if piv is None:
            return None
        M[col], M[piv] = M[piv], M[col]
        p = M[col][col]
        M[col] = [v / p for v in M[col]]
        for r in range(n):
            if r != col and M[r][col] != 0:
                f = M[r][col]
                M[r] = [a - f * c for a, c in zip(M[r], M[col])]
    return [M[i][n] for i in range(n)]


def rank_exact(A: Matrix) -> int:
    """Posto de uma matriz (eliminação exata)."""
    if not A:
        return 0
    M = [list(r) for r in A]
    rows, cols = len(M), len(M[0])
    rank = 0
    for col in range(cols):
        piv = None
        for r in range(rank, rows):
            if M[r][col] != 0:
                piv = r
                break
        if piv is None:
            continue
        M[rank], M[piv] = M[piv], M[rank]
        for r in range(rows):
            if r != rank and M[r][col] != 0:
                f = M[r][col] / M[rank][col]
                M[r] = [a - f * c for a, c in zip(M[r], M[rank])]
        rank += 1
        if rank == rows:
            break
    return rank


def transpose(A: Matrix) -> Matrix:
    if not A:
        return []
    return [list(col) for col in zip(*A)]
