"""The authored register: what the team has decided about specific models.

``hunter.yml`` says what correct looks like. This file says what the team has
decided about individual models: that one is temporary on purpose, that an
off-plan build is approved, who owns what, and what the grain is in plain words.
Two files because they have different owners and change at different rates.

Where a reason is required, and where it is not:

* Declaring metadata (owner, grain, status, business name) needs no reason. It
  is information, not an exception.
* Overriding Hunter's persistence inference needs a reason, because it silences
  a signal Hunter computed.
* Approving anything needs a reason and a named approver.
* Silencing a rule needs a reason and an expiry date. Section 7.1.

The register can only ever change how a finding is classified or reported. It
cannot delete one silently: an approved exception still appears on the site,
with its reason and its review date, so the approval is visible.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from hunter.config.schema import IgnoreRule
from hunter.enums import BuildStatus, EntityKind, Persistence, Severity

MIN_REASON_LENGTH = 10

PLACEHOLDER_REASONS = frozenset(
    {"", "tbd", "todo", "fixme", "n/a", "na", "none", "reason", "-", "?", "xxx"}
)


def _is_placeholder(reason: str | None) -> bool:
    if reason is None:
        return True
    cleaned = reason.strip().lower().rstrip(".")
    return cleaned in PLACEHOLDER_REASONS or len(cleaned) < MIN_REASON_LENGTH


class RegisterModel(BaseModel):
    """What the team has recorded about one model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Declared intent that overrides inference. Three values a person can give:
    # temporary (a working step), verified (meant to stay, and somebody has
    # checked that it should) and persistent (meant to stay). ``verified`` is
    # a confirmation, so it carries the name of whoever confirmed it.
    persistence: Persistence | None = None
    verified_by: str | None = None
    verified_on: dt.date | None = None
    status: BuildStatus | None = None

    # Metadata DBML cannot express. Section 7.2.
    owner: str | None = None
    entity_type: EntityKind | None = None
    grain: str | None = Field(default=None, description="Grain in plain English")
    source_of_truth: str | None = None
    scd_type: int | None = Field(default=None, ge=0, le=7)
    business_name: str | None = None
    domain: str | None = None
    implements: str | None = Field(
        default=None,
        description="DBML table this model implements, where the names differ",
    )

    # Approval
    approved: bool = False
    approved_by: str | None = None
    approved_on: dt.date | None = None
    reason: str | None = None
    review_by: dt.date | None = None

    @field_validator("grain", "owner", "business_name", "domain", "source_of_truth")
    @classmethod
    def _no_blank_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def _reasons_where_required(self) -> RegisterModel:
        if self.approved:
            if _is_placeholder(self.reason):
                raise ValueError(
                    f"an approval needs a real reason, at least {MIN_REASON_LENGTH} characters"
                )
            if not (self.approved_by and self.approved_by.strip()):
                raise ValueError("an approval needs approved_by")
        if self.persistence is not None and _is_placeholder(self.reason):
            raise ValueError(
                "declaring persistence overrides what Hunter infers, so it needs a reason"
            )
        if self.persistence is Persistence.UNKNOWN:
            raise ValueError(
                "persistence must be temporary, verified or permanent; "
                "leave it out to let Hunter infer it"
            )
        if self.persistence is Persistence.VERIFIED and not (
            self.verified_by and self.verified_by.strip()
        ):
            raise ValueError("marking a table verified is a confirmation, so it needs verified_by")
        if self.verified_by and self.persistence is not Persistence.VERIFIED:
            raise ValueError("verified_by only means something with persistence: verified")
        return self

    @property
    def is_review_overdue(self) -> bool:
        return self.review_by is not None and dt.date.today() > self.review_by

    def review_overdue_on(self, as_of: dt.date) -> bool:
        return self.review_by is not None and as_of > self.review_by


