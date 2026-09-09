"""The dependency graph and exposure weighting."""

from __future__ import annotations

import pytest

from hunter.model.entities import Model
from hunter.model.graph import Consumers, Graph, exposure_weight


def model(name: str, deps: list[str] | None = None) -> Model:
    return Model(
        name=name,
        unique_id=f"model.project.{name}",
        path=f"models/{name}.sql",
        depends_on_models=deps or [],
    )


@pytest.fixture
def graph() -> Graph:
    """stg_a and stg_b feed int_x; wh_rejoin reads int_x and stg_a directly."""
    models = {
        item.name: item
        for item in [
            model("stg_a"),
            model("stg_b"),
            model("int_x", ["stg_a", "stg_b"]),
            model("wh_f", ["int_x"]),
            model("wh_d", ["stg_a"]),
            model("wh_rejoin", ["int_x", "stg_a"]),
            model("orphan"),
        ]
    }
    return Graph.build(models)


class TestTraversal:
    def test_descendants_reach_every_depth(self, graph: Graph) -> None:
        assert graph.descendants("stg_a") == frozenset({"int_x", "wh_f", "wh_d", "wh_rejoin"})

    def test_ancestors_reach_every_depth(self, graph: Graph) -> None:
        assert graph.ancestors("wh_f") == frozenset({"int_x", "stg_a", "stg_b"})

    def test_an_orphan_has_neither(self, graph: Graph) -> None:
        assert graph.descendants("orphan") == frozenset()
        assert graph.ancestors("orphan") == frozenset()

    def test_results_are_memoised(self, graph: Graph) -> None:
        assert graph.descendants("stg_a") is graph.descendants("stg_a")

    def test_direct_neighbours_are_sorted(self, graph: Graph) -> None:
        assert graph.direct_children("stg_a") == ["int_x", "wh_d", "wh_rejoin"]
        assert graph.direct_parents("int_x") == ["stg_a", "stg_b"]

    def test_fanout_counts_direct_children_only(self, graph: Graph) -> None:
        assert graph.fanout("stg_a") == 3
        assert graph.fanout("int_x") == 2


class TestStructure:
    def test_roots_read_from_sources(self, graph: Graph) -> None:
        assert graph.roots() == ["orphan", "stg_a", "stg_b"]

    def test_leaves_are_read_by_nothing(self, graph: Graph) -> None:
        assert graph.leaves() == ["orphan", "wh_d", "wh_f", "wh_rejoin"]

    def test_topological_order_respects_dependencies(self, graph: Graph) -> None:
        order = graph.topological_order()
        assert order.index("stg_a") < order.index("int_x") < order.index("wh_f")

    def test_a_healthy_graph_has_no_cycles(self, graph: Graph) -> None:
        assert graph.cycles() == []


class TestCycles:
    """dbt will not build a cycle, so one here means an inconsistent manifest."""

    def test_a_cycle_is_found_rather_than_walked_forever(self) -> None:
        models = {"a": model("a", ["b"]), "b": model("b", ["a"])}
        cycles = Graph.build(models).cycles()
        assert len(cycles) == 1
        assert set(cycles[0]) == {"a", "b"}

    def test_topological_order_still_returns_every_node(self) -> None:
        models = {"a": model("a", ["b"]), "b": model("b", ["a"]), "c": model("c")}
        order = Graph.build(models).topological_order()
        assert sorted(order) == ["a", "b", "c"]


class TestRejoins:
    """A model reading the same upstream table twice is how double counting
    starts."""

    def test_a_rejoin_is_found(self, graph: Graph) -> None:
        assert graph.rejoin_paths("wh_rejoin") == ["stg_a"]

    def test_a_single_path_is_not_a_rejoin(self, graph: Graph) -> None:
        assert graph.rejoin_paths("wh_f") == []

    def test_one_parent_cannot_be_a_rejoin(self, graph: Graph) -> None:
        assert graph.rejoin_paths("wh_d") == []


class TestExposureWeight:
    """FR7.4: a missing test on a model feeding 12 dashboard fields costs more
    than the same gap on an orphan."""

    def test_an_orphan_weighs_one(self) -> None:
        assert exposure_weight(0, Consumers()) == 1.0

    def test_weight_grows_with_reach(self) -> None:
        light = exposure_weight(1, Consumers())
        heavy = exposure_weight(20, Consumers(lookml_fields=40))
        assert 1.0 < light < heavy

    def test_weight_is_capped(self) -> None:
        assert exposure_weight(10_000, Consumers(lookml_fields=10_000)) == 3.0

    def test_the_cap_is_configurable(self) -> None:
        assert exposure_weight(10_000, Consumers(), cap=1.5) == 1.5

    def test_growth_is_sublinear_so_one_model_cannot_dominate(self) -> None:
        """Ten times the reach must not cost ten times as much."""
        small = exposure_weight(2, Consumers(), cap=99.0)
        large = exposure_weight(20, Consumers(), cap=99.0)
        assert large < small * 3

    def test_explores_and_exposures_count_double(self) -> None:
        """An explore or a declared exposure is a stronger signal of use than
        one more field."""
        by_field = exposure_weight(0, Consumers(lookml_fields=2), cap=99.0)
        by_explore = exposure_weight(0, Consumers(explores=2), cap=99.0)
        assert by_explore > by_field


class TestConsumers:
    def test_total_excludes_the_view_count(self) -> None:
        consumers = Consumers(lookml_fields=5, lookml_views=1, explores=2, exposures=1)
        assert consumers.total == 8

    def test_a_view_with_no_fields_still_counts_as_use(self) -> None:
        assert Consumers(lookml_views=1).any
        assert not Consumers().any
