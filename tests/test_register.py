"""The authored register: what it accepts, what it refuses, what goes stale."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
import yaml

from hunter.config.register import (
    OffPlanApproval,
    Register,
    RegisterError,
    RegisterModel,
    load_register,
    validate_register,
)
from hunter.enums import Persistence, Severity

TODAY = dt.date(2026, 9, 8)


def write(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


class TestReasonsWhereRequired:
    """Information needs no justification. Exceptions do."""

    def test_plain_metadata_needs_no_reason(self) -> None:
        entry = RegisterModel(owner="data-platform", grain="one row per store per day")
        assert entry.owner == "data-platform"
        assert entry.reason is None

    def test_declaring_persistence_needs_a_reason(self) -> None:
        with pytest.raises(ValueError, match="needs a reason"):
            RegisterModel(persistence=Persistence.TEMPORARY)

    def test_declaring_persistence_with_a_reason_is_accepted(self) -> None:
        entry = RegisterModel(
            persistence=Persistence.TEMPORARY,
            reason="intermediate step feeding the order fact, not for consumption",
        )
        assert entry.persistence is Persistence.TEMPORARY

    def test_approval_needs_a_reason(self) -> None:
        with pytest.raises(ValueError, match="real reason"):
            RegisterModel(approved=True, approved_by="sav")

    def test_approval_needs_a_named_approver(self) -> None:
        with pytest.raises(ValueError, match="approved_by"):
            RegisterModel(approved=True, reason="agreed at the design review on 3 September")

    @pytest.mark.parametrize("placeholder", ["tbd", "TODO", "n/a", "-", "?", "", "  ", "reason"])
    def test_placeholder_reasons_are_refused(self, placeholder: str) -> None:
        with pytest.raises(ValueError):
            RegisterModel(approved=True, approved_by="sav", reason=placeholder)

    def test_off_plan_approval_needs_reason_and_approver(self) -> None:
        with pytest.raises(ValueError, match="real reason"):
            OffPlanApproval(model="wh_x__y_fact", reason="tbd", approved_by="sav")

    def test_blank_strings_become_none(self) -> None:
        entry = RegisterModel(owner="   ", grain="")
        assert entry.owner is None
        assert entry.grain is None


class TestLoading:
    def test_a_missing_file_is_an_empty_register(self, tmp_path: Path) -> None:
        register = load_register(tmp_path / "absent.yml")
        assert register.models == {}
        assert register.off_plan_approved == []

    def test_an_empty_file_is_an_empty_register(self, tmp_path: Path) -> None:
        path = tmp_path / "register.yml"
        path.write_text("", encoding="utf-8")
        assert load_register(path).models == {}

    def test_a_full_file_round_trips(self, tmp_path: Path) -> None:
        path = write(
            tmp_path / "register.yml",
            {
                "version": 1,
                "models": {
                    "int_orders__joined": {
                        "persistence": "temporary",
                        "reason": "intermediate step feeding the order fact",
                        "review_by": "2026-12-31",
                    },
                    "wh_sales__order_fact": {
                        "owner": "commerce",
                        "grain": "one row per order",
                        "entity_type": "fact",
                        "business_name": "Orders",
                        "domain": "sales",
                    },
                },
                "off_plan_approved": [
                    {
                        "model": "wh_finance__ledger_fact",
                        "reason": "built for the year-end close, design entry to follow",
                        "approved_by": "sav",
                        "review_by": "2026-10-31",
                    }
                ],
                "ignores": [
                    {
                        "rule": "documentation.model_description_missing",
                        "models": ["stg_legacy__*"],
                        "reason": "legacy staging, scheduled for removal in Q4",
                        "expires": "2026-11-30",
                    }
                ],
                "conceptual": [
                    {"name": "orders", "business_name": "Orders", "domain": "sales"},
                ],
            },
        )
        register = load_register(path)
        assert register.declared_persistence("int_orders__joined") is Persistence.TEMPORARY
        assert register.entry("wh_sales__order_fact").grain == "one row per order"
        assert register.is_off_plan_approved("wh_finance__ledger_fact")
        assert register.conceptual[0].label == "Orders"

    def test_unknown_key_is_refused(self, tmp_path: Path) -> None:
        path = write(tmp_path / "register.yml", {"models": {"x": {"ownr": "typo"}}})
        with pytest.raises(RegisterError, match="not a valid register"):
            load_register(path)

    def test_malformed_yaml_is_a_clear_error(self, tmp_path: Path) -> None:
        path = tmp_path / "register.yml"
        path.write_text("models: [unclosed", encoding="utf-8")
        with pytest.raises(RegisterError, match="not valid YAML"):
            load_register(path)

    def test_duplicate_off_plan_approval_is_refused(self, tmp_path: Path) -> None:
        path = write(
            tmp_path / "register.yml",
            {
                "off_plan_approved": [
                    {"model": "a", "reason": "a good reason recorded here", "approved_by": "s"},
                    {"model": "a", "reason": "another good reason recorded", "approved_by": "s"},
                ]
            },
        )
        with pytest.raises(RegisterError, match="more than once"):
            load_register(path)


class TestIgnoreLookup:
    def test_a_live_ignore_covers_its_rule(self) -> None:
        register = Register.model_validate(
            {
                "ignores": [
                    {
                        "rule": "documentation.model_description_missing",
                        "models": ["stg_*"],
                        "reason": "documentation sweep scheduled for next sprint",
                        "expires": "2026-12-31",
                    }
                ]
            }
        )
        found = register.ignore_for("documentation.model_description_missing", "stg_orders", TODAY)
        assert found is not None

    def test_an_expired_ignore_covers_nothing(self) -> None:
        """FR8.5: the finding comes back on expiry."""
        register = Register.model_validate(
            {
                "ignores": [
                    {
                        "rule": "documentation.model_description_missing",
                        "models": ["stg_*"],
                        "reason": "documentation sweep scheduled for last sprint",
                        "expires": "2026-06-30",
                    }
                ]
            }
        )
        assert (
            register.ignore_for("documentation.model_description_missing", "stg_orders", TODAY)
            is None
        )


class TestValidateRegister:
    """A register nobody prunes stops being a record and becomes a hiding place."""

    def test_entry_for_a_model_that_no_longer_exists_is_reported(self) -> None:
        register = Register.model_validate({"models": {"wh_gone__x_fact": {"owner": "a"}}})
        issues = validate_register(
            register, known_models={"wh_here__y_fact"}, known_rules=set(), as_of=TODAY
        )
        assert [i.rule for i in issues] == ["register.entry_matches_no_model"]
        assert issues[0].severity is Severity.LOW

    def test_overdue_review_is_reported(self) -> None:
        register = Register.model_validate(
            {
                "models": {
                    "int_x__y": {
                        "persistence": "temporary",
                        "reason": "intermediate step, reviewed each quarter",
                        "review_by": "2026-06-30",
                    }
                }
            }
        )
        issues = validate_register(
            register, known_models={"int_x__y"}, known_rules=set(), as_of=TODAY
        )
        assert [i.rule for i in issues] == ["register.review_overdue"]
        assert issues[0].severity is Severity.MEDIUM

    def test_overdue_off_plan_approval_is_reported(self) -> None:
        register = Register.model_validate(
            {
                "off_plan_approved": [
                    {
                        "model": "wh_finance__ledger_fact",
                        "reason": "built for the year-end close, design entry to follow",
                        "approved_by": "sav",
                        "review_by": "2026-07-31",
                    }
                ]
            }
        )
        issues = validate_register(
            register,
            known_models={"wh_finance__ledger_fact"},
            known_rules=set(),
            as_of=TODAY,
        )
        assert [i.rule for i in issues] == ["register.approval_review_overdue"]
        assert "sav" in issues[0].evidence["approved_by"]

    def test_expired_ignore_is_reported(self) -> None:
        register = Register.model_validate(
            {
                "ignores": [
                    {
                        "rule": "documentation.model_description_missing",
                        "reason": "documentation sweep scheduled for last sprint",
                        "expires": "2026-06-30",
                    }
                ]
            }
        )
        issues = validate_register(register, known_models=set(), known_rules=set(), as_of=TODAY)
        assert [i.rule for i in issues] == ["register.ignore_expired"]

    def test_ignore_naming_an_unknown_rule_is_reported(self) -> None:
        register = Register.model_validate(
            {
                "ignores": [
                    {
                        "rule": "documentation.model_descrption_missing",
                        "reason": "misspelt rule name, silences nothing at all",
                        "expires": "2027-12-31",
                    }
                ]
            }
        )
        issues = validate_register(
            register,
            known_models=set(),
            known_rules={"documentation.model_description_missing"},
            as_of=TODAY,
        )
        assert [i.rule for i in issues] == ["register.ignore_names_unknown_rule"]

    def test_wildcard_ignore_is_not_flagged_as_unknown(self) -> None:
        register = Register.model_validate(
            {
                "ignores": [
                    {
                        "rule": "documentation.*",
                        "reason": "documentation sweep scheduled for next sprint",
                        "expires": "2027-12-31",
                    }
                ]
            }
        )
        issues = validate_register(
            register,
            known_models=set(),
            known_rules={"documentation.model_description_missing"},
            as_of=TODAY,
        )
        assert issues == []

    def test_a_healthy_register_produces_nothing(self) -> None:
        register = Register.model_validate(
            {
                "models": {"wh_a__b_fact": {"owner": "team", "grain": "one row per thing"}},
                "off_plan_approved": [
                    {
                        "model": "wh_a__c_fact",
                        "reason": "delivered early with the design entry agreed",
                        "approved_by": "sav",
                        "review_by": "2027-01-31",
                    }
                ],
            }
        )
        issues = validate_register(
            register,
            known_models={"wh_a__b_fact", "wh_a__c_fact"},
            known_rules=set(),
            as_of=TODAY,
        )
        assert issues == []

    def test_every_issue_carries_a_plain_language_consequence(self) -> None:
        """F14.2: a finding without a consequence line is not shippable."""
        register = Register.model_validate(
            {
                "models": {"gone": {"owner": "a"}},
                "ignores": [
                    {
                        "rule": "a.b",
                        "reason": "an expired exception left behind",
                        "expires": "2026-01-01",
                    }
                ],
            }
        )
        issues = validate_register(register, known_models={"other"}, known_rules=set(), as_of=TODAY)
        assert issues
        for issue in issues:
            assert issue.consequence.strip()
            assert issue.summary.strip()
            assert not issue.consequence.startswith("high severity")


class TestImplementsMap:
    def test_maps_model_to_designed_table_where_names_differ(self) -> None:
        register = Register.model_validate(
            {
                "models": {
                    "wh_sales__orders": {"implements": "wh_sales__order_fact"},
                    "wh_sales__returns": {"owner": "commerce"},
                }
            }
        )
        assert register.implements_map() == {"wh_sales__orders": "wh_sales__order_fact"}


class TestVerified:
    """The third status. Permanent, plus a named person saying so."""

    def test_verified_needs_a_reason(self) -> None:
        with pytest.raises(ValueError, match="needs a reason"):
            RegisterModel(persistence=Persistence.VERIFIED, verified_by="sav")

    def test_verified_needs_a_named_person(self) -> None:
        with pytest.raises(ValueError, match="verified_by"):
            RegisterModel(
                persistence=Persistence.VERIFIED,
                reason="signed off at the design review as the order fact of record",
            )

    def test_verified_with_both_is_accepted(self) -> None:
        entry = RegisterModel(
            persistence=Persistence.VERIFIED,
            verified_by="sav",
            reason="signed off at the design review as the order fact of record",
        )
        assert entry.persistence is Persistence.VERIFIED
        assert entry.persistence.is_lasting

    def test_verified_by_on_its_own_is_refused(self) -> None:
        with pytest.raises(ValueError, match="verified_by only means something"):
            RegisterModel(owner="commerce", verified_by="sav")

    def test_permanent_is_the_word_people_write(self) -> None:
        """The stored value is ``persistent``; the file accepts the everyday word."""
        entry = RegisterModel(
            persistence="permanent",  # type: ignore[arg-type]
            reason="a finished table, kept although its layer is a working layer",
        )
        assert entry.persistence is Persistence.PERSISTENT
        assert entry.persistence.label == "permanent"

    def test_unknown_cannot_be_declared(self) -> None:
        with pytest.raises(ValueError, match="temporary, verified or permanent"):
            RegisterModel(persistence=Persistence.UNKNOWN, reason="a long enough reason here")
