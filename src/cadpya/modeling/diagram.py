"""Mermaid flowchart diagram generation for coupled models.

Produces a Mermaid flowchart string showing all components and couplings,
recursing into nested coupled models as subgraphs.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cadpya.modeling.coupled import CoupledModel

# Characters that are not safe in an unquoted Mermaid node identifier.
_UNSAFE_ID_RE = re.compile(r"[^A-Za-z0-9]")


def _sanitize_id(name: str) -> str:
    """Replace non-alphanumeric characters so a name is safe as a Mermaid node ID."""
    safe = _UNSAFE_ID_RE.sub("_", name)
    return safe or "_"


def _sanitize_label(text: str) -> str:
    """Escape text for use inside a Mermaid double-quoted label string."""
    # Strip control characters (including newlines); escape double quotes.
    text = "".join(ch if ch.isprintable() else " " for ch in text)
    return text.replace('"', "#quot;")


def _sanitize_title(text: str) -> str:
    """Sanitize text for the YAML frontmatter title field (double-quoted YAML string).

    In YAML double-quoted strings backslash introduces escape sequences, so
    backslashes must be escaped first before any other substitution.
    """
    # Escape backslashes first so later replacements don't introduce new sequences.
    text = text.replace("\\", "\\\\")
    text = "".join(ch if ch.isprintable() else " " for ch in text)
    return text.replace('"', "#quot;")


def to_mermaid(model: CoupledModel[Any], title: str = "", max_depth: int = 20) -> str:
    """Generate a Mermaid flowchart from a coupled model.

    Recursively expands nested coupled models into subgraphs up to
    ``max_depth`` levels.  Cycle detection (same model instance appearing on
    the current recursion path) stops infinite descent and emits a Mermaid
    comment instead.

    Component names and titles are sanitized before emission: characters that
    are unsafe in Mermaid identifiers are replaced with ``_``; double-quotes
    and control characters in node labels and the title are escaped.
    Edges are currently unlabeled (``src --> dst`` only).

    Args:
        model: the coupled model to diagram
        title: optional title displayed above the diagram
        max_depth: maximum nesting depth before truncation (default 20)

    Returns:
        A Mermaid flowchart string (paste into markdown or mermaid.live).
    """
    lines: list[str] = []
    if title:
        safe_title = _sanitize_title(title)
        lines.append("---")
        lines.append(f'title: "{safe_title}"')
        lines.append("---")
    lines.append("flowchart TD")
    _emit_model(model, prefix="", lines=lines, depth=1, max_depth=max_depth, visited=frozenset())
    return "\n".join(lines) + "\n"


def _node_id(prefix: str, name: str) -> str:
    """Build a unique Mermaid node ID from prefix and component name."""
    safe_name = _sanitize_id(name)
    if prefix:
        return f"{prefix}__{safe_name}"
    return safe_name


def _emit_model(
    model: CoupledModel[Any],
    prefix: str,
    lines: list[str],
    depth: int,
    max_depth: int,
    visited: frozenset[int],
) -> None:
    """Recursively emit Mermaid nodes and edges for a coupled model."""
    indent = "    " * depth
    model_id = id(model)

    if model_id in visited:
        lines.append(f"{indent}%% [diagram: cycle detected — model already on current path]")
        return
    if depth > max_depth:
        lines.append(f"{indent}%% [diagram: max depth {max_depth} exceeded]")
        return

    visited = visited | {model_id}

    # Emit nodes for each component
    for name in sorted(model.components):
        spec = model.components[name]
        nid = _node_id(prefix, name)

        if spec.is_coupled:
            assert spec.coupled_model is not None  # guaranteed by is_coupled
            safe_label = _sanitize_label(name)
            lines.append(f'{indent}subgraph {nid}["{safe_label}"]')
            _emit_model(
                spec.coupled_model,
                prefix=nid,
                lines=lines,
                depth=depth + 1,
                max_depth=max_depth,
                visited=visited,
            )
            lines.append(f"{indent}end")
        else:
            class_name = _class_name(spec)
            safe_label = _sanitize_label(f"{name} ({class_name})")
            lines.append(f'{indent}{nid}["{safe_label}"]')

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
