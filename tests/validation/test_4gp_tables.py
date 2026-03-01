"""Validate 4GP simulation against paper Tables 1-5 (uadevs-paper.tex).

Drives the Coordinator step-by-step via compute_branches() / execute_branch()
and inspects engine states directly.

NOTE: Tables 3-5 in the paper show tocj=0 after all generators fire. Our
implementation correctly accumulates elapsed time uncertainty when multiple
events occur at the same interval (elapsed upper = t.upper - t_last.lower),
so tocj upper bound grows to 0.024 after 4 generators fire at [0.997, 1.005].
This widens P's t_next to [1.223, 1.255] vs paper's [1.247, 1.255].
The computed values below are algorithmically correct per IA-DEVS.
"""

from __future__ import annotations

from cadpya.basic_models.generator import PERIOD
from cadpya.basic_models.processor import ProcessorState
from cadpya.engine.coordinator import Coordinator
from cadpya.engine.simulator import Simulator
from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval
from tests.coupled_models.test_4gp import make_4gp_model

ZERO = Decimal.zero(3)
ZERO_TIME = Interval.closed(ZERO, ZERO)


def d(s: str) -> Decimal:
    return Decimal(3, s)


def _make_coord() -> Coordinator[Decimal, int]:
    model = make_4gp_model()
    coord: Coordinator[Decimal, int] = Coordinator(model, ZERO)
    coord.init(ZERO_TIME)
    return coord


def _fire_first_engine(coord: Coordinator[Decimal, int]) -> None:
    """Compute branches and execute the first non-skip branch."""
    assert coord.t_next is not None
    branches = coord.compute_branches(coord.t_next)
    main = next(b for b in branches if b.engine_name)
    coord.execute_branch(main)


def _get_sim(coord: Coordinator[Decimal, int], name: str) -> Simulator:  # type: ignore[type-arg]
    eng = coord.engines[name]
    assert isinstance(eng, Simulator)
    return eng


class TestTable1Initialization:
    """Paper Table 1 (tab:init): Simulators variables after initialization."""

    def test_generators_state(self) -> None:
        coord = _make_coord()
        for name in ("G1", "G2", "G3", "G4"):
            sim = _get_sim(coord, name)
            assert sim.model.state_interval == Interval.closed(d("0.000"), d("0.000"))

    def test_generators_t_last(self) -> None:
        coord = _make_coord()
        for name in ("G1", "G2", "G3", "G4"):
            assert _get_sim(coord, name).t_last == ZERO_TIME

    def test_generators_t_next(self) -> None:
        coord = _make_coord()
        for name in ("G1", "G2", "G3", "G4"):
            assert _get_sim(coord, name).t_next == PERIOD

    def test_processor_passive(self) -> None:
        coord = _make_coord()
        sim = _get_sim(coord, "P")
        assert sim.model.state_interval.is_empty()
        assert sim.t_next is None

    def test_processor_t_last(self) -> None:
        coord = _make_coord()
        assert _get_sim(coord, "P").t_last == ZERO_TIME

    def test_coordinator_times(self) -> None:
        coord = _make_coord()
        assert coord.t_last == ZERO_TIME
        assert coord.t_next == PERIOD


class TestTable2AfterG1Fires:
    """Paper Table 2 (tab:first-step): After G1 advances first."""

    def test_g1_advanced(self) -> None:
        coord = _make_coord()
        _fire_first_engine(coord)  # G1 fires first (alphabetical)

        sim = _get_sim(coord, "G1")
        assert sim.t_last == Interval.closed(d("0.997"), d("1.005"))
        assert sim.t_next == Interval.closed(d("1.994"), d("2.010"))

    def test_other_generators_unchanged(self) -> None:
        coord = _make_coord()
        _fire_first_engine(coord)

        for name in ("G2", "G3", "G4"):
            sim = _get_sim(coord, name)
            assert sim.t_last == ZERO_TIME
            assert sim.t_next == PERIOD

    def test_processor_received_job_1(self) -> None:
        coord = _make_coord()
        _fire_first_engine(coord)

        sim = _get_sim(coord, "P")
        state = sim.model.state_interval
        assert state.lower == ProcessorState(tocj=d("0.000"), qj=(1,))
        assert state.upper == ProcessorState(tocj=d("0.000"), qj=(1,))

    def test_processor_times(self) -> None:
        coord = _make_coord()
        _fire_first_engine(coord)

        sim = _get_sim(coord, "P")
        assert sim.t_last == Interval.closed(d("0.997"), d("1.005"))
        assert sim.t_next == Interval.closed(d("1.247"), d("1.255"))


