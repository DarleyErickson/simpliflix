"""Esquemas de entrada da API (Pydantic). A validação semântica fica em validation_service."""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ObjectiveIn(BaseModel):
    type: Any = "max"
    coefficients: List[Any] = Field(default_factory=list)


class VariableIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    domain: Any = "continuous"
    sign: Optional[str] = None
    lower_bound: Any = 0
    upper_bound: Any = None


class ConstraintIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    coefficients: List[Any] = Field(default_factory=list)
    operator: Any = None
    rhs: Any = None


class OptionsIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    methods: List[str] = Field(default_factory=lambda: ["simplex"])
    pivot_rule: str = "dantzig"
    max_iterations: int = 200
    max_nodes: int = 500
    include_integer: bool = True
    include_dual: bool = True


class ProblemIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: Optional[str] = None
    description: Optional[str] = None
    objective: ObjectiveIn
    variables: Optional[List[VariableIn]] = None
    constraints: List[ConstraintIn] = Field(default_factory=list)
    options: Optional[OptionsIn] = None
