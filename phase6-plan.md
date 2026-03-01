# Phase 6 Plan: End-to-End Validation

> **Action needed**: Copy this file to `phase6-plan.md` in the repo root before implementation.

## Context

Phase 5 (Coordinator + Root Coordinator + BFS branching) is merged. Phase 6 validates the full simulator against the paper's 4GP case study (Tables 1-5 in `uadevs-paper.tex`) and confirms branching behavior matches theoretical expectations.

### Bug discovered: missing non-punctual skip branch

During analysis of the paper's step 8 (line 1097 of `uadevs-paper.tex`), I found that the current `compute_branches` implementation is incomplete for non-punctual limits. The paper states:

> "the simulation is branched in five scenarios, one per each Generator that could be advanced plus one for the case none of them advance"

At step 8 (after G1→G2→G3→G4→P→P→P), the generators' t_next = [1.994, 2.010] overlaps with P's t_next = [1.997, 2.005]. The limit is computed as [1.994, 1.997) — non-punctual, restricted by P's lower bound. Only the 4 generators are imminent in this limit (P's t_next starts at 1.997, outside the open-upper limit).

The paper says this creates **5 branches**: one for each generator firing + one "nothing" branch where no generator fires. The current code (coordinator.py lines 303-309) only creates the 4 generator branches — **no skip/nothing branch**.

The "nothing" branch is important: it represents the scenario where the event happens *after* the limit interval. After executing the skip branch, engines' t_next lower bounds are restricted to exclude the limit interval, and simulation continues with narrower intervals.

---

## Step 1: Fix non-punctual skip branch + `_subtract_limit`

**Files**: `src/cadpya/engine/coordinator.py`, `tests/engine/test_coordinator.py`

### 1a. Add skip branch for non-punctual limits

In `compute_branches` (line 303-309), after building the list of branches for non-punctual limits, add a skip branch when the limit is a proper subset of any imminent's t_next:

```python
# Current (lines 303-309):
# Non-punctual: one branch per imminent in the limit
relevant = [
    name for name in imminents
    if (tn_ := self._engines[name].t_next) is not None and tn_.intersects(limit)
]
return [BranchAction(engine_name=name, limit=limit) for name in relevant]

# Fixed:
relevant = [
    name for name in imminents
    if (tn_ := self._engines[name].t_next) is not None and tn_.intersects(limit)
]
branches = [BranchAction(engine_name=name, limit=limit) for name in relevant]
# "Nothing fires in this limit" branch — when limit is strictly inside
# any imminent's t_next, the event could happen later instead
any_could_skip = any(
    (tn_ := self._engines[name].t_next) is not None and limit != tn_
    for name in relevant
)
if any_could_skip:
    branches.append(BranchAction(engine_name="", limit=limit))
return branches
```

### 1b. Generalize `_subtract_limit` for non-punctual limits

Current `_subtract_limit` (lines 329-347) only handles punctual limits (`[v, v]` → opens lower bound). For non-punctual limits like `[a, b)`, we need to restrict t_next's lower bound to at least `b`:

- If limit is punctual and `tn.lower == limit.lower`: open the lower bound (existing logic)
- If limit is non-punctual: set t_next lower to `limit.upper` with closedness = `not limit.upper_closed`
  - Example: limit = `[1.994, 1.997)` (upper_closed=False), engine t_next = `[1.994, 2.010]`
  - New t_next = `[1.997, 2.010]` (lower = 1.997, lower_closed = True, since limit upper was open)

### 1c. New tests in `tests/engine/test_coordinator.py`

- `test_non_punctual_skip_branch_created`: Build a model where limit is non-punctual and strictly inside t_next → verify skip branch (engine_name="") is in the returned branches
- `test_non_punctual_subtract_limit`: Execute skip branch with non-punctual limit → verify engines' t_next lower bound is restricted correctly
- `test_no_skip_when_limit_equals_t_next`: When limit == engine's t_next (event must happen in this interval) → no skip branch

---

## Step 2: Table 1-5 validation tests

**File**: `tests/validation/test_4gp_tables.py` (new)