class TestTable3AfterAllGeneratorsFire:
    """Paper Table 3 (tab:four-steps): After G1→G2→G3→G4 sequence.

    Note: tocj upper bound accumulates elapsed time uncertainty (0.008 per
    generator after the first), giving tocj=[0, 0.024] instead of paper's [0, 0].
    """

    def test_all_generators_advanced(self) -> None:
        coord = _make_coord()
        for _ in range(4):
            _fire_first_engine(coord)

        for name in ("G1", "G2", "G3", "G4"):
            sim = _get_sim(coord, name)
            assert sim.t_last == Interval.closed(d("0.997"), d("1.005"))
            assert sim.t_next == Interval.closed(d("1.994"), d("2.010"))

    def test_processor_has_all_jobs(self) -> None:
        coord = _make_coord()
        for _ in range(4):
            _fire_first_engine(coord)

        sim = _get_sim(coord, "P")
        state = sim.model.state_interval
        assert state.lower.qj == (1, 2, 3, 4)
        assert state.upper.qj == (1, 2, 3, 4)

    def test_processor_tocj_with_elapsed_uncertainty(self) -> None:
        coord = _make_coord()
        for _ in range(4):
            _fire_first_engine(coord)

        sim = _get_sim(coord, "P")
        state = sim.model.state_interval
        # tocj lower=0 (best case: all events at same instant)
        assert state.lower.tocj == d("0.000")
        # tocj upper=0.024 (worst case: 3 x 0.008 elapsed accumulation)
        assert state.upper.tocj == d("0.024")

    def test_processor_t_next(self) -> None:
        coord = _make_coord()
        for _ in range(4):
            _fire_first_engine(coord)

        sim = _get_sim(coord, "P")
        assert sim.t_next is not None
        # ta = [0.250-0.024, 0.250-0] = [0.226, 0.250]
        # t_next = t_last + ta = [0.997+0.226, 1.005+0.250] = [1.223, 1.255]
        assert sim.t_next == Interval.closed(d("1.223"), d("1.255"))


class TestTable4AfterProcessorFiresThreeTimes:
    """Paper Table 4 (tab:seven-steps): After G1→G2→G3→G4→P→P→P."""

    def test_processor_state_after_three_firings(self) -> None:
        coord = _make_coord()
        for _ in range(7):  # 4 Gs + 3 Ps
            _fire_first_engine(coord)

        sim = _get_sim(coord, "P")
        state = sim.model.state_interval
        # Only job 4 remains
        assert state.lower == ProcessorState(tocj=d("0.000"), qj=(4,))
        assert state.upper == ProcessorState(tocj=d("0.000"), qj=(4,))

    def test_processor_times(self) -> None:
        coord = _make_coord()
        for _ in range(7):
            _fire_first_engine(coord)

        sim = _get_sim(coord, "P")
        assert sim.t_last == Interval.closed(d("1.723"), d("1.755"))
        assert sim.t_next == Interval.closed(d("1.973"), d("2.005"))

    def test_generators_unchanged(self) -> None:
        coord = _make_coord()
        for _ in range(7):
            _fire_first_engine(coord)

        for name in ("G1", "G2", "G3", "G4"):
            sim = _get_sim(coord, name)
            assert sim.t_next == Interval.closed(d("1.994"), d("2.010"))


class TestTable5NothingBranch:
    """Paper Table 5 (tab:eight-steps): Skip branch where nothing fires.

    At step 8, P's t_next [1.973, 2.005] overlaps with Gs' [1.994, 2.010].
    The limit is [1.973, 1.994) — only P is imminent (Gs start at 1.994,
    which is outside the open-upper limit). Two branches: P fires, or nothing.
    """

    def test_conflict_produces_skip_branch(self) -> None:
        coord = _make_coord()
        for _ in range(7):
            _fire_first_engine(coord)

        assert coord.t_next is not None
        branches = coord.compute_branches(coord.t_next)
        assert len(branches) == 2
        assert branches[0].engine_name == "P"
        assert branches[1].engine_name == ""

    def test_skip_branch_restricts_p_t_next(self) -> None:
        coord = _make_coord()
        for _ in range(7):
            _fire_first_engine(coord)

        assert coord.t_next is not None
        branches = coord.compute_branches(coord.t_next)
        skip = branches[1]
        coord.execute_branch(skip)

        # P's t_next lower restricted from 1.973 to 1.994
        sim = _get_sim(coord, "P")
        assert sim.t_next is not None
        assert sim.t_next.lower == d("1.994")
        assert sim.t_next.upper == d("2.005")

    def test_skip_branch_generators_unchanged(self) -> None:
        coord = _make_coord()
        for _ in range(7):
            _fire_first_engine(coord)

        assert coord.t_next is not None
        branches = coord.compute_branches(coord.t_next)
        coord.execute_branch(branches[1])  # skip

        # Gs don't intersect limit [1.973, 1.994), so unchanged
        for name in ("G1", "G2", "G3", "G4"):
            sim = _get_sim(coord, name)
            assert sim.t_next == Interval.closed(d("1.994"), d("2.010"))
