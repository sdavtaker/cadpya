"""Tests for the IA-DEVS Coordinator (Algorithms 2-3)."""

from __future__ import annotations

import copy

from cadpya.basic_models.generator import PERIOD
from cadpya.engine.coordinator import Coordinator
from cadpya.engine.simulator import Simulator
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval

# Reuse GP model builder from coupled model tests
from tests.coupled_models.test_gp import make_gp_model

ZERO = Decimal.zero(3)
ZERO_TIME = Interval.closed(ZERO, ZERO)


def d(s: str) -> Decimal:
    return Decimal(3, s)


class TestCoordinatorInit:
    def test_gp_creates_two_engines(self) -> None:
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)
        assert set(coord.engines.keys()) == {"G", "P"}

    def test_gp_generator_engine_is_simulator(self) -> None:
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)
        assert isinstance(coord.engines["G"], Simulator)

    def test_gp_processor_engine_is_simulator(self) -> None:
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)
        assert isinstance(coord.engines["P"], Simulator)

    def test_gp_t_last_is_zero(self) -> None:
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)
        assert coord.t_last == ZERO_TIME

    def test_gp_t_next_is_generator_period(self) -> None:
        """Only G is active (P is passive), so t_next = G's t_next = PERIOD."""
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)
        assert coord.t_next == PERIOD


class TestCoordinatorGPSimulation:
    """Test GP model step by step through the Coordinator."""

    def test_compute_branches_first_step(self) -> None:
        """First step: only G is imminent, single branch."""
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)

        branches = coord.compute_branches(PERIOD)
        # G has t_next=PERIOD which is non-punctual, but only one imminent
        assert len(branches) == 1
        assert branches[0].engine_name == "G"

    def test_execute_first_step_routes_to_processor(self) -> None:
        """G fires, output routed to P via Z_{G,P}."""
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)

        branches = coord.compute_branches(PERIOD)
        output = coord.execute_branch(branches[0])
        # G's output goes to P (IC) and NOT to "self" (no EOC from G)
        assert output is None

    def test_after_first_step_processor_has_job(self) -> None:
        """After G fires, P should have job 1 in queue."""
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)

        branches = coord.compute_branches(PERIOD)
        coord.execute_branch(branches[0])

        p_sim = coord.engines["P"]
        assert isinstance(p_sim, Simulator)
        state = p_sim.model.state_interval
        assert state.lower.qj == (1,)

    def test_after_first_step_t_next_has_both(self) -> None:
        """After G fires, both G and P are active. t_next = min of both."""
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)

        branches = coord.compute_branches(PERIOD)
        coord.execute_branch(branches[0])

        # P wakes with tocj=0, ta = [0.250, 0.250]
        # P's t_next = PERIOD + [0.250, 0.250] = [1.247, 1.255]
        # G's t_next = PERIOD + PERIOD = [1.994, 2.010]
        # coord.t_next = min = P's t_next = [1.247, 1.255]
        assert coord.t_next is not None
        assert coord.t_next.lower == d("1.247")
        assert coord.t_next.upper == d("1.255")

    def test_second_step_processor_fires(self) -> None:
        """Second step: P fires, outputs job 1 via EOC."""
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)

        # Step 1: G fires
        branches = coord.compute_branches(PERIOD)
        coord.execute_branch(branches[0])

        # Step 2: P fires
        t_next2 = coord.t_next
        assert t_next2 is not None
        branches2 = coord.compute_branches(t_next2)
        assert len(branches2) == 1
        assert branches2[0].engine_name == "P"

        output = coord.execute_branch(branches2[0])
        # P has EOC → output should be the job ID
        assert output is not None
        assert output == Interval.closed(1, 1)


class TestCoordinatorXFunction:
    def test_x_function_not_used_for_gp(self) -> None:
        """GP has no EIC, so x_function is a no-op (but shouldn't crash)."""
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)
        coord.x_function(Interval.closed(1, 1), ZERO_TIME)
        # Should not change anything since no EIC
        assert coord.t_next == PERIOD