Approach: Drive the Coordinator directly with `compute_branches()` / `execute_branch()` for deterministic single-branch execution. Inspect engine states via `coord.engines["G1"]` (Simulator instances with `.model.state_interval`, `.t_last`, `.t_next`).

### Constants (from basic_models)

```
PERIOD = [0.997, 1.005]           # Generator period
PROCESSING_TIME = 0.250           # Processor service time
ZERO_STATE = [0, 0]               # Generator initial state
ZERO_TOCJ = 0.000                 # Processor initial time-of-current-job
```

### test_table1_initialization (paper Table 1, `tab:init`)

Init 4GP Coordinator at t=[0,0]. Assert:

| Component | state | t_last | t_next |
|-----------|-------|--------|--------|
| G1-G4 | `[0, 0]` | `[0, 0]` | `[0.997, 1.005]` |
| P | `[<0,()>, <0,()>]` | `[0, 0]` | `None` (passive) |

Coordinator: `t_last=[0,0]`, `t_next=[0.997, 1.005]`

### test_table2_after_g1_fires (paper Table 2, `tab:first-step`)

Init, compute_branches at PERIOD (returns 4 branches for G1-G4), execute G1's branch. Assert:

| Component | state | t_last | t_next |
|-----------|-------|--------|--------|
| G1 | `[0, 0]` | `[0.997, 1.005]` | `[1.994, 2.010]` |
| G2-G4 | `[0, 0]` | `[0, 0]` | `[0.997, 1.005]` |
| P | `[<0,(1)>, <0,(1)>]` | `[0.997, 1.005]` | `[1.247, 1.255]` |

Key calculation: P's t_next = [0.997, 1.005] + [0.250, 0.250] = [1.247, 1.255]

### test_table3_after_all_generators_fire (paper Table 3, `tab:four-steps`)

Execute G1→G2→G3→G4 in sequence (always pick alphabetically first branch for determinism). Assert:

| Component | state | t_last | t_next |
|-----------|-------|--------|--------|
| G1-G4 | `[0, 0]` | `[0.997, 1.005]` | `[1.994, 2.010]` |
| P | `[<0,(1,2,3,4)>, <0,(1,2,3,4)>]` | `[0.997, 1.005]` | `[1.247, 1.255]` |

### test_table4_after_processor_fires_three_times (paper Table 4, `tab:seven-steps`)

Continue from Table 3. P fires 3 times (outputs jobs 1, 2, 3). Assert:

| Component | state | t_last | t_next |
|-----------|-------|--------|--------|
| G1-G4 | `[0, 0]` | `[0.997, 1.005]` | `[1.994, 2.010]` |
| P | `[<0,(4)>, <0,(4)>]` | `[1.747, 1.755]` | `[1.997, 2.005]` |

Key calculations:
- P fires job 1: t_last=[1.247, 1.255], t_next=[1.497, 1.505]
- P fires job 2: t_last=[1.497, 1.505], t_next=[1.747, 1.755]
- P fires job 3: t_last=[1.747, 1.755], t_next=[1.997, 2.005]

### test_table5_nothing_branch (paper Table 5, `tab:eight-steps`)

Continue from Table 4. Compute branches at coord.t_next:
- Coordinator t_next = min(Gs' [1.994, 2.010], P's [1.997, 2.005]) = [1.994, 2.005]
- Limit = [1.994, 1.997) — restricted upper to P's lower bound (1.997, open)
- 5 branches: G1, G2, G3, G4, nothing

Execute the skip branch (engine_name=""). Assert:

| Component | state | t_last | t_next |
|-----------|-------|--------|--------|
| G1-G4 | `[0, 0]` | `[0.997, 1.005]` | `[1.997, 2.010]` |
| P | `[<0,(4)>, <0,(4)>]` | `[1.747, 1.755]` | `[1.997, 2.005]` |

