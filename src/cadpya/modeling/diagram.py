"""Mermaid flowchart diagram generation for coupled models.

Produces a Mermaid flowchart string showing all components and couplings,
recursing into nested coupled models as subgraphs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cadpya.modeling.coupled import CoupledModel


def to_mermaid(model: CoupledModel[Any], title: str = "") -> str:
    """Generate a Mermaid flowchart from a coupled model.

    Recursively expands nested coupled models into subgraphs.
    Atomic components are shown as rectangles with the class name.
    The ``"self"`` boundary is shown as a stadium-shaped node when
    the model has EOC or EIC couplings.

    Args:
        model: the coupled model to diagram
        title: optional title displayed above the diagram

    Returns:
        A Mermaid flowchart string (paste into markdown or mermaid.live).
    """
    lines: list[str] = []
    if title:
        lines.append("---")
        lines.append(f"title: {title}")
        lines.append("---")
    lines.append("flowchart TD")
    _emit_model(model, prefix="", lines=lines, depth=1)
    return "\n".join(lines) + "\n"


def _node_id(prefix: str, name: str) -> str:
    """Build a unique Mermaid node ID from prefix and component name."""
    if prefix:
        return f"{prefix}__{name}"
    return name


def _emit_model(
    model: CoupledModel[Any],
    prefix: str,
    lines: list[str],
    depth: int,
) -> None:
    """Recursively emit Mermaid nodes and edges for a coupled model."""
    indent = "    " * depth

    # Emit nodes for each component
    for name in sorted(model.components):
        spec = model.components[name]
        nid = _node_id(prefix, name)

        if spec.is_coupled:
            lines.append(f'{indent}subgraph {nid}["{name}"]')
            _emit_model(spec.coupled_model, prefix=nid, lines=lines, depth=depth + 1)  # type: ignore[arg-type]
            lines.append(f"{indent}end")
        else:
            class_name = _class_name(spec)
            lines.append(f'{indent}{nid}["{name} ({class_name})"]')

    # Emit self boundary node if model has EOC or EIC
    has_self = "self" in model.influencers or any(
        dst == "self" or src == "self" for src, dst in model.translations
    )
    if has_self:
        self_id = _node_id(prefix, "self")
        lines.append(f'{indent}{self_id}(["self"])')

    # Emit edges from translations
    for src, dst in sorted(model.translations):
        src_id = _node_id(prefix, src)
        dst_id = _node_id(prefix, dst)
        lines.append(f"{indent}{src_id} --> {dst_id}")


def _class_name(spec: Any) -> str:
    """Extract a human-readable class name from a ComponentSpec."""
    factory = spec.model_factory
    if factory is None:
        return "Atomic"
    name: str = getattr(factory, "__name__", "")
    if name:
        return name
    # functools.partial or other wrapper
    wrapped = getattr(factory, "func", None)
    if wrapped is not None:
        return getattr(wrapped, "__name__", "Atomic")
    return "Atomic"
