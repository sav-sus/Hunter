"""Shared vocabulary.

This module imports nothing from the rest of Hunter, so every other module can
import it freely. Values are the strings that appear in ``hunter.yml``, in
``register.yml`` and in ``report.json``, so renaming one is a breaking change to
the report contract.
"""

from __future__ import annotations

from enum import StrEnum


class ConfigLevel(StrEnum):
    """Where a resolved configuration value came from.

    Ordered weakest to strongest. Section 7 of the requirements document.
    """

    DEFAULT = "default"
    HOUSE = "house"
    PROJECT = "project"
    REGISTER = "register"
    MODEL = "model"


CONFIG_PRECEDENCE: tuple[ConfigLevel, ...] = (
    ConfigLevel.DEFAULT,
    ConfigLevel.HOUSE,
    ConfigLevel.PROJECT,
    ConfigLevel.REGISTER,
    ConfigLevel.MODEL,
)


class Dimension(StrEnum):
    """Score dimensions. Weights live in the house ruleset, section 9."""

    TESTING = "testing"
    MODEL_CONFORMANCE = "model_conformance"
    LINEAGE_HEALTH = "lineage_health"
    DOCUMENTATION = "documentation"
    CROSS_LAYER_SYNC = "cross_layer_sync"
    CONVENTIONS_STRUCTURE = "conventions_structure"
    ENTITY_MODELLING = "entity_modelling"
    PERFORMANCE_COST = "performance_cost"