Key: Generators' t_next lower changes from 1.994 to 1.997 (limit's upper bound excluded). P is unchanged (its t_next [1.997, 2.005] doesn't intersect limit [1.994, 1.997)).

**Note on paper's Table 5**: The paper shows P's state with tocj=0.25 in Table 5. This may represent a different branch path (where P receives an external_transition due to a generator firing). In the pure "nothing" branch, P should be unchanged. Need to verify during implementation — if the paper's Table 5 description on line 1099 says "none of the models advanced", then P's state should indeed be unchanged (tocj stays 0, not 0.25). The paper text says "the case in which none of the models advanced" which contradicts tocj=0.25. Will investigate.

---

## Step 3: Branch count validation

**File**: `tests/validation/test_4gp_branching.py` (new)

Use `RootCoordinator.simulate()` for full BFS runs. Count branches at each step level.

### test_first_wave_4_branches
- Run with max_steps=4
- Step 0 should have 4 log entries with components = {G1, G2, G3, G4}

### test_24_branches_after_all_generators
- Run with max_steps sufficient for all 4 generator waves
- After 4 steps in each branch: 4! = 24 distinct branch lineages
- Each lineage should have all 4 generators fired (in some permutation)
- Branch count progression: step 0 → 4, step 1 → 12, step 2 → 24, step 3 → 24

### test_120_branches_at_conflict_step
- After step 7 per branch (G×4 + P×3), the conflict creates 5 branches each → 24×5 = 120
- Requires the skip branch fix from Step 1
- Run with max_steps=200, max_branches=500
- The paper notes: "from our 120 branches, only 20 are different" — we don't merge yet (deferred), but we can verify 120 exist

---

## Step 4: Hierarchical equivalence

**File**: `tests/validation/test_hierarchical_equivalence.py` (new)

The hierarchical model (`tests/coupled_models/test_hierarchical.py::make_hierarchical_model`) nests generators in two sub-coupled models. It should produce the same observable behavior as the flat 4GP.

### test_same_eoc_outputs
- Run both models through RootCoordinator with same max_steps
- Collect all `(output)` values from log entries where output is not None
- Assert same multiset of output values

Note: Component names differ (flat uses "G1"/"P", hierarchical uses "Left"/"Right"/"P"), so we compare outputs only, not component names.

### test_same_branch_count_first_wave
- Both should produce the same number of branches at step 0 (2 for hierarchical since it has 2 sub-coordinators as immediate children, vs 4 for flat)
- Actually: hierarchical has Left and Right as children, each containing 2 generators. At the top level, both Left and Right are imminent → 2 branches (not 4). The branching within sub-coordinators happens internally. This is a structural difference but semantically equivalent.

---

## Step 5: Log structure validation

**File**: `tests/validation/test_log_structure.py` (new)

### test_parent_branch_refs_valid
- Run 4GP simulation with max_steps=50
- Every `parent_branch` must either be None (for root) or refer to a branch ID that appears in some log entry
- The root branch "0" must be reachable from any entry by following parent_branch chain

### test_branch_tree_acyclic
- Build parent map: `{branch_id: parent_branch_id}`
- Walk ancestor chain for each branch — must terminate at "0", no cycles

### test_step_numbers_non_decreasing
- Group log entries by branch
- Within each branch, step numbers should be non-decreasing

---

## File Summary

| File | Action |
|------|--------|
| `src/cadpya/engine/coordinator.py` | Fix: non-punctual skip branch + generalize `_subtract_limit` |
| `tests/engine/test_coordinator.py` | Add: 3 tests for non-punctual skip/subtract |
| `tests/validation/__init__.py` | Create (empty) |
| `tests/validation/test_4gp_tables.py` | Create: 5 tests (Tables 1-5) |
| `tests/validation/test_4gp_branching.py` | Create: 3 tests (branch counts) |
| `tests/validation/test_hierarchical_equivalence.py` | Create: 2 tests |
| `tests/validation/test_log_structure.py` | Create: 3 tests |

**Total: ~16 new tests**

## Verification

1. `scripts/check-all.sh` passes (ruff, mypy, pytest ≥90% coverage)
2. Tables 1-5 values match paper exactly
3. Branch counts: 4 → 24 → 120 at expected simulation steps
4. Hierarchical model produces equivalent outputs to flat 4GP
5. Log structure forms a valid acyclic tree
6. Non-punctual skip branch produces correct state restrictions
