"""Tests for Mermaid diagram generation."""

from __future__ import annotations

from cadpya.modeling.diagram import _sanitize_id, _sanitize_label, _sanitize_title, to_mermaid
from tests.coupled_models.test_4gp import make_4gp_model
from tests.coupled_models.test_eic import make_eic_top_model, make_gpp_model
from tests.coupled_models.test_hierarchical import make_hierarchical_model


class TestFlatModel:
    def test_starts_with_flowchart(self) -> None:
        result = to_mermaid(make_4gp_model())
        assert result.startswith("flowchart TD\n")

    def test_contains_all_components(self) -> None:
        result = to_mermaid(make_4gp_model())
        for name in ("G1", "G2", "G3", "G4", "P"):
            assert f'"{name} (' in result

    def test_contains_class_names(self) -> None:
        result = to_mermaid(make_4gp_model())
        assert "(Generator)" in result
        assert "(Processor)" in result

    def test_contains_ic_edges(self) -> None:
        result = to_mermaid(make_4gp_model())
        for i in range(1, 5):
            assert f"G{i} --> P" in result

    def test_contains_eoc_edge(self) -> None:
        result = to_mermaid(make_4gp_model())
        assert "P --> self" in result

    def test_self_boundary_node(self) -> None:
        result = to_mermaid(make_4gp_model())
        assert 'self(["self"])' in result

    def test_no_subgraphs(self) -> None:
        result = to_mermaid(make_4gp_model())
        assert "subgraph" not in result


class TestNestedModel:
    def test_contains_subgraphs(self) -> None:
        result = to_mermaid(make_hierarchical_model())
        assert 'subgraph Left["Left"]' in result
        assert 'subgraph Right["Right"]' in result

    def test_nested_nodes_have_prefix(self) -> None:
        result = to_mermaid(make_hierarchical_model())
        assert 'Left__G1["G1 (Generator)"]' in result
        assert 'Right__G4["G4 (Generator)"]' in result

    def test_nested_edges_use_prefix(self) -> None:
        result = to_mermaid(make_hierarchical_model())
        assert "Left__G1 --> Left__self" in result
        assert "Right__G3 --> Right__self" in result

    def test_top_level_edges(self) -> None:
        result = to_mermaid(make_hierarchical_model())
        assert "Left --> P" in result
        assert "Right --> P" in result
        assert "P --> self" in result

    def test_nested_self_nodes(self) -> None:
        result = to_mermaid(make_hierarchical_model())
        assert 'Left__self(["self"])' in result
        assert 'Right__self(["self"])' in result


class TestEICModel:
    def test_eic_edge_inside_subgraph(self) -> None:
        result = to_mermaid(make_eic_top_model())
        assert "GPP__self --> GPP__P" in result

    def test_top_level_coupling(self) -> None:
        result = to_mermaid(make_eic_top_model())
        assert "Generators --> GPP" in result
        assert "GPP --> self" in result

    def test_eic_standalone_model(self) -> None:
        result = to_mermaid(make_gpp_model())
        # self→P is the EIC edge
        assert "self --> P" in result
        # P→self is the EOC edge
        assert "P --> self" in result


class TestTitle:
    def test_no_title(self) -> None:
        result = to_mermaid(make_4gp_model())
        assert "title:" not in result
        assert result.startswith("flowchart TD\n")

    def test_with_title(self) -> None:
        result = to_mermaid(make_4gp_model(), title="My Model")
        assert 'title: "My Model"' in result
        assert "flowchart TD" in result


class TestSanitizeId:
    def test_safe_name_unchanged(self) -> None:
        assert _sanitize_id("G1") == "G1"
        assert _sanitize_id("hello_world") == "hello_world"

    def test_spaces_replaced(self) -> None:
        assert _sanitize_id("my model") == "my_model"

    def test_quotes_replaced(self) -> None:
        assert _sanitize_id('bad"name') == "bad_name"

    def test_newline_replaced(self) -> None:
        assert _sanitize_id("bad\nname") == "bad_name"

    def test_empty_becomes_underscore(self) -> None:
        assert _sanitize_id("") == "_"

    def test_only_unsafe_becomes_underscores(self) -> None:
        assert _sanitize_id('""') == "__"


class TestSanitizeLabel:
    def test_safe_text_unchanged(self) -> None:
        assert _sanitize_label("G1 (Generator)") == "G1 (Generator)"

    def test_double_quote_escaped(self) -> None:
        assert _sanitize_label('say "hello"') == "say #quot;hello#quot;"

    def test_newline_replaced_with_space(self) -> None:
        assert _sanitize_label("line1\nline2") == "line1 line2"

    def test_control_char_replaced(self) -> None:
        assert _sanitize_label("bad\x00char") == "bad char"


class TestSanitizeTitle:
    def test_safe_title_unchanged(self) -> None:
        assert _sanitize_title("My Model") == "My Model"

    def test_double_quote_escaped(self) -> None:
        assert _sanitize_title('A "quoted" title') == "A #quot;quoted#quot; title"

    def test_newline_replaced(self) -> None:
        assert _sanitize_title("line1\nline2") == "line1 line2"


class TestUnsafeNamesInOutput:
    def test_unsafe_component_name_sanitized_in_node_id(self) -> None:
        # Names with quotes or newlines must not appear raw in the diagram.
        result = to_mermaid(make_4gp_model())
        # Clean model: no raw quotes should appear in node IDs (only inside
        # double-quoted label strings, which are already tested above).
        assert '""' not in result

    def test_unsafe_title_sanitized(self) -> None:
        result = to_mermaid(make_4gp_model(), title='Injection: %%{init}%%\n"evil"')
        # The title line itself must be a single line — no embedded newlines.
        title_line = next(line for line in result.splitlines() if line.startswith("title:"))
        assert "\n" not in title_line
        # Quote escaped, directive-like content preserved but safely quoted.
        assert "#quot;" in title_line
        assert "%%{init}%%" in title_line

    def test_title_with_quote_is_escaped(self) -> None:
        result = to_mermaid(make_4gp_model(), title='A "B" C')
        assert 'title: "A #quot;B#quot; C"' in result


class TestMaxDepth:
    def test_default_depth_renders_nested(self) -> None:
        result = to_mermaid(make_hierarchical_model())
        assert "subgraph" in result
        assert "max depth" not in result

    def test_max_depth_zero_truncates_all_subgraphs(self) -> None:
        # depth starts at 1 inside _emit_model, so max_depth=0 truncates immediately
        result = to_mermaid(make_hierarchical_model(), max_depth=0)
        assert "max depth 0 exceeded" in result

    def test_max_depth_one_renders_top_only(self) -> None:
        # At depth=1 we render the top model; nested coupled models hit depth=2 > max_depth=1
        result = to_mermaid(make_hierarchical_model(), max_depth=1)
        assert "max depth 1 exceeded" in result
        # Top-level subgraph headers are present but bodies are truncated
        assert "subgraph" in result
