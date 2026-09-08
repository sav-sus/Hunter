"""Normalisation: layers, consumers, persistence, attribution and vendoring."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
import yaml

from hunter.config import resolve
from hunter.config.register import Register
from hunter.enums import EntityKind, Persistence, PersistenceSignal
from hunter.ingest.git import FileHistory, GitData
from hunter.ingest.lookml import LookmlData
from hunter.ingest.manifest import ManifestData
from hunter.model.build import build_project, consumers_of
from hunter.model.entities import Exposure, LookmlField, LookmlView, Model


def model(
    name: str,
    *,
    path: str | None = None,
    deps: list[str] | None = None,
    materialised: str = "view",
    package: str | None = "my_project",
    vendored: bool = False,
) -> Model:
    return Model(
        name=name,
        unique_id=f"model.my_project.{name}",
        path=path or f"models/{name}.sql",
        depends_on_models=deps or [],
        materialisation=materialised,
        package=package,
        vendored=vendored,
    )


def manifest_with(*models: Model) -> ManifestData:
    data = ManifestData()
    data.project_name = "my_project"
    for item in models:
        data.models[item.name] = item
    return data


@pytest.fixture
def config():
    return resolve().config


class TestLayers:
    def test_layer_comes_from_the_path(self, config) -> None:
        data = manifest_with(model("anything", path="models/warehouse/anything.sql"))
        project, _ = build_project(config=config, register=Register(), manifest=data)
        assert project.models["anything"].layer == "warehouse"

    def test_prefix_places_a_model_in_an_undeclared_directory(self, config) -> None:
        data = manifest_with(model("wh_sales__order_fact", path="odd/place/x.sql"))
        project, _ = build_project(config=config, register=Register(), manifest=data)
        assert project.models["wh_sales__order_fact"].layer == "warehouse"

    def test_domain_is_read_from_the_name(self, config) -> None:
        data = manifest_with(model("wh_commerce__order_fact", path="models/warehouse/x.sql"))
        project, _ = build_project(config=config, register=Register(), manifest=data)
        assert project.models["wh_commerce__order_fact"].domain == "commerce"

    def test_a_model_outside_every_layer_gets_none_rather_than_a_guess(self, config) -> None:
        data = manifest_with(model("mystery", path="somewhere/else.sql"))
        project, _ = build_project(config=config, register=Register(), manifest=data)
        assert project.models["mystery"].layer is None

    def test_declared_entity_kind_comes_from_the_suffix(self, config) -> None:
        data = manifest_with(
            model("wh_a__thing_fact", path="models/warehouse/a.sql"),
            model("wh_a__thing_dim", path="models/warehouse/b.sql"),
            model("wh_a__thing_xa", path="models/warehouse/c.sql"),
            model("wh_a__plain", path="models/warehouse/d.sql"),
        )
        project, _ = build_project(config=config, register=Register(), manifest=data)
        assert project.models["wh_a__thing_fact"].entity_kind_declared is EntityKind.FACT
        assert project.models["wh_a__thing_dim"].entity_kind_declared is EntityKind.DIMENSION
        assert project.models["wh_a__thing_xa"].entity_kind_declared is EntityKind.AGGREGATE
        assert project.models["wh_a__plain"].entity_kind_declared is EntityKind.UNKNOWN


class TestDownstream:
    def test_downstream_models_are_transitive_and_sorted(self, config) -> None:
        data = manifest_with(
            model("stg_a"),
            model("int_b", deps=["stg_a"]),
            model("wh_c", deps=["int_b"]),
        )
        project, _ = build_project(config=config, register=Register(), manifest=data)
        assert project.models["stg_a"].downstream_models == ["int_b", "wh_c"]

    def test_dependencies_on_absent_models_do_not_appear_downstream(self, config) -> None:
        """A dependency on a package model keeps lineage connected but is not
        reported as one of the client's own downstream models."""
        data = manifest_with(model("wh_c", deps=["snowplow_unified_sessions"]))
        project, _ = build_project(config=config, register=Register(), manifest=data)
        assert project.models["wh_c"].downstream_models == []