class Severity(StrEnum):
    """How much a finding matters. Only HIGH can fail a build in gate mode."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


SEVERITY_ORDER: dict[Severity, int] = {
    Severity.HIGH: 0,
    Severity.MEDIUM: 1,
    Severity.LOW: 2,
    Severity.INFO: 3,
}


class Persistence(StrEnum):
    """Whether a model is meant to last. FR1.2.

    Three answers a person can give, and one Hunter gives when it cannot tell.
    ``VERIFIED`` is ``PERSISTENT`` with a named person having confirmed it: the
    table is meant to stay and somebody has checked that it should. It can only
    come from the register, never from inference.
    """

    TEMPORARY = "temporary"
    VERIFIED = "verified"
    PERSISTENT = "persistent"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value: object) -> Persistence | None:
        """``permanent`` is the word people write; ``persistent`` is the stored value."""
        if isinstance(value, str) and value.strip().lower() == "permanent":
            return cls.PERSISTENT
        return None

    @property
    def is_lasting(self) -> bool:
        """Permanent or verified: a finished table, judged as one."""
        return self in {Persistence.PERSISTENT, Persistence.VERIFIED}

    @property
    def label(self) -> str:
        """The word a reader sees."""
        return {
            Persistence.TEMPORARY: "temporary",
            Persistence.VERIFIED: "verified",
            Persistence.PERSISTENT: "permanent",
            Persistence.UNKNOWN: "not determined",
        }[self]


class PersistenceSignal(StrEnum):
    """Which signal decided the persistence class. FR1.3.

    Listed in precedence order. The register beats everything, because a person
    stating intent outranks anything Hunter can infer.
    """

    REGISTER = "register_declaration"
    TABLE_EXPIRATION = "warehouse_table_expiration"
    EPHEMERAL = "materialized_ephemeral"
    LAYER = "layer_persistence"
    MATERIALISATION = "materialisation"
    DOWNSTREAM_COUNT = "downstream_dependant_count"
    NONE = "no_signal"


class EntityKind(StrEnum):
    """Entity shapes Hunter recognises. Suffixes are configured, not fixed."""

    FACT = "fact"
    DIMENSION = "dimension"
    AGGREGATE = "aggregate"
    BRIDGE = "bridge"
    SNAPSHOT = "snapshot"
    OTHER = "other"
    UNKNOWN = "unknown"


class BuildStatus(StrEnum):
    """Declared lifecycle status of an entity, from the register."""

    PLANNED = "planned"
    BUILDING = "building"
    LIVE = "live"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class Presence(StrEnum):
    """Whether an entity appears at one point of the alignment chain.

    ``UNKNOWN`` is not the same as ``ABSENT``. Without warehouse access the
    warehouse column is UNKNOWN, and FR17.7 requires saying so rather than
    assuming the entity is missing.
    """

    PRESENT = "present"
    ABSENT = "absent"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class AlignmentState(StrEnum):
    """The state shown to the reader for one entity. Section 17, extended.

    ``BUILT_DISABLED`` and ``APPROVED_OFF_PLAN`` are additions to the seven
    states in the requirements document. The first exists because the pilot has
    six models that are built but switched off by a dbt variable, and calling
    those "designed, not started" would be wrong. The second exists because the
    register lets a team approve an off-plan build.
    """

    DESIGNED_AND_DELIVERED = "designed_and_delivered"
    BUILT_NOT_DEPLOYED = "built_not_deployed"
    BUILT_DISABLED = "built_disabled"
    DESIGNED_NOT_STARTED = "designed_not_started"
    LIVE_WITHOUT_CODE = "live_without_code"
    BUILT_OFF_PLAN = "built_off_plan"
    APPROVED_OFF_PLAN = "approved_off_plan"
    OFF_PLAN_NOT_DEPLOYED = "off_plan_not_deployed"
    UNTRACKED_TABLE = "untracked_table"
    CONCEPTUAL_ONLY = "conceptual_only"
    LOGICAL_ONLY = "logical_only"
    NOT_PRESENT = "not_present"


#: Plain-language label for each state, for the non-technical views. F14.5.
ALIGNMENT_STATE_LABELS: dict[AlignmentState, str] = {
    AlignmentState.DESIGNED_AND_DELIVERED: "Designed and delivered",
    AlignmentState.BUILT_NOT_DEPLOYED: "Built, not deployed",
    AlignmentState.BUILT_DISABLED: "Built, switched off",
    AlignmentState.DESIGNED_NOT_STARTED: "Designed, not started",
    AlignmentState.LIVE_WITHOUT_CODE: "Live without code",
    AlignmentState.BUILT_OFF_PLAN: "Built off-plan",
    AlignmentState.APPROVED_OFF_PLAN: "Built off-plan, approved",
    AlignmentState.OFF_PLAN_NOT_DEPLOYED: "Off-plan, not deployed",
    AlignmentState.UNTRACKED_TABLE: "Untracked table",
    AlignmentState.CONCEPTUAL_ONLY: "On the business model only",
    AlignmentState.LOGICAL_ONLY: "On the data flow diagram only",
    AlignmentState.NOT_PRESENT: "Not present anywhere",
}


#: What each state means, in business terms. F14.2.
ALIGNMENT_STATE_MEANINGS: dict[AlignmentState, str] = {
    AlignmentState.DESIGNED_AND_DELIVERED: "Working as intended.",
    AlignmentState.BUILT_NOT_DEPLOYED: "The code exists but has not reached production yet.",
    AlignmentState.BUILT_DISABLED: (
        "The code exists but is switched off, so nothing is being produced from it."
    ),
    AlignmentState.DESIGNED_NOT_STARTED: "On the plan, no work done yet.",
    AlignmentState.LIVE_WITHOUT_CODE: (
        "Something outside this project is producing this table. Nobody here manages it."
    ),
    AlignmentState.BUILT_OFF_PLAN: (
        "Delivered but never designed, so it is undocumented and has no named owner."
    ),
    AlignmentState.APPROVED_OFF_PLAN: (
        "Delivered ahead of the design, with a recorded reason and a review date."
    ),
    AlignmentState.OFF_PLAN_NOT_DEPLOYED: ("Work in progress outside the plan, or abandoned."),
    AlignmentState.UNTRACKED_TABLE: ("In production, and nobody designed or built it here."),
    AlignmentState.CONCEPTUAL_ONLY: (
        "Agreed with the business as something the warehouse should hold, but not "
        "designed yet. This is the design backlog."
    ),
    AlignmentState.LOGICAL_ONLY: (
        "Named in the data flow diagram, with no design and no model of its own. "
        "It may be produced by an installed package rather than by this project."
    ),
    AlignmentState.NOT_PRESENT: "Referenced somewhere but found nowhere.",
}


class ReportMode(StrEnum):
    """Who the report is written for. FR13.3."""

    INTERNAL = "internal"
    CLIENT = "client"


class ManifestSource(StrEnum):
    """How CI gets dbt's manifest. Chosen at ``hunter init``, kept in hunter.yml."""

    PARSE = "parse"  # run dbt parse in CI; needs a dbt profile secret
    COMMITTED = "committed"  # unpack a manifest committed in the repository
    ARTIFACT = "artifact"  # fetch it from the repository's own dbt workflow


class PrMode(StrEnum):
    """How the Action behaves on a pull request. FR11.6."""

    ADVISORY = "advisory"
    RATCHET = "ratchet"
    GATE = "gate"