class TestCoordinatorAllPassive:
    def test_all_passive_t_next_none(self) -> None:
        """When all children are passive, t_next is None."""
        from cadpya.basic_models.processor import ProcessorState
        from tests.coupled_models.test_gp import _select_alphabetical

        # Two passive processors
        empty_proc = ProcessorState(tocj=Decimal.zero(3), qj=())
        from cadpya.basic_models.processor import Processor
        from cadpya.modeling.component import ComponentSpec
        from cadpya.modeling.coupled import CoupledModel

        model = CoupledModel(
            components={
                "P1": ComponentSpec.atomic(Processor, Interval.empty(empty_proc), ZERO_TIME),
                "P2": ComponentSpec.atomic(Processor, Interval.empty(empty_proc), ZERO_TIME),
            },
            influencers={
                "P1": frozenset(),
                "P2": frozenset(),
                "self": frozenset({"P1"}),
            },
            translations={
                ("P1", "self"): lambda y: y,
            },
            select=_select_alphabetical,
            zero_time=ZERO,
        )
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)
        assert coord.t_next is None

    def test_compute_branches_when_passive(self) -> None:
        """compute_branches returns empty when t_next is None."""
        from cadpya.basic_models.processor import ProcessorState
        from tests.coupled_models.test_gp import _select_alphabetical

        empty_proc = ProcessorState(tocj=Decimal.zero(3), qj=())
        from cadpya.basic_models.processor import Processor
        from cadpya.modeling.component import ComponentSpec
        from cadpya.modeling.coupled import CoupledModel

        model = CoupledModel(
            components={
                "P": ComponentSpec.atomic(Processor, Interval.empty(empty_proc), ZERO_TIME),
            },
            influencers={"P": frozenset(), "self": frozenset({"P"})},
            translations={("P", "self"): lambda y: y},
            select=_select_alphabetical,
            zero_time=ZERO,
        )
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)
        assert coord.compute_branches(ZERO_TIME) == []


class TestCoordinatorSubtractLimit:
    def test_subtract_limit_creates_fork(self) -> None:
        """When limit is punctual and matches t_next lower, skip branch opens lower bound."""
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)

        # G's t_next = [0.997, 1.005], create punctual at its lower bound
        punctual = Interval.closed(d("0.997"), d("0.997"))
        from cadpya.engine.coordinator import BranchAction

        coord.execute_branch(BranchAction(engine_name="", limit=punctual))
        # After subtract, G's t_next lower should be open at 0.997
        g_tn = coord.engines["G"].t_next
        assert g_tn is not None
        assert g_tn.lower == d("0.997")
        assert g_tn.lower_closed is False
        assert g_tn.upper == d("1.005")
        assert g_tn.upper_closed is True


class TestCoordinatorPunctualBranching:
    def test_gp_step2_has_punctual_path(self) -> None:
        """After G fires, both G and P are active with overlapping t_next.

        P's t_next = [1.247, 1.255], G's t_next = [1.994, 2.010].
        P is first imminent. limit = P's t_next = [1.247, 1.255] (non-punctual).
        Only P is imminent → single branch, no punctual split.
        """
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)

        # Step 1: G fires
        branches = coord.compute_branches(PERIOD)
        coord.execute_branch(branches[0])

        # Step 2: P is sole imminent
        assert coord.t_next is not None
        branches2 = coord.compute_branches(coord.t_next)
        assert len(branches2) == 1
        assert branches2[0].engine_name == "P"

    def test_single_imminent_with_punctual_t_next(self) -> None:
        """A single imminent with punctual t_next produces 1 branch."""
        from cadpya.basic_models.processor import Processor, ProcessorState
        from cadpya.modeling.component import ComponentSpec
        from cadpya.modeling.coupled import CoupledModel
        from tests.coupled_models.test_gp import _select_alphabetical

        # Processor with one job, starts at tocj=0 → ta = [0.250, 0.250]
        state = Interval.closed(
            ProcessorState(tocj=Decimal.zero(3), qj=(1,)),
            ProcessorState(tocj=Decimal.zero(3), qj=(1,)),
        )
        model = CoupledModel(
            components={
                "P": ComponentSpec.atomic(Processor, state, ZERO_TIME),
            },
            influencers={"P": frozenset(), "self": frozenset({"P"})},
            translations={("P", "self"): lambda y: y},
            select=_select_alphabetical,
            zero_time=ZERO,
        )
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)

        # P's t_next = [0.250, 0.250] — punctual
        assert coord.t_next is not None
        assert coord.t_next.is_punctual()

        branches = coord.compute_branches(coord.t_next)
        # Punctual limit with single imminent → 1 branch (no fork since
        # limit == chosen's t_next)
        assert len(branches) == 1
        assert branches[0].engine_name == "P"

        output = coord.execute_branch(branches[0])
        assert output is not None
        assert output == Interval.closed(1, 1)