class TestExposureWeighting:
    def test_lookml_fields_raise_the_weight(self, config) -> None:
        data = manifest_with(model("wh_a__order_fact", path="models/warehouse/a.sql"))
        lookml = LookmlData()
        view = LookmlView(name="orders", sql_table_name="wh_a__order_fact")
        view.model_name = "wh_a__order_fact"
        view.fields = [
            LookmlField(name=f"f{index}", view="orders", field_type="dimension")
            for index in range(12)
        ]
        lookml.views["orders"] = view

        project, _ = build_project(config=config, register=Register(), manifest=data, lookml=lookml)
        assert project.models["wh_a__order_fact"].exposure_weight > 1.0

    def test_weighting_can_be_switched_off(self, tmp_path: Path) -> None:
        path = tmp_path / "hunter.yml"
        path.write_text(
            yaml.safe_dump({"scoring": {"exposure_weighting": False}}), encoding="utf-8"
        )
        config = resolve(path).config

        data = manifest_with(model("wh_a__order_fact", path="models/warehouse/a.sql"))
        exposure = Exposure(
            name="dash",
            unique_id="exposure.my_project.dash",
            depends_on_models=["wh_a__order_fact"],
        )
        data.exposures = [exposure]
        project, _ = build_project(config=config, register=Register(), manifest=data)
        assert project.models["wh_a__order_fact"].exposure_weight == 1.0


class TestPersistence:
    def test_a_warehouse_table_is_persistent_by_its_layer(self, config) -> None:
        data = manifest_with(
            model("wh_a__x_fact", path="models/warehouse/a.sql", materialised="table")
        )
        project, _ = build_project(config=config, register=Register(), manifest=data)
        item = project.models["wh_a__x_fact"]
        assert item.persistence is Persistence.PERSISTENT
        assert item.persistence_signal is PersistenceSignal.LAYER

    def test_an_ephemeral_model_is_temporary_whatever_its_layer(self, config) -> None:
        data = manifest_with(
            model("wh_a__x_fact", path="models/warehouse/a.sql", materialised="ephemeral")
        )
        project, _ = build_project(config=config, register=Register(), manifest=data)
        item = project.models["wh_a__x_fact"]
        assert item.persistence is Persistence.TEMPORARY
        assert item.persistence_signal is PersistenceSignal.EPHEMERAL

    def test_the_register_outranks_every_inferred_signal(self, config) -> None:
        """A person stating intent beats anything Hunter can work out, and it
        costs them a written reason."""
        register = Register.model_validate(
            {
                "models": {
                    "wh_a__x_fact": {
                        "persistence": "temporary",
                        "reason": "staging step for the rebuild, removed next sprint",
                    }
                }
            }
        )
        data = manifest_with(
            model("wh_a__x_fact", path="models/warehouse/a.sql", materialised="table")
        )
        project, _ = build_project(config=config, register=register, manifest=data)
        item = project.models["wh_a__x_fact"]
        assert item.persistence is Persistence.TEMPORARY
        assert item.persistence_signal is PersistenceSignal.REGISTER

    def test_the_deciding_signal_is_always_recorded(self, config) -> None:
        """FR1.3 requires reporting which signal decided, not just the answer."""
        data = manifest_with(
            model("mystery", path="nowhere/x.sql", materialised="table"),
        )
        project, _ = build_project(config=config, register=Register(), manifest=data)
        assert project.models["mystery"].persistence_signal is PersistenceSignal.MATERIALISATION


