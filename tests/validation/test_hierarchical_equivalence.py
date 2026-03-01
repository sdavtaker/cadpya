"""Validate hierarchical model produces equivalent outputs to flat 4GP."""

from __future__ import annotations

from cadpya.engine.root_coordinator import RootCoordinator
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval
from tests.coupled_models.test_4gp import make_4gp_model
from tests.coupled_models.test_hierarchical import make_hierarchical_model

ZERO = Decimal.zero(3)
ZERO_TIME = Interval.closed(ZERO, ZERO)


class TestHierarchicalEquivalence:
    def test_same_distinct_output_values(self) -> None:
        """Both models should produce the same set of distinct output values.

        The hierarchical model has different branching structure (2 sub-coordinators
        vs 4 flat generators), so BFS explores paths in different order. But the
        set of possible outputs (job IDs) should be identical.
        """
        rc: RootCoordinator[Decimal] = RootCoordinator()
        max_steps = 200

        flat_log = rc.simulate(make_4gp_model(), ZERO_TIME, max_steps=max_steps)
        hier_log = rc.simulate(make_hierarchical_model(), ZERO_TIME, max_steps=max_steps)

        flat_outputs = {e.output for e in flat_log if e.output is not None}
        hier_outputs = {e.output for e in hier_log if e.output is not None}

        assert flat_outputs == hier_outputs

    def test_both_produce_processor_outputs(self) -> None:
        """Both models should eventually have the processor fire and produce output."""
        rc: RootCoordinator[Decimal] = RootCoordinator()

        flat_log = rc.simulate(make_4gp_model(), ZERO_TIME, max_steps=200)
        hier_log = rc.simulate(make_hierarchical_model(), ZERO_TIME, max_steps=200)

        flat_has_output = any(e.output is not None for e in flat_log)
        hier_has_output = any(e.output is not None for e in hier_log)

        assert flat_has_output
        assert hier_has_output
