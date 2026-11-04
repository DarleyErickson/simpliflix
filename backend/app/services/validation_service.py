"""
Validação semântica dos modelos recebidos pela API.

Todas as mensagens são em português e indicam ao usuário como corrigir o problema.
Nenhum erro interno do Python é exposto: ``ModelValidationError`` carrega apenas a lista
de problemas encontrados (campo + mensagem).
"""
from __future__ import annotations

import math
from fractions import Fraction
from typing import Any, List, Optional

from app.utils.numerical_utils import to_frac

MAX_VARIABLES = 20
MAX_CONSTRAINTS = 40
MAX_ABS_VALUE = Fraction(10) ** 12
VALID_OPS = {"<=": "<=", "≤": "<=", ">=": ">=", "≥": ">=", "=": "=", "==": "="}
VALID_SIGNS = {"nonneg", "nonpos", "free"}


class ModelValidationError(Exception):
    def __init__(self, errors: List[dict]):
        super().__init__("Modelo inválido")
        self.errors = errors


class Collector:
    def __init__(self):
        self.errors: List[dict] = []

    def add(self, field: str, message: str):
        self.errors.append({"field": field, "message": message})

    def number(self, value: Any, field: str, label: str, required: bool = True) -> Optional[Fraction]:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            if required:
                self.add(field, f"{label}: campo obrigatório vazio. Informe um número (use 0 se não houver).")
            return None
        if isinstance(value, bool):
            self.add(field, f"{label}: valor inválido. Informe um número.")
            return None
        if isinstance(value, float) and not math.isfinite(value):
            self.add(field, f"{label}: o valor deve ser um número finito.")
            return None
        try:
            f = to_frac(value)
        except (ValueError, ZeroDivisionError, TypeError):
            self.add(field, f"{label}: \"{value}\" não é um número válido. Use ponto ou vírgula como separador "
                            f"decimal (ex.: 2.5).")
            return None
        if abs(f) > MAX_ABS_VALUE:
            self.add(field, f"{label}: valor muito grande (limite ±10¹²).")
            return None
        return f

    def raise_if_any(self):
        if self.errors:
            raise ModelValidationError(self.errors)


def normalize_op(op: Any) -> Optional[str]:
    if not isinstance(op, str):
        return None
    return VALID_OPS.get(op.strip())