class TestCoordinatorWithInfinity:
    """Test coordinator with models that have infinity in t_next."""

    def test_mixed_finite_and_inf_t_next(self) -> None:
        """One active engine with finite t_next, one with inf t_next."""
        from cadpya.basic_models.processor import Processor, ProcessorState
        from cadpya.modeling.component import ComponentSpec
        from cadpya.modeling.coupled import CoupledModel
        from tests.coupled_models.test_gp import _select_alphabetical

        empty_proc = ProcessorState(tocj=Decimal.zero(3), qj=())
        # P1 has one job, P2 is passive
        state_with_job = Interval.closed(
            ProcessorState(tocj=Decimal.zero(3), qj=(1,)),
            ProcessorState(tocj=Decimal.zero(3), qj=(1,)),
        )
        model = CoupledModel(
            components={
                "P1": ComponentSpec.atomic(Processor, state_with_job, ZERO_TIME),
                "P2": ComponentSpec.atomic(Processor, Interval.empty(empty_proc), ZERO_TIME),
            },
            influencers={
                "P1": frozenset(),
                "P2": frozenset(),
                "self": frozenset({"P1"}),
            },
            translations={("P1", "self"): lambda y: y},
            select=_select_alphabetical,
            zero_time=ZERO,
        )
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)
        # P1 is active, P2 is passive
        assert coord.t_next is not None
        assert coord.t_next.is_punctual()


class TestCoordinatorPunctualFork:
    def test_punctual_fork_when_limit_inside_t_next(self) -> None:
        """When limit is punctual but strictly inside chosen's t_next,
        compute_branches returns 2 actions: skip + main."""
        from cadpya.basic_models.generator import Generator
        from cadpya.modeling.component import ComponentSpec
        from cadpya.modeling.coupled import CoupledModel
        from tests.coupled_models.test_gp import _select_alphabetical

        # Single generator: t_next = [0.997, 1.005] (non-punctual)
        model = CoupledModel(
            components={
                "G": ComponentSpec.atomic(
                    Generator,
                    Interval.closed(Decimal.zero(3), Decimal.zero(3)),
                    ZERO_TIME,
                ),
            },
            influencers={"G": frozenset(), "self": frozenset({"G"})},
            translations={("G", "self"): lambda y: y},
            select=_select_alphabetical,
            zero_time=ZERO,
        )
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)

        # Call compute_branches with a punctual time inside t_next
        punctual_t = Interval.closed(d("1.000"), d("1.000"))
        branches = coord.compute_branches(punctual_t)
        # Limit = t_next ∩ t = [0.997, 1.005] ∩ [1.000, 1.000] = [1.000, 1.000]
        # punctual, and limit != G's t_next → fork branch + main branch
        assert len(branches) == 2
        assert branches[0].engine_name == ""  # skip/fork
        assert branches[1].engine_name == "G"  # main


