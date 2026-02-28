"""Generic interval over any totally-ordered type.

Supports open/closed bounds, infinity, Minkowski addition, and
interval subtraction. Used throughout IA-DEVS for representing
uncertainty in state, time, input, and output values.
"""

from __future__ import annotations

from typing import Any


class Interval[T]:
    """Interval over a totally-ordered type ``T``.

    Supports open/closed bounds and +/-infinity on either end.
    Construct via factory class methods, not ``__init__`` directly.
    """

    __slots__ = (
        "_empty",
        "_lower",
        "_lower_closed",
        "_lower_inf",
        "_upper",
        "_upper_closed",
        "_upper_inf",
    )

    _lower: T
    _upper: T
    _lower_closed: bool
    _upper_closed: bool
    _lower_inf: int  # -1 for -inf, 0 for finite, +1 for +inf
    _upper_inf: int
    _empty: bool

    def __init__(
        self,
        lower: T,
        upper: T,
        *,
        lower_closed: bool,
        upper_closed: bool,
        lower_inf: int = 0,
        upper_inf: int = 0,
        empty: bool = False,
    ) -> None:
        object.__setattr__(self, "_lower", lower)
        object.__setattr__(self, "_upper", upper)
        object.__setattr__(self, "_lower_closed", lower_closed)
        object.__setattr__(self, "_upper_closed", upper_closed)
        object.__setattr__(self, "_lower_inf", lower_inf)
        object.__setattr__(self, "_upper_inf", upper_inf)
        object.__setattr__(self, "_empty", empty)

    # -- Copy support (immutable, return self) -------------------------------

    def __copy__(self) -> Interval[T]:
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> Interval[T]:
        memo[id(self)] = self
        return self

    # -- Frozen semantics --------------------------------------------------

    def __setattr__(self, _name: str, _value: object) -> None:
        msg = "Interval instances are immutable"
        raise AttributeError(msg)

    def __delattr__(self, _name: str) -> None:
        msg = "Interval instances are immutable"
        raise AttributeError(msg)

    # -- Properties --------------------------------------------------------

    @property
    def lower(self) -> T:
        return self._lower

    @property
    def upper(self) -> T:
        return self._upper

    @property
    def lower_closed(self) -> bool:
        return self._lower_closed

    @property
    def upper_closed(self) -> bool:
        return self._upper_closed

    @property
    def lower_inf(self) -> int:
        return self._lower_inf

    @property
    def upper_inf(self) -> int:
        return self._upper_inf

    # -- Factory methods ---------------------------------------------------

    @classmethod
    def closed(cls, lo: T, hi: T) -> Interval[T]:
        """Create closed interval ``[lo, hi]``."""
        if lo > hi:  # type: ignore[operator]
            msg = f"lower ({lo}) must be <= upper ({hi})"
            raise ValueError(msg)
        return cls(lo, hi, lower_closed=True, upper_closed=True)

    @classmethod
    def open(cls, lo: T, hi: T) -> Interval[T]:
        """Create open interval ``(lo, hi)``."""
        if lo > hi:  # type: ignore[operator]
            msg = f"lower ({lo}) must be <= upper ({hi})"
            raise ValueError(msg)
        return cls(lo, hi, lower_closed=False, upper_closed=False)

    @classmethod
    def left_open(cls, lo: T, hi: T) -> Interval[T]:
        """Create left-open interval ``(lo, hi]``."""
        if lo > hi:  # type: ignore[operator]
            msg = f"lower ({lo}) must be <= upper ({hi})"
            raise ValueError(msg)
        return cls(lo, hi, lower_closed=False, upper_closed=True)

    @classmethod
    def right_open(cls, lo: T, hi: T) -> Interval[T]:
        """Create right-open interval ``[lo, hi)``."""
        if lo > hi:  # type: ignore[operator]
            msg = f"lower ({lo}) must be <= upper ({hi})"
            raise ValueError(msg)
        return cls(lo, hi, lower_closed=True, upper_closed=False)

    @classmethod
    def empty(cls, zero: T) -> Interval[T]:
        """Create empty interval (represents passive / empty set)."""
        return cls(zero, zero, lower_closed=False, upper_closed=False, empty=True)

    @classmethod
    def right_open_inf(cls, lo: T) -> Interval[T]:
        """Create ``[lo, +inf)``."""
        return cls(lo, lo, lower_closed=True, upper_closed=False, upper_inf=1)

    @classmethod
    def open_inf(cls, lo: T) -> Interval[T]:
        """Create ``(lo, +inf)``."""
        return cls(lo, lo, lower_closed=False, upper_closed=False, upper_inf=1)

    # -- Queries -----------------------------------------------------------

    def is_empty(self) -> bool:
        """Return True if this is the empty interval."""
        return self._empty

    def is_subset_of(self, other: Interval[T]) -> bool:
        """Return True if ``self`` is a subset of ``other``.

        The empty set is a subset of everything.
        """
        if self._empty:
            return True
        if other._empty:
            return False

        # Check lower bound: self.lower >= other.lower (with closure)
        if not self._lower_ge_bound(other):
            return False
        # Check upper bound: self.upper <= other.upper (with closure)
        return self._upper_le_bound(other)

    def intersects(self, other: Interval[T]) -> bool:
        """Return True if the intersection is non-empty."""
        if self._empty or other._empty:
            return False

        # Check if self.upper < other.lower or self.lower > other.upper
        # accounting for closure and infinity
        return not (self._is_strictly_below(other) or other._is_strictly_below(self))

    def intersection(self, other: Interval[T]) -> Interval[T]:
        """Compute the intersection of two intervals.

        Returns the empty interval if they don't overlap.
        """
        if self._empty or other._empty:
            return Interval.empty(self._lower)
        if not self.intersects(other):
            return Interval.empty(self._lower)

        # Lower bound: max of the two lowers
        lo, lo_closed, lo_inf = _max_lower(self, other)
        # Upper bound: min of the two uppers
        hi, hi_closed, hi_inf = _min_upper(self, other)

        return Interval(
            lo,
            hi,
            lower_closed=lo_closed,
            upper_closed=hi_closed,
            lower_inf=lo_inf,
            upper_inf=hi_inf,
        )

    def is_punctual(self) -> bool:
        """Return True if this interval contains exactly one point."""
        return (
            not self._empty
            and self._lower_inf == 0
            and self._upper_inf == 0
            and self._lower_closed
            and self._upper_closed
            and self._lower == self._upper
        )

    # -- Arithmetic --------------------------------------------------------

    def __add__(self, other: object) -> Interval[T]:
        """Minkowski addition: ``[a,b] + [c,d] = [a+c, b+d]``."""
        if not isinstance(other, Interval):
            return NotImplemented
        if self._empty or other._empty:
            return Interval.empty(self._lower)

        lo = self._lower + other._lower
        hi = self._upper + other._upper
        lo_closed = self._lower_closed and other._lower_closed
        hi_closed = self._upper_closed and other._upper_closed
        lo_inf = _combine_inf(self._lower_inf, other._lower_inf)
        hi_inf = _combine_inf(self._upper_inf, other._upper_inf)
        return Interval(
            lo,
            hi,
            lower_closed=lo_closed,
            upper_closed=hi_closed,
            lower_inf=lo_inf,
            upper_inf=hi_inf,
        )

    def __sub__(self, other: object) -> Interval[T]:
        """Interval subtraction: ``[a,b] - [c,d] = [a-d, b-c]``."""
        if not isinstance(other, Interval):
            return NotImplemented
        if self._empty or other._empty:
            return Interval.empty(self._lower)

        # Note the cross: subtract upper from lower and vice versa
        lo = self._lower - other._upper
        hi = self._upper - other._lower
        lo_closed = self._lower_closed and other._upper_closed
        hi_closed = self._upper_closed and other._lower_closed
        lo_inf = _combine_inf(self._lower_inf, other._upper_inf)
        hi_inf = _combine_inf(self._upper_inf, other._lower_inf)
        return Interval(
            lo,
            hi,
            lower_closed=lo_closed,
            upper_closed=hi_closed,
            lower_inf=lo_inf,
            upper_inf=hi_inf,
        )

    # -- Equality ----------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Interval):
            return NotImplemented
        if self._empty and other._empty:
            return True
        if self._empty or other._empty:
            return False
        return (
            self._lower == other._lower
            and self._upper == other._upper
            and self._lower_closed == other._lower_closed
            and self._upper_closed == other._upper_closed
            and self._lower_inf == other._lower_inf
            and self._upper_inf == other._upper_inf
        )

    def __hash__(self) -> int:
        if self._empty:
            return hash(("empty",))
        return hash(
            (
                self._lower,
                self._upper,
                self._lower_closed,
                self._upper_closed,
                self._lower_inf,
                self._upper_inf,
            )
        )

    # -- String representations --------------------------------------------

    def __repr__(self) -> str:
        if self._empty:
            return f"Interval.empty({self._lower!r})"
        lb = "[" if self._lower_closed else "("
        rb = "]" if self._upper_closed else ")"
        lo = "-inf" if self._lower_inf == -1 else repr(self._lower)
        hi = "+inf" if self._upper_inf == 1 else repr(self._upper)
        return f"Interval({lb}{lo}, {hi}{rb})"

    def __str__(self) -> str:
        if self._empty:
            return "empty"
        lb = "[" if self._lower_closed else "("
        rb = "]" if self._upper_closed else ")"
        lo = "-inf" if self._lower_inf == -1 else str(self._lower)
        hi = "+inf" if self._upper_inf == 1 else str(self._upper)
        return f"{lb}{lo}, {hi}{rb}"

    # -- Internal helpers --------------------------------------------------

    def _lower_ge_bound(self, other: Interval[T]) -> bool:
        """Check if self's lower bound >= other's lower bound."""
        # -inf is always <= anything
        if other._lower_inf == -1:
            return True
        if self._lower_inf == -1:
            return False
        # +inf cases
        if self._lower_inf == 1:
            return True
        if other._lower_inf == 1:
            return False
        # Both finite
        if self._lower > other._lower:  # type: ignore[operator]
            return True
        if self._lower < other._lower:  # type: ignore[operator]
            return False
        # Equal values: check closure
        # (v is "higher" than [v — an open lower bound excludes v, so it starts above.
        # self_lower >= other_lower fails only when self includes v but other doesn't:
        # i.e. self is [v (closed) and other is (v (open) → self starts lower → False.
        return not (self._lower_closed and not other._lower_closed)

    def _upper_le_bound(self, other: Interval[T]) -> bool:
        """Check if self's upper bound <= other's upper bound."""
        if other._upper_inf == 1:
            return True
        if self._upper_inf == 1:
            return False
        if other._upper_inf == -1:
            return False
        if self._upper_inf == -1:
            return True
        # Both finite
        if self._upper < other._upper:  # type: ignore[operator]
            return True
        if self._upper > other._upper:  # type: ignore[operator]
            return False
        # Equal values: check closure
        if other._upper_closed and not self._upper_closed:
            return True
        return not (not other._upper_closed and self._upper_closed)

    def _is_strictly_below(self, other: Interval[T]) -> bool:
        """Check if self is entirely below other (no overlap)."""
        # self.upper < other.lower (accounting for infinity and closure)
        if self._upper_inf == 1:
            return False
        if other._lower_inf == -1:
            return False
        if self._upper_inf == -1:
            return True
        if other._lower_inf == 1:
            return True
        # Both finite
        if self._upper < other._lower:  # type: ignore[operator]
            return True
        if self._upper > other._lower:  # type: ignore[operator]
            return False
        # Equal: strictly below only if at least one side is open
        return not (self._upper_closed and other._lower_closed)


