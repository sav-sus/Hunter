"""DBML reading: the normalising pass, and recovery from a bad block."""

from __future__ import annotations

from pathlib import Path

from hunter.ingest.dbml import (
    block_subject,
    load_dbml,
    normalise,
    parse_file,
    split_blocks,
)


class TestNormalise:
    """The pilot's design file escapes quotes SQL-style, which pydbml rejects."""

    def test_doubled_quote_inside_a_note_becomes_an_escape(self) -> None:
        text, changes = normalise("table t {\n  c int [note: 'last year''s level']\n}")
        assert "last year\\'s level" in text
        assert changes == 1

    def test_an_empty_string_is_left_alone(self) -> None:
        """The dangerous case. A regular expression corrupts this one."""
        text, changes = normalise("table t {\n  c int [note: '']\n}")
        assert "[note: '']" in text
        assert changes == 0

    def test_triple_quoted_notes_are_left_alone(self) -> None:
        source = "project p {\n  note: '''\n  # Heading\n  text with '' inside\n  '''\n}"
        text, changes = normalise(source)
        assert text == source
        assert changes == 0

    def test_an_existing_backslash_escape_is_kept(self) -> None:
        text, changes = normalise("table t {\n  c int [note: 'last year\\'s level']\n}")
        assert "last year\\'s level" in text
        assert changes == 0

    def test_double_quoted_strings_are_untouched(self) -> None:
        source = 'table "my table" {\n  c int\n}'
        text, changes = normalise(source)
        assert text == source
        assert changes == 0

    def test_quotes_in_comments_are_untouched(self) -> None:
        source = "// it''s a comment\ntable t {\n  c int\n}"
        text, changes = normalise(source)
        assert text == source
        assert changes == 0

    def test_block_comments_are_untouched(self) -> None:
        source = "/* it''s a block comment */\ntable t {\n  c int\n}"
        text, changes = normalise(source)
        assert text == source
        assert changes == 0

    def test_several_doubled_quotes_in_one_note(self) -> None:
        text, changes = normalise("table t {\n  c int [note: 'a''s and b''s and c''s']\n}")
        assert changes == 3
        assert "a\\'s and b\\'s and c\\'s" in text

    def test_empty_input_is_safe(self) -> None:
        assert normalise("") == ("", 0)

    def test_normalised_file_then_parses(self, tmp_path: Path) -> None:
        path = tmp_path / "design.dbml"
        path.write_text(
            "table orders_fact {\n"
            "  order_pk varchar [pk, note: 'last year''s key']\n"
            "  amount numeric [note: 'value']\n"
            "  Note: 'Table Grain: One row per order.'\n"
            "}\n",
            encoding="utf-8",
        )
        data = parse_file(path)
        assert data.issues == []
        entity = data.entities["orders_fact"]
        assert entity.primary_key_columns == ["order_pk"]
        assert entity.column("order_pk").note == "last year's key"
        assert entity.grain_note == "One row per order"


class TestSplitBlocks:
    def test_splits_top_level_blocks(self) -> None:
        blocks = split_blocks(
            "project p {\n  database_type: 'bigquery'\n}\n"
            "table a {\n  x int\n}\n"
            "table b {\n  y int\n}\n"
        )
        kinds = [block.split()[0].lower() for block in blocks]
        assert kinds == ["project", "table", "table"]

    def test_braces_inside_strings_do_not_split(self) -> None:
        blocks = split_blocks("table a {\n  x int [note: 'a { brace }']\n}\n")
        assert len(blocks) == 1

    def test_standalone_ref_line_is_its_own_block(self) -> None:
        blocks = split_blocks("table a {\n  x int\n}\nRef: a.x > b.y\n")
        assert any(block.startswith("Ref:") for block in blocks)

    def test_subject_is_extracted_for_error_reporting(self) -> None:
        assert block_subject("table orders_fact {\n  x int\n}") == "orders_fact"
        assert block_subject('table "quoted name" {\n  x int\n}') == "quoted name"
        assert block_subject("TableGroup commerce {\n  a\n}") == "commerce"


class TestRecovery:
    """One malformed block must cost one table, not a score dimension."""

    def test_a_bad_block_is_isolated_and_reported(self, tmp_path: Path) -> None:
        path = tmp_path / "design.dbml"
        path.write_text(
            "table good_one_fact {\n"
            "  good_one_pk varchar [pk]\n"
            "  Note: 'Table Grain: One row per thing.'\n"
            "}\n"
            "table broken_fact {\n"
            "  this is not valid dbml at all [[[\n"
            "}\n"
            "table good_two_dim {\n"
            "  good_two_pk varchar [pk]\n"
            "}\n",
            encoding="utf-8",
        )
        data = parse_file(path)

        # The two sound tables survive
        assert set(data.entities) == {"good_one_fact", "good_two_dim"}
        # The failure is reported rather than raised
        assert any(issue.subject == "broken_fact" for issue in data.issues)
        assert all(issue.recoverable for issue in data.issues)

    def test_table_groups_survive_the_recovery_path(self, tmp_path: Path) -> None:
        path = tmp_path / "design.dbml"
        path.write_text(
            "TableGroup commerce {\n  orders_fact\n}\n"
            "table orders_fact {\n  order_pk varchar [pk]\n}\n"
            "table broken {\n  !!! [[[\n}\n",
            encoding="utf-8",
        )
        data = parse_file(path)
        assert data.entities["orders_fact"].domain == "commerce"

    def test_an_unreadable_file_is_reported_not_raised(self, tmp_path: Path) -> None:
        data = parse_file(tmp_path / "absent.dbml")
        assert data.entities == {}
        assert len(data.issues) == 1
        assert not data.issues[0].recoverable


class TestLoadDbml:
    def test_a_table_designed_twice_is_reported(self, tmp_path: Path) -> None:
        first = tmp_path / "a.dbml"
        second = tmp_path / "b.dbml"
        first.write_text("table orders_fact {\n  order_pk varchar [pk]\n}\n", encoding="utf-8")
        second.write_text("table orders_fact {\n  other_pk varchar [pk]\n}\n", encoding="utf-8")

        data = load_dbml([first, second])
        assert len(data.entities) == 1
        assert any("designed in two files" in issue.message for issue in data.issues)
        # The first definition wins, so the result is stable across runs
        assert data.entities["orders_fact"].primary_key_columns == ["order_pk"]

    def test_refs_are_sorted_for_determinism(self, tmp_path: Path) -> None:
        path = tmp_path / "a.dbml"
        path.write_text(
            "table z_dim {\n  z_pk varchar [pk]\n}\n"
            "table a_fact {\n  a_pk varchar [pk]\n  z_fk varchar\n}\n"
            "Ref: a_fact.z_fk > z_dim.z_pk\n",
            encoding="utf-8",
        )
        data = load_dbml([path])
        assert [ref.key for ref in data.refs] == sorted(ref.key for ref in data.refs)
        assert data.refs[0].cardinality == "many-to-one"

    def test_no_files_is_an_empty_result_not_an_error(self) -> None:
        data = load_dbml([])
        assert data.entities == {}
        assert data.issues == []
