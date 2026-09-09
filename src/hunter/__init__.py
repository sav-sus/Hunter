"""Rittman Hunter: repository intelligence for dbt and LookML projects."""

from __future__ import annotations

__version__ = "0.1.0"

#: Bumped whenever the score arithmetic changes in a way that moves a number.
#: FR7.8 and FR7.9: a client on a support plan must never see an apparent
#: regression caused by an upgrade, so version-attributable movement is
#: reported apart from real repository change.
SCORE_MODEL_VERSION = "1"

__all__ = ["SCORE_MODEL_VERSION", "__version__"]