def _combine_inf(a: int, b: int) -> int:
    """Combine infinity flags for addition. If either is inf, result is inf."""
    if a != 0:
        return a
    return b


def _max_lower[T](a: Interval[T], b: Interval[T]) -> tuple[T, bool, int]:
    """Return the max of two lower bounds as (value, closed, inf)."""
    # -inf < any finite
    if a._lower_inf == -1 and b._lower_inf == -1:
        return a._lower, a._lower_closed and b._lower_closed, -1
    if a._lower_inf == -1:
        return b._lower, b._lower_closed, b._lower_inf
    if b._lower_inf == -1:
        return a._lower, a._lower_closed, a._lower_inf
    # +inf cases
    if a._lower_inf == 1:
        return a._lower, a._lower_closed, 1
    if b._lower_inf == 1:
        return b._lower, b._lower_closed, 1
    # Both finite
    if a._lower > b._lower:  # type: ignore[operator]
        return a._lower, a._lower_closed, 0
    if b._lower > a._lower:  # type: ignore[operator]
        return b._lower, b._lower_closed, 0
    # Equal: closed only if both closed
    return a._lower, a._lower_closed and b._lower_closed, 0


def _min_upper[T](a: Interval[T], b: Interval[T]) -> tuple[T, bool, int]:
    """Return the min of two upper bounds as (value, closed, inf)."""
    # +inf > any finite
    if a._upper_inf == 1 and b._upper_inf == 1:
        return a._upper, a._upper_closed and b._upper_closed, 1
    if a._upper_inf == 1:
        return b._upper, b._upper_closed, b._upper_inf
    if b._upper_inf == 1:
        return a._upper, a._upper_closed, a._upper_inf
    # -inf cases
    if a._upper_inf == -1:
        return a._upper, a._upper_closed, -1
    if b._upper_inf == -1:
        return b._upper, b._upper_closed, -1
    # Both finite
    if a._upper < b._upper:  # type: ignore[operator]
        return a._upper, a._upper_closed, 0
    if b._upper < a._upper:  # type: ignore[operator]
        return b._upper, b._upper_closed, 0
    # Equal: closed only if both closed
    return a._upper, a._upper_closed and b._upper_closed, 0
