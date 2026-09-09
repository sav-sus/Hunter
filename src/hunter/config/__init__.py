"""Configuration: the ruleset, the register, and how they resolve."""

from __future__ import annotations

from hunter.config.loader import (
    ConfigError,
    Divergence,
    ResolvedConfig,
    house_path,
    read_yaml,
    resolve,
)
from hunter.config.register import (
    OffPlanApproval,
    Register,
    RegisterError,
    RegisterIssue,
    RegisterModel,
    load_register,
    validate_register,
)
from hunter.config.schema import (
    DEFAULT_WEIGHTS,
    EntitySpec,
    HunterConfig,
    IgnoreRule,
    LayerSpec,
    RuleSetting,
    ScoringSpec,
)

__all__ = [
    "DEFAULT_WEIGHTS",
    "ConfigError",
    "Divergence",
    "EntitySpec",
    "HunterConfig",
    "IgnoreRule",
    "LayerSpec",
    "OffPlanApproval",
    "Register",
    "RegisterError",
    "RegisterIssue",
    "RegisterModel",
    "ResolvedConfig",
    "RuleSetting",
    "ScoringSpec",
    "house_path",
    "load_register",
    "read_yaml",
    "resolve",
    "validate_register",
]
