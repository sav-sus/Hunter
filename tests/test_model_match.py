"""Matching one entity across model levels."""

from __future__ import annotations

import pytest

from hunter.model.match import (
    Index,
    normalise_domain,
    normalise_name,
    qualified_key,
    singularise,
)


class TestSingularise:
    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            ("orders", "order"),
            ("lines", "line"),
            ("categories", "category"),
            ("addresses", "address"),
            ("boxes", "box"),
            ("order", "order"),
            ("status", "status"),
            ("analysis", "analysis"),
            ("business", "business"),
        ],
    )
    def test_forms(self, given: str, expected: str) -> None:
        assert singularise(given) == expected


class TestNormaliseName:
    def test_a_plural_business_name_and_a_suffixed_design_name_agree(self) -> None:
        """The conceptual diagram says demand_orders; the design says
        demand_order_fact."""
        assert normalise_name("wh_commerce__demand_orders") == "demand_order"
        assert normalise_name("wh_commerce__demand_order_fact") == "demand_order"

    @pytest.mark.parametrize(
        ("given", "expected"),
        [
            ("wh_platform__daily_performance_xa", "daily_performance"),
            ("wh_master__customer_dim", "customer"),
            ("stg_sfcc__members", "member"),
            ("plain_name", "plain_name"),
            ("wh_thing_fact", "thing"),
        ],
    )
    def test_forms(self, given: str, expected: str) -> None:
        assert normalise_name(given) == expected

    def test_the_longest_matching_suffix_wins(self) -> None:
        assert normalise_name("x__y_snapshot", suffixes=("_shot", "_snapshot")) == "y"


class TestNormaliseDomain:
    def test_domain_aliases_agree(self) -> None:
        """wh_master_data and wh_master are the same domain."""
        assert normalise_domain("wh_master_data__customer") == "master"
        assert normalise_domain("wh_master__customer_dim") == "master"

    def test_engagement_suffix_is_trimmed(self) -> None:
        assert normalise_domain("wh_platform_engagement__session") == "platform"

    def test_a_name_with_no_domain_gives_none(self) -> None:
        assert normalise_domain("plain_name") is None

    def test_qualified_key_combines_both(self) -> None:
        assert qualified_key("wh_commerce__demand_orders") == "commerce/demand_order"
        assert qualified_key("plain_name") == "plain_name"


class TestIndex:
    @pytest.fixture
    def index(self) -> Index:
        return Index.build(
            [
                "wh_commerce__demand_order_fact",
                "wh_master__customer_dim",
                "wh_platform__session_fact",
                "wh_snowplow_platform__sessions_fact",
            ]
        )

    def test_an_exact_match_is_certain(self, index: Index) -> None:
        match = index.find("wh_master__customer_dim")
        assert match.target == "wh_master__customer_dim"
        assert match.method == "exact"
        assert match.confidence == 1.0

    def test_a_normalised_match_is_less_certain(self, index: Index) -> None:
        match = index.find("wh_commerce__demand_orders")
        assert match.target == "wh_commerce__demand_order_fact"
        assert match.method == "normalised"
        assert match.confidence < 1.0

    def test_a_domain_alias_still_matches(self, index: Index) -> None:
        assert index.find("wh_master_data__customer").target == "wh_master__customer_dim"

    def test_a_declared_mapping_beats_everything(self, index: Index) -> None:
        match = index.find("nothing_like_it", declared="wh_master__customer_dim")
        assert match.target == "wh_master__customer_dim"
        assert match.method == "declared"
        assert match.confidence == 1.0

    def test_a_declared_mapping_naming_an_absent_target_falls_through(self, index: Index) -> None:
        assert index.find("wh_master_data__customer", declared="not_there").matched

    def test_no_match_returns_no_match(self, index: Index) -> None:
        match = index.find("wh_nowhere__nothing")
        assert not match.matched
        assert match.method == "none"

    def test_the_domain_keeps_two_similar_entities_apart(self, index: Index) -> None:
        """Two domains both have a session entity. Neither should win the
        other's row."""
        assert index.find("wh_platform__sessions").target == "wh_platform__session_fact"
        assert (
            index.find("wh_snowplow_platform__session").target
            == "wh_snowplow_platform__sessions_fact"
        )

    def test_an_ambiguous_loose_match_is_reported_not_resolved(self) -> None:
        """Picking one silently produces a wrong row that reads as fact."""
        index = Index.build(["alpha__thing_fact", "beta__thing_dim"])
        match = index.find("thing")
        assert not match.matched
        assert match.ambiguous
        assert match.candidates == ("alpha__thing_fact", "beta__thing_dim")

    def test_an_empty_index_matches_nothing(self) -> None:
        assert not Index.build([]).find("anything").matched
