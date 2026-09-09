"""The committed baseline: where a repository started.

FR7.5. An existing repository starts where it starts and only has to improve.
Without a baseline, installing Hunter on a mature project produces a low number
and an argument, rather than a direction of travel.

The baseline records the versions it was computed with, so a later run can tell
whether movement is real or caused by an upgrade. FR7.9.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from hunter import SCORE_MODEL_VERSION, __version__
from hunter.enums import Dimension
from hunter.model.findings import ScoreResult


class BaselineError(Exception):
    """The baseline file could not be read."""


class Baseline(BaseModel):
    """A committed score, and what produced it."""

    model_config = ConfigDict(extra="forbid")

    total: float
    dimensions: dict[Dimension, float] = Field(default_factory=dict)
    recorded_on: dt.date
    commit: str | None = None
    hunter_version: str = __version__
    house_ruleset_version: str = "unknown"
    score_model_version: str = SCORE_MODEL_VERSION
    note: str | None = None

    @classmethod
    def from_result(
        cls,
        result: ScoreResult,
        *,
        house_version: str,
        commit: str | None = None,
        recorded_on: dt.date | None = None,
        note: str | None = None,
    ) -> Baseline:
        return cls(
            total=result.total,
            dimensions={
                entry.dimension: entry.score for entry in result.dimensions if entry.scored
            },
            recorded_on=recorded_on or dt.date.today(),
            commit=commit,
            house_ruleset_version=house_version,
            note=note,
        )


def load_baseline(path: Path) -> Baseline | None:
    """Read the committed baseline. A missing file means there is not one yet."""
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BaselineError(f"could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BaselineError(f"{path} is not valid JSON: {exc}") from exc

    try:
        return Baseline.model_validate(raw)
    except Exception as exc:
        raise BaselineError(f"{path} is not a valid baseline: {exc}") from exc


def write_baseline(path: Path, baseline: Baseline) -> None:
    """Write a baseline, sorted and newline-terminated so diffs stay readable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = baseline.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def dimension_deltas(result: ScoreResult, baseline: Baseline | None) -> dict[Dimension, float]:
    """Movement per dimension since the baseline."""
    if baseline is None:
        return {}
    out: dict[Dimension, float] = {}
    for entry in result.dimensions:
        if not entry.scored:
            continue
        before = baseline.dimensions.get(entry.dimension)
        if before is not None:
            out[entry.dimension] = round(entry.score - before, 1)
    return dict(sorted(out.items(), key=lambda item: item[0].value))
