"""Configuration resolution: precedence, provenance and the divergence report."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
import yaml

from hunter.config import ConfigError, resolve
from hunter.config.loader import house_path
from hunter.config.schema import IgnoreRule, ScoringSpec
from hunter.enums import ConfigLevel, Dimension


def write(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


class TestHouseRuleset:
    def test_shipped_house_resolves_on_its_own(self) -> None:
        resolved = resolve()
        assert resolved.config.extends == "ra-house@1"
        assert resolved.config.house_version == "1"
        assert resolved.divergences == []

    def test_weights_total_100(self) -> None:
        weights = resolve().config.scoring.weights
        assert sum(weights.values()) == pytest.approx(100.0)
        assert set(weights) == set(Dimension)

    def test_house_spec_must_name_a_version(self) -> None:
        with pytest.raises(ConfigError, match="must name a version"):
            house_path("ra-house")

    def test_unknown_house_version_says_what_is_available(self) -> None:
        with pytest.raises(ConfigError, match="ra-house-1"):
            house_path("ra-house@99")


class TestPrecedence:
    def test_project_beats_house(self, tmp_path: Path) -> None:
        project = write(
            tmp_path / "hunter.yml",
            {"extends": "ra-house@1", "structure": {"max_joins": 3}},
        )
        resolved = resolve(project)
        assert resolved.config.structure.max_joins == 3
        assert resolved.level_of("structure.max_joins") == ConfigLevel.PROJECT

    def test_house_value_survives_where_project_is_silent(self, tmp_path: Path) -> None:
        project = write(tmp_path / "hunter.yml", {"structure": {"max_joins": 3}})
        resolved = resolve(project)
        # max_model_lines came from the house file, not the project
        assert resolved.config.structure.max_model_lines == 400
        assert resolved.level_of("structure.max_model_lines") == ConfigLevel.HOUSE

    def test_model_overlay_beats_project(self, tmp_path: Path) -> None:
        project = write(tmp_path / "hunter.yml", {"structure": {"max_joins": 3}})
        resolved = resolve(
            project,
            overlays={ConfigLevel.MODEL: {"structure": {"max_joins": 1}}},
        )
        assert resolved.config.structure.max_joins == 1
        assert resolved.level_of("structure.max_joins") == ConfigLevel.MODEL

    def test_register_overlay_beats_project_and_loses_to_model(self, tmp_path: Path) -> None:
        project = write(tmp_path / "hunter.yml", {"structure": {"max_joins": 9}})
        resolved = resolve(
            project,
            overlays={
                ConfigLevel.REGISTER: {"structure": {"max_joins": 5}},
                ConfigLevel.MODEL: {"structure": {"max_joins": 2}},
            },
        )
        assert resolved.config.structure.max_joins == 2


class TestKeyedListMerge:
    """A project adding one layer must not have to restate every layer."""

    def test_overriding_one_layer_keeps_the_rest(self, tmp_path: Path) -> None:
        house_names = [layer.name for layer in resolve().config.layers]
        project = write(
            tmp_path / "hunter.yml",
            {"layers": [{"name": "staging", "prefix": "s_"}]},
        )
        resolved = resolve(project)

        # Every house layer survives, in the same order
        assert [layer.name for layer in resolved.config.layers] == house_names
        assert resolved.config.layer("staging").prefix == "s_"
        # Untouched fields on the same layer survive
        assert resolved.config.layer("staging").persistence.value == "temporary"

    def test_adding_a_new_layer_appends_it(self, tmp_path: Path) -> None:
        house_count = len(resolve().config.layers)
        project = write(
            tmp_path / "hunter.yml",
            {
                "layers": [
                    {
                        "name": "sandbox",
                        "paths": ["models/sandbox/**"],
                        "persistence": "temporary",
                        "may_reference": ["staging"],
                    }
                ]
            },
        )
        resolved = resolve(project)
        assert resolved.config.layer("sandbox") is not None
        assert len(resolved.config.layers) == house_count + 1

    def test_entities_merge_on_kind(self, tmp_path: Path) -> None:
        house_count = len(resolve().config.entities)
        project = write(
            tmp_path / "hunter.yml",
            {"entities": [{"kind": "fact", "suffix": "_f"}]},
        )
        resolved = resolve(project)
        assert resolved.config.entity_for_name("orders_f").kind.value == "fact"
        assert len(resolved.config.entities) == house_count

    def test_ignores_accumulate_rather_than_replace(self, tmp_path: Path) -> None:
        project = write(
            tmp_path / "hunter.yml",
            {
                "ignores": [
                    {
                        "rule": "documentation.model_description_missing",
                        "models": ["stg_legacy_*"],
                        "reason": "legacy staging, scheduled for removal in Q4",
                        "expires": "2027-01-31",
                    }
                ]
            },
        )
        resolved = resolve(project)
        assert len(resolved.config.ignores) == 1
        assert resolved.config.ignores[0].rule == "documentation.model_description_missing"


class TestDivergenceReport:
    """FR7b and FR7d: overrides are a first-class output, not a side effect."""

    def test_override_is_reported_with_both_values(self, tmp_path: Path) -> None:
        project = write(tmp_path / "hunter.yml", {"structure": {"max_joins": 3}})
        resolved = resolve(project)
        paths = resolved.overridden_paths()
        assert "structure.max_joins" in paths
        divergence = next(d for d in resolved.divergences if d.path == "structure.max_joins")
        assert divergence.house_value == 7
        assert divergence.project_value == 3
        assert divergence.level == ConfigLevel.PROJECT

    def test_reweighting_is_labelled_as_such(self, tmp_path: Path) -> None:
        weights = {str(d): v for d, v in resolve().config.scoring.weights.items()}
        weights["testing"] = 8.0
        weights["documentation"] = 23.0
        project = write(tmp_path / "hunter.yml", {"scoring": {"weights": weights}})
        resolved = resolve(project)
        changed = {d.path for d in resolved.divergences}
        assert "scoring.weights.testing" in changed
        divergence = next(d for d in resolved.divergences if d.path == "scoring.weights.testing")
        assert divergence.kind == "reweighted"

    def test_disabling_a_rule_is_labelled_and_carries_its_reason(self, tmp_path: Path) -> None:
        project = write(
            tmp_path / "hunter.yml",
            {
                "rules": {
                    "structure.select_star": {
                        "enabled": False,
                        "reason": "the reporting layer expands columns on purpose",
                    }
                }
            },
        )
        resolved = resolve(project)
        assert not resolved.config.is_rule_enabled("structure.select_star")
        # Not a house-set path, so it is not a divergence, but the reason is kept
        setting = resolved.config.rule_setting("structure.select_star")
        assert setting.reason is not None

    def test_a_layer_field_override_is_reported(self, tmp_path: Path) -> None:
        project = write(
            tmp_path / "hunter.yml",
            {"layers": [{"name": "warehouse", "requires_owner": False}]},
        )
        resolved = resolve(project)
        assert "layers.warehouse.requires_owner" in resolved.overridden_paths()

    def test_no_overrides_means_no_divergences(self, tmp_path: Path) -> None:
        project = write(tmp_path / "hunter.yml", {"extends": "ra-house@1"})
        assert resolve(project).divergences == []


class TestValidation:
    def test_partial_weights_inherit_the_rest_and_must_still_total_100(
        self, tmp_path: Path
    ) -> None:
        """Naming two weights keeps the other six, so the total then breaks."""
        project = write(
            tmp_path / "hunter.yml",
            {"scoring": {"weights": {"testing": 50, "documentation": 10}}},
        )
        with pytest.raises(ConfigError, match="must total 100"):
            resolve(project)

    def test_weights_that_miss_the_total_are_rejected(self, tmp_path: Path) -> None:
        weights = {str(d): 1.0 for d in Dimension}
        project = write(tmp_path / "hunter.yml", {"scoring": {"weights": weights}})
        with pytest.raises(ConfigError, match="must total 100"):
            resolve(project)

    def test_a_missing_dimension_is_named(self) -> None:
        """Guards the house file itself: every dimension needs a weight."""
        with pytest.raises(ValueError, match="no weight given for"):
            ScoringSpec(weights={Dimension.TESTING: 100.0})

    def test_negative_weights_are_rejected(self) -> None:
        weights = dict.fromkeys(Dimension, 0.0)
        weights[Dimension.TESTING] = 110.0
        weights[Dimension.DOCUMENTATION] = -10.0
        with pytest.raises(ValueError, match="cannot be negative"):
            ScoringSpec(weights=weights)

    def test_unknown_key_is_an_error_not_a_shrug(self, tmp_path: Path) -> None:
        project = write(tmp_path / "hunter.yml", {"structure": {"max_joinz": 3}})
        with pytest.raises(ConfigError):
            resolve(project)

    def test_layer_referencing_an_unknown_layer_is_rejected(self, tmp_path: Path) -> None:
        project = write(
            tmp_path / "hunter.yml",
            {"layers": [{"name": "warehouse", "may_reference": ["nonesuch"]}]},
        )
        with pytest.raises(ConfigError, match="unknown layers"):
            resolve(project)

    def test_two_entities_cannot_claim_one_suffix(self, tmp_path: Path) -> None:
        project = write(
            tmp_path / "hunter.yml",
            {"entities": [{"kind": "bridge", "suffix": "_fact"}]},
        )
        with pytest.raises(ConfigError, match="claimed by both"):
            resolve(project)

    def test_disabling_a_rule_without_a_reason_is_rejected(self, tmp_path: Path) -> None:
        project = write(
            tmp_path / "hunter.yml",
            {"rules": {"structure.select_star": {"enabled": False}}},
        )
        with pytest.raises(ConfigError, match="requires a reason"):
            resolve(project)

    def test_missing_project_file_is_a_clear_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="not found"):
            resolve(tmp_path / "absent.yml")

    def test_malformed_yaml_is_a_clear_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "hunter.yml"
        bad.write_text("layers: [unclosed", encoding="utf-8")
        with pytest.raises(ConfigError, match="not valid YAML"):
            resolve(bad)

    def test_top_level_list_is_rejected(self, tmp_path: Path) -> None:
        bad = tmp_path / "hunter.yml"
        bad.write_text("- one\n- two\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="mapping at the top level"):
            resolve(bad)


class TestIgnoreRule:
    def test_reason_must_be_a_real_sentence(self) -> None:
        with pytest.raises(ValueError, match="real sentence"):
            IgnoreRule(rule="a.b", reason="tbd", expires=dt.date(2027, 1, 1))

    def test_covers_matches_rule_and_model_patterns(self) -> None:
        ignore = IgnoreRule(
            rule="documentation.model_description_missing",
            models=["stg_ga4__*"],
            reason="legacy staging, scheduled for removal",
            expires=dt.date(2027, 1, 1),
        )
        assert ignore.covers("documentation.model_description_missing", "stg_ga4__event_2024")
        assert not ignore.covers("documentation.model_description_missing", "wh_commerce__x")
        assert not ignore.covers("testing.missing_unique", "stg_ga4__event_2024")

    def test_wildcard_rule_pattern_matches(self) -> None:
        ignore = IgnoreRule(
            rule="documentation.*",
            reason="documentation sweep scheduled for next sprint",
            expires=dt.date(2027, 1, 1),
        )
        assert ignore.covers("documentation.model_description_missing", "anything")

    def test_expiry_is_a_date_comparison(self) -> None:
        ignore = IgnoreRule(
            rule="a.b",
            reason="a good enough reason to wait",
            expires=dt.date(2026, 6, 30),
        )
        assert ignore.is_expired(dt.date(2026, 7, 1))
        assert not ignore.is_expired(dt.date(2026, 6, 30))


class TestRetiredSwitches:
    def test_the_old_exposure_switch_name_still_loads(self) -> None:
        from hunter.config.schema import CrossLayerSpec

        spec = CrossLayerSpec.model_validate({"generate_missing_exposures": False})
        assert spec.report_missing_exposures is False

    def test_the_silent_datagroup_switch_names_its_replacement(self) -> None:
        import pytest

        from hunter.config.schema import CrossLayerSpec

        with pytest.raises(ValueError, match=r"crosslayer\.explore_no_caching_policy"):
            CrossLayerSpec.model_validate({"require_datagroup_on_explores": False})
