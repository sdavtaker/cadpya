"""Tests for Mermaid diagram generation."""

from __future__ import annotations

from cadpya.modeling.diagram import to_mermaid
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
        assert "title: My Model" in result
        assert "flowchart TD" in result