class TestRestrictUpper:
    def test_restrict_upper_basic(self) -> None:
        from cadpya.engine.coordinator import _restrict_upper

        iv = Interval.closed(d("0.000"), d("2.000"))
        result = _restrict_upper(iv, d("1.000"), True)
        assert result.upper == d("1.000")
        assert result.upper_closed is False

    def test_restrict_upper_no_change(self) -> None:
        from cadpya.engine.coordinator import _restrict_upper

        iv = Interval.closed(d("0.000"), d("1.000"))
        result = _restrict_upper(iv, d("2.000"), True)
        assert result == iv

    def test_restrict_upper_equal_value(self) -> None:
        from cadpya.engine.coordinator import _restrict_upper

        iv = Interval.closed(d("0.000"), d("1.000"))
        result = _restrict_upper(iv, d("1.000"), True)
        assert result.upper == d("1.000")
        assert result.upper_closed is False


class TestCoordinatorNotInitialized:
    def test_t_last_raises_before_init(self) -> None:
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        import pytest

        with pytest.raises(RuntimeError, match="not initialized"):
            _ = coord.t_last


class TestCoordinatorDeepCopy:
    def test_deep_copy_independent(self) -> None:
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)

        clone = copy.deepcopy(coord)
        assert clone.t_next == coord.t_next

        # Advance original
        branches = coord.compute_branches(PERIOD)
        coord.execute_branch(branches[0])

        # Clone should not be affected
        assert clone.t_next == PERIOD

    def test_deep_copy_shares_coupled_model(self) -> None:
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)

        clone = copy.deepcopy(coord)
        assert clone._coupled_model is coord._coupled_model


class TestNonPunctualSkipBranch:
    def test_non_punctual_skip_branch_created(self) -> None:
        """When limit is non-punctual and strictly inside t_next, skip branch is added.

        After G1→G2→G3→G4→P→P→P in 4GP, the conflict produces a non-punctual
        limit where P is imminent. Since limit != P's t_next, a skip branch
        is created alongside the main P branch.
        """
        from tests.coupled_models.test_4gp import make_4gp_model

        model = make_4gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)

        # Fire all 4 generators, then P fires 3 times
        for _ in range(7):
            assert coord.t_next is not None
            branches = coord.compute_branches(coord.t_next)
            main = next(b for b in branches if b.engine_name)
            coord.execute_branch(main)

        # Conflict: P t_next=[1.973, 2.005], Gs t_next=[1.994, 2.010]
        # Limit = [1.973, 1.994) — P first imminent, restricted by Gs' lower
        assert coord.t_next is not None
        branches = coord.compute_branches(coord.t_next)
        # P + skip = 2 branches (Gs don't intersect this limit)
        assert len(branches) == 2
        assert branches[0].engine_name == "P"
        assert branches[1].engine_name == ""  # skip

    def test_non_punctual_subtract_limit(self) -> None:
        """After executing non-punctual skip branch, engines' t_next is restricted."""
        from tests.coupled_models.test_4gp import make_4gp_model

        model = make_4gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)

        # Fire all 4 generators, then P fires 3 times
        for _ in range(7):
            assert coord.t_next is not None
            branches = coord.compute_branches(coord.t_next)
            main = next(b for b in branches if b.engine_name)
            coord.execute_branch(main)

        assert coord.t_next is not None
        branches = coord.compute_branches(coord.t_next)
        skip = next(b for b in branches if b.engine_name == "")

        # Limit is [1.973, 1.994) — open upper
        assert skip.limit.lower == d("1.973")
        assert skip.limit.upper == d("1.994")
        assert skip.limit.upper_closed is False

        # Execute skip branch — P's t_next lower should be restricted
        coord.execute_branch(skip)

        p_eng = coord.engines["P"]
        assert p_eng.t_next is not None
        # P's t_next lower restricted from 1.973 to 1.994 (limit.upper, closed
        # because limit.upper_closed was False → not False = True)
        assert p_eng.t_next.lower == d("1.994")
        assert p_eng.t_next.lower_closed is True
        assert p_eng.t_next.upper == d("2.005")

    def test_no_skip_when_limit_equals_t_next(self) -> None:
        """No skip branch when limit == all engines' t_next."""
        model = make_gp_model()
        coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
        coord.init(ZERO_TIME)

        branches = coord.compute_branches(PERIOD)
        skip_branches = [b for b in branches if b.engine_name == ""]
        assert len(skip_branches) == 0