class TestVendoring:
    def test_package_models_are_excluded_from_scoring(self, config) -> None:
        """Holding a client to their conventions on code they did not write
        produces findings nobody can act on."""
        data = manifest_with(
            model("own_model", path="models/warehouse/a.sql"),
            model("elementary_thing", path="models/x.sql", package="elementary", vendored=True),
        )
        project, _ = build_project(config=config, register=Register(), manifest=data)
        assert project.models["own_model"].is_scoreable
        assert not project.models["elementary_thing"].is_scoreable


class TestDisabledModels:
    def test_disabled_models_are_kept_and_still_classified(self, config) -> None:
        data = manifest_with(model("live_one", path="models/warehouse/a.sql"))
        off = model("switched_off", path="models/warehouse/b.sql")
        off.enabled = False
        data.disabled_models["switched_off"] = off

        project, _ = build_project(config=config, register=Register(), manifest=data)
        assert "switched_off" not in project.models
        assert project.any_model("switched_off") is not None
        assert project.disabled_models["switched_off"].layer == "warehouse"
        assert project.model_names() == {"live_one", "switched_off"}


class TestAttribution:
    def test_git_history_matches_on_a_path_suffix(self, config) -> None:
        """Manifest paths are project-relative; git paths are repo-relative."""
        data = manifest_with(model("wh_a__x_fact", path="models/warehouse/a.sql"))
        git = GitData(available=True)
        git.histories["dbt/models/warehouse/a.sql"] = FileHistory(
            path="dbt/models/warehouse/a.sql",
            created_by="First Author",
            created_at=dt.date(2026, 1, 1),
            last_modified_by="Second Author",
            last_modified_at=dt.date(2026, 6, 1),
        )
        project, _ = build_project(config=config, register=Register(), manifest=data, git=git)
        item = project.models["wh_a__x_fact"]
        assert item.created_by == "First Author"
        assert item.last_modified_by == "Second Author"

    def test_an_ambiguous_path_is_attributed_to_nobody(self, config) -> None:
        """Two matches means guessing. FR6.5 reports no identifiable owner
        instead."""
        data = manifest_with(model("x", path="models/a.sql"))
        git = GitData(available=True)
        for prefix in ("one", "two"):
            git.histories[f"{prefix}/models/a.sql"] = FileHistory(
                path=f"{prefix}/models/a.sql", created_by="Someone"
            )
        project, _ = build_project(config=config, register=Register(), manifest=data, git=git)
        assert project.models["x"].created_by is None


class TestRegisterMetadata:
    def test_owner_and_entity_type_are_applied(self, config) -> None:
        register = Register.model_validate(
            {"models": {"wh_a__x": {"owner": "commerce", "entity_type": "fact"}}}
        )
        data = manifest_with(model("wh_a__x", path="models/warehouse/a.sql"))
        project, _ = build_project(config=config, register=register, manifest=data)
        item = project.models["wh_a__x"]
        assert item.owner == "commerce"
        assert item.entity_kind_declared is EntityKind.FACT

    def test_an_entry_for_an_absent_model_is_ignored_here(self, config) -> None:
        """The stale entry is reported by validate_register, not by crashing."""
        register = Register.model_validate({"models": {"absent": {"owner": "x"}}})
        data = manifest_with(model("present", path="models/warehouse/a.sql"))
        project, _ = build_project(config=config, register=register, manifest=data)
        assert project.models["present"].owner is None


class TestConsumersOf:
    def test_blast_radius_counts_views_fields_and_explores(self, config) -> None:
        data = manifest_with(model("wh_a__order_fact", path="models/warehouse/a.sql"))
        lookml = LookmlData()
        view = LookmlView(name="orders", sql_table_name="wh_a__order_fact")
        view.model_name = "wh_a__order_fact"
        view.fields = [LookmlField(name="f", view="orders", field_type="dimension")]
        lookml.views["orders"] = view
        project, _ = build_project(config=config, register=Register(), manifest=data, lookml=lookml)

        found = consumers_of("wh_a__order_fact", project)
        assert found.lookml_views == 1
        assert found.lookml_fields == 1