class OffPlanApproval(BaseModel):
    """A model built ahead of the design, with that accepted and recorded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str
    reason: str
    approved_by: str
    approved_on: dt.date | None = None
    review_by: dt.date | None = None

    @field_validator("reason")
    @classmethod
    def _reason_is_real(cls, value: str) -> str:
        if _is_placeholder(value):
            raise ValueError(
                f"an off-plan approval needs a real reason, at least {MIN_REASON_LENGTH} characters"
            )
        return value.strip()

    @field_validator("approved_by")
    @classmethod
    def _approver_named(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("an off-plan approval needs a named approver")
        return cleaned

    def review_overdue_on(self, as_of: dt.date) -> bool:
        return self.review_by is not None and as_of > self.review_by


class ConceptualEntityDeclaration(BaseModel):
    """A business entity, declared here when there is no authored diagram."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    business_name: str | None = None
    domain: str | None = None
    implements: str | None = None
    note: str | None = None

    @property
    def label(self) -> str:
        return self.business_name or self.name.replace("_", " ")


class Register(BaseModel):
    """The whole register file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    version: int = 1
    models: dict[str, RegisterModel] = Field(default_factory=dict)
    off_plan_approved: list[OffPlanApproval] = Field(default_factory=list)
    ignores: list[IgnoreRule] = Field(default_factory=list)
    conceptual: list[ConceptualEntityDeclaration] = Field(default_factory=list)

    @field_validator("models", mode="before")
    @classmethod
    def _null_models_is_empty(cls, value: object) -> object:
        """A section somebody emptied by deleting its entries reads as null."""
        return {} if value is None else value

    @field_validator("off_plan_approved", "ignores", "conceptual", mode="before")
    @classmethod
    def _null_list_is_empty(cls, value: object) -> object:
        return [] if value is None else value

    @model_validator(mode="after")
    def _no_duplicate_approvals(self) -> Register:
        seen: set[str] = set()
        for approval in self.off_plan_approved:
            if approval.model in seen:
                raise ValueError(f"{approval.model} approved off-plan more than once")
            seen.add(approval.model)
        return self

    # ---- lookups ----

    def entry(self, model_name: str) -> RegisterModel | None:
        return self.models.get(model_name)

    def approval(self, model_name: str) -> OffPlanApproval | None:
        for approval in self.off_plan_approved:
            if approval.model == model_name:
                return approval
        return None

    def is_off_plan_approved(self, model_name: str) -> bool:
        return self.approval(model_name) is not None

    def declared_persistence(self, model_name: str) -> Persistence | None:
        entry = self.entry(model_name)
        return entry.persistence if entry else None

    def implements_map(self) -> dict[str, str]:
        """Model name to the DBML table it implements, where names differ."""
        out = {name: entry.implements for name, entry in self.models.items() if entry.implements}
        for declaration in self.conceptual:
            if declaration.implements:
                out.setdefault(declaration.implements, declaration.name)
        return {k: v for k, v in out.items() if v}

    def ignore_for(self, rule_id: str, model_name: str, as_of: dt.date) -> IgnoreRule | None:
        """The live ignore covering this rule and model, if any.

        An expired ignore does not cover anything. FR8.5.
        """
        for ignore in self.ignores:
            if ignore.covers(rule_id, model_name) and not ignore.is_expired(as_of):
                return ignore
        return None


@dataclass(frozen=True)
class RegisterIssue:
    """A problem with the register itself.

    Returned as plain data rather than a ``Finding`` so this module stays
    independent of the internal model. ``checks.alignment`` turns these into
    findings.
    """

    rule: str
    severity: Severity
    subject: str
    summary: str
    consequence: str
    evidence: dict[str, Any]


EMPTY_REGISTER = Register()


class RegisterError(Exception):
    """The register file could not be read or is not valid."""


def load_register(path: Path) -> Register:
    """Read the register. A missing file is an empty register, not an error.

    Most repositories will not have one on the first run, and Hunter must still
    produce a score.
    """
    if not path.exists():
        return EMPTY_REGISTER

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RegisterError(f"could not read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise RegisterError(f"{path} is not valid YAML: {exc}") from exc

    if raw is None:
        return EMPTY_REGISTER
    if not isinstance(raw, dict):
        raise RegisterError(f"{path} must contain a mapping at the top level")

    try:
        return Register.model_validate(raw)
    except Exception as exc:
        raise RegisterError(f"{path} is not a valid register: {exc}") from exc


def validate_register(
    register: Register,
    *,
    known_models: set[str],
    known_rules: set[str],
    as_of: dt.date | None = None,
) -> list[RegisterIssue]:
    """Check the register against reality, and report what has gone stale.

    A register nobody prunes stops being a record of decisions and becomes a
    place debt hides. These are the findings that keep it honest.
    """
    today = as_of or dt.date.today()
    issues: list[RegisterIssue] = []

    for name, entry in sorted(register.models.items()):
        if known_models and name not in known_models:
            issues.append(
                RegisterIssue(
                    rule="register.entry_matches_no_model",
                    severity=Severity.LOW,
                    subject=name,
                    summary=f"The register has an entry for {name}, which no longer exists.",
                    consequence=(
                        "This decision no longer applies to anything. It should be "
                        "removed so the register reflects the repository."
                    ),
                    evidence={"model": name},
                )
            )
        if entry.review_overdue_on(today):
            issues.append(
                RegisterIssue(
                    rule="register.review_overdue",
                    severity=Severity.MEDIUM,
                    subject=name,
                    summary=(
                        f"The decision recorded for {name} was due for review on {entry.review_by}."
                    ),
                    consequence=(
                        "The exception is still in force but nobody has re-checked it. "
                        "Either confirm it or remove it."
                    ),
                    evidence={"model": name, "review_by": str(entry.review_by)},
                )
            )

    for approval in sorted(register.off_plan_approved, key=lambda a: a.model):
        if known_models and approval.model not in known_models:
            issues.append(
                RegisterIssue(
                    rule="register.approval_matches_no_model",
                    severity=Severity.LOW,
                    subject=approval.model,
                    summary=(
                        f"{approval.model} is approved as an off-plan build, but no such "
                        "model exists."
                    ),
                    consequence="The approval covers nothing and should be removed.",
                    evidence={"model": approval.model},
                )
            )
        if approval.review_overdue_on(today):
            issues.append(
                RegisterIssue(
                    rule="register.approval_review_overdue",
                    severity=Severity.MEDIUM,
                    subject=approval.model,
                    summary=(
                        f"{approval.model} was approved off-plan pending review by "
                        f"{approval.review_by}, which has passed."
                    ),
                    consequence=(
                        "It was accepted as a temporary exception. Either add it to the "
                        "design or agree a new date."
                    ),
                    evidence={
                        "model": approval.model,
                        "review_by": str(approval.review_by),
                        "approved_by": approval.approved_by,
                    },
                )
            )

    for ignore in sorted(register.ignores, key=lambda i: (i.rule, i.expires)):
        if known_rules and ignore.rule not in known_rules and "*" not in ignore.rule:
            issues.append(
                RegisterIssue(
                    rule="register.ignore_names_unknown_rule",
                    severity=Severity.LOW,
                    subject=ignore.rule,
                    summary=f"An ignore names {ignore.rule}, which is not a rule Hunter has.",
                    consequence=(
                        "It silences nothing. Most likely the rule was renamed or the "
                        "name is misspelt."
                    ),
                    evidence={"rule": ignore.rule},
                )
            )
        if ignore.is_expired(today):
            issues.append(
                RegisterIssue(
                    rule="register.ignore_expired",
                    severity=Severity.MEDIUM,
                    subject=ignore.rule,
                    summary=(f"The exception for {ignore.rule} expired on {ignore.expires}."),
                    consequence=(
                        "The rule is now being applied again, so any findings it was "
                        "hiding are counted from today."
                    ),
                    evidence={
                        "rule": ignore.rule,
                        "expires": str(ignore.expires),
                        "models": ignore.models,
                        "reason": ignore.reason,
                    },
                )
            )

    return issues
