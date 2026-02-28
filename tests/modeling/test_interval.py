"""Tests for the Interval generic type."""

from __future__ import annotations

import pytest

from cadpya.modeling.decimal import Decimal
from cadpya.modeling.interval import Interval


def d(s: str) -> Decimal:
    """Shorthand for Decimal(3, s)."""
    return Decimal(3, s)


class TestFactoryMethods:
    def test_closed(self) -> None:
        iv = Interval.closed(d("0.997"), d("1.005"))
        assert iv.lower == d("0.997")
        assert iv.upper == d("1.005")
        assert iv.lower_closed is True
        assert iv.upper_closed is True
        assert str(iv) == "[0.997, 1.005]"

    def test_open(self) -> None:
        iv = Interval.open(d("0.000"), d("1.000"))
        assert iv.lower_closed is False
        assert iv.upper_closed is False
        assert str(iv) == "(0.000, 1.000)"

    def test_left_open(self) -> None:
        iv = Interval.left_open(d("0.000"), d("1.000"))
        assert iv.lower_closed is False
        assert iv.upper_closed is True
        assert str(iv) == "(0.000, 1.000]"

    def test_right_open(self) -> None:
        iv = Interval.right_open(d("0.000"), d("1.000"))
        assert iv.lower_closed is True
        assert iv.upper_closed is False
        assert str(iv) == "[0.000, 1.000)"

    def test_empty(self) -> None:
        iv = Interval.empty(d("0.000"))
        assert iv.is_empty() is True
        assert str(iv) == "empty"

    def test_right_open_inf(self) -> None:
        iv = Interval.right_open_inf(d("0.000"))
        assert iv.lower_closed is True
        assert iv.upper_closed is False
        assert iv.upper_inf == 1
        assert str(iv) == "[0.000, +inf)"

    def test_open_inf(self) -> None:
        iv = Interval.open_inf(d("1.000"))
        assert iv.lower_closed is False
        assert iv.upper_inf == 1
        assert str(iv) == "(1.000, +inf)"

    def test_hi_less_than_lo_raises(self) -> None:
        with pytest.raises(ValueError, match=r"lower.*upper"):
            Interval.closed(d("2.000"), d("1.000"))

    def test_point_interval(self) -> None:
        iv = Interval.closed(d("1.000"), d("1.000"))
        assert iv.lower == iv.upper
        assert not iv.is_empty()


class TestFrozen:
    def test_setattr_raises(self) -> None:
        iv = Interval.closed(d("0.000"), d("1.000"))
        with pytest.raises(AttributeError, match="immutable"):
            iv.foo = 42

    def test_delattr_raises(self) -> None:
        iv = Interval.closed(d("0.000"), d("1.000"))
        with pytest.raises(AttributeError, match="immutable"):
            del iv._lower


class TestIsEmpty:
    def test_empty_is_empty(self) -> None:
        assert Interval.empty(d("0.000")).is_empty() is True

    def test_closed_not_empty(self) -> None:
        assert Interval.closed(d("0.000"), d("1.000")).is_empty() is False

    def test_point_not_empty(self) -> None:
        assert Interval.closed(d("1.000"), d("1.000")).is_empty() is False

    def test_inf_not_empty(self) -> None:
        assert Interval.right_open_inf(d("0.000")).is_empty() is False


class TestMinkowskiAddition:
    def test_closed_plus_closed(self) -> None:
        a = Interval.closed(d("1.000"), d("2.000"))
        b = Interval.closed(d("0.500"), d("1.500"))
        result = a + b
        assert result == Interval.closed(d("1.500"), d("3.500"))

    def test_closed_plus_open_produces_open_sides(self) -> None:
        a = Interval.closed(d("1.000"), d("2.000"))
        b = Interval.open(d("0.000"), d("1.000"))
        result = a + b
        assert result.lower_closed is False
        assert result.upper_closed is False
        assert result.lower == d("1.000")
        assert result.upper == d("3.000")

    def test_closed_plus_left_open(self) -> None:
        a = Interval.closed(d("1.000"), d("2.000"))
        b = Interval.left_open(d("0.000"), d("1.000"))
        result = a + b
        assert result.lower_closed is False
        assert result.upper_closed is True

    def test_any_plus_empty(self) -> None:
        a = Interval.closed(d("1.000"), d("2.000"))
        b = Interval.empty(d("0.000"))
        result = a + b
        assert result.is_empty()

    def test_empty_plus_any(self) -> None:
        a = Interval.empty(d("0.000"))
        b = Interval.closed(d("1.000"), d("2.000"))
        result = a + b
        assert result.is_empty()

    def test_closed_plus_inf(self) -> None:
        a = Interval.closed(d("1.000"), d("2.000"))
        b = Interval.right_open_inf(d("0.000"))
        result = a + b
        assert result.upper_inf == 1
        assert result.lower == d("1.000")
        assert result.lower_closed is True
        assert result.upper_closed is False

    def test_add_non_interval_returns_not_implemented(self) -> None:
        iv = Interval.closed(d("1.000"), d("2.000"))
        assert iv.__add__(42) is NotImplemented


class TestIntervalSubtraction:
    def test_closed_minus_closed(self) -> None:
        # [1, 2] - [0.3, 0.5] = [1-0.5, 2-0.3] = [0.5, 1.7]
        a = Interval.closed(d("1.000"), d("2.000"))
        b = Interval.closed(d("0.300"), d("0.500"))
        result = a - b
        assert result == Interval.closed(d("0.500"), d("1.700"))

    def test_subtraction_closure_rules(self) -> None:
        # result_lower_closed = a.lower_closed and b.upper_closed
        # result_upper_closed = a.upper_closed and b.lower_closed
        a = Interval.left_open(d("1.000"), d("2.000"))  # (1, 2]
        b = Interval.right_open(d("0.000"), d("1.000"))  # [0, 1)
        result = a - b
        # lower: a.lower_closed=False and b.upper_closed=False → False
        # upper: a.upper_closed=True and b.lower_closed=True → True
        assert result.lower_closed is False
        assert result.upper_closed is True

    def test_any_minus_empty(self) -> None:
        a = Interval.closed(d("1.000"), d("2.000"))
        b = Interval.empty(d("0.000"))
        result = a - b
        assert result.is_empty()

    def test_empty_minus_any(self) -> None:
        a = Interval.empty(d("0.000"))
        b = Interval.closed(d("1.000"), d("2.000"))
        result = a - b
        assert result.is_empty()

    def test_sub_non_interval_returns_not_implemented(self) -> None:
        iv = Interval.closed(d("1.000"), d("2.000"))
        assert iv.__sub__(42) is NotImplemented


class TestIsSubsetOf:
    def test_proper_subset(self) -> None:
        inner = Interval.closed(d("1.000"), d("2.000"))
        outer = Interval.closed(d("0.000"), d("3.000"))
        assert inner.is_subset_of(outer) is True

    def test_equal_is_subset(self) -> None:
        a = Interval.closed(d("1.000"), d("2.000"))
        b = Interval.closed(d("1.000"), d("2.000"))
        assert a.is_subset_of(b) is True

    def test_not_subset(self) -> None:
        a = Interval.closed(d("0.000"), d("3.000"))
        b = Interval.closed(d("1.000"), d("2.000"))
        assert a.is_subset_of(b) is False

    def test_empty_subset_of_anything(self) -> None:
        empty = Interval.empty(d("0.000"))
        other = Interval.closed(d("1.000"), d("2.000"))
        assert empty.is_subset_of(other) is True

    def test_nonempty_not_subset_of_empty(self) -> None:
        a = Interval.closed(d("1.000"), d("2.000"))
        empty = Interval.empty(d("0.000"))
        assert a.is_subset_of(empty) is False

    def test_open_subset_of_closed(self) -> None:
        inner = Interval.open(d("1.000"), d("2.000"))
        outer = Interval.closed(d("1.000"), d("2.000"))
        assert inner.is_subset_of(outer) is True

    def test_closed_not_subset_of_open_at_endpoints(self) -> None:
        inner = Interval.closed(d("1.000"), d("2.000"))
        outer = Interval.open(d("1.000"), d("2.000"))
        assert inner.is_subset_of(outer) is False

    def test_subset_of_inf(self) -> None:
        finite = Interval.closed(d("1.000"), d("2.000"))
        inf = Interval.right_open_inf(d("0.000"))
        assert finite.is_subset_of(inf) is True

    def test_not_subset_of_inf_when_lower_outside(self) -> None:
        finite = Interval.closed(d("1.000"), d("3.000"))
        inf = Interval.right_open_inf(d("2.000"))
        assert finite.is_subset_of(inf) is False


class TestIntersects:
    def test_overlapping(self) -> None:
        a = Interval.closed(d("0.000"), d("2.000"))
        b = Interval.closed(d("1.000"), d("3.000"))
        assert a.intersects(b) is True

    def test_non_overlapping(self) -> None:
        a = Interval.closed(d("0.000"), d("1.000"))
        b = Interval.closed(d("2.000"), d("3.000"))
        assert a.intersects(b) is False

    def test_touching_closed_endpoints(self) -> None:
        a = Interval.closed(d("0.000"), d("1.000"))
        b = Interval.closed(d("1.000"), d("2.000"))
        assert a.intersects(b) is True

    def test_touching_open_endpoints(self) -> None:
        a = Interval.right_open(d("0.000"), d("1.000"))  # [0, 1)
        b = Interval.closed(d("1.000"), d("2.000"))  # [1, 2]
        assert a.intersects(b) is False

    def test_with_empty(self) -> None:
        a = Interval.closed(d("0.000"), d("1.000"))
        empty = Interval.empty(d("0.000"))
        assert a.intersects(empty) is False

    def test_both_empty(self) -> None:
        a = Interval.empty(d("0.000"))
        b = Interval.empty(d("0.000"))
        assert a.intersects(b) is False

    def test_with_inf(self) -> None:
        a = Interval.right_open_inf(d("0.000"))
        b = Interval.closed(d("100.000"), d("200.000"))
        assert a.intersects(b) is True


class TestEquality:
    def test_equal_intervals(self) -> None:
        a = Interval.closed(d("1.000"), d("2.000"))
        b = Interval.closed(d("1.000"), d("2.000"))
        assert a == b

    def test_different_bounds(self) -> None:
        a = Interval.closed(d("1.000"), d("2.000"))
        b = Interval.closed(d("1.000"), d("3.000"))
        assert a != b

    def test_different_closure(self) -> None:
        a = Interval.closed(d("1.000"), d("2.000"))
        b = Interval.open(d("1.000"), d("2.000"))
        assert a != b

    def test_both_empty(self) -> None:
        a = Interval.empty(d("0.000"))
        b = Interval.empty(d("1.000"))
        assert a == b

    def test_empty_vs_non_empty(self) -> None:
        a = Interval.empty(d("0.000"))
        b = Interval.closed(d("0.000"), d("0.000"))
        assert a != b

    def test_eq_non_interval_returns_not_implemented(self) -> None:
        iv = Interval.closed(d("0.000"), d("1.000"))
        assert iv.__eq__(42) is NotImplemented


class TestHash:
    def test_equal_intervals_equal_hash(self) -> None:
        a = Interval.closed(d("1.000"), d("2.000"))
        b = Interval.closed(d("1.000"), d("2.000"))
        assert hash(a) == hash(b)

    def test_empty_intervals_equal_hash(self) -> None:
        a = Interval.empty(d("0.000"))
        b = Interval.empty(d("999.000"))
        assert hash(a) == hash(b)

    def test_usable_in_set(self) -> None:
        s = {Interval.closed(d("1.000"), d("2.000")), Interval.closed(d("1.000"), d("2.000"))}
        assert len(s) == 1


class TestStringRepresentations:
    def test_closed_str(self) -> None:
        assert str(Interval.closed(d("0.997"), d("1.005"))) == "[0.997, 1.005]"

    def test_empty_str(self) -> None:
        assert str(Interval.empty(d("0.000"))) == "empty"

    def test_inf_str(self) -> None:
        assert str(Interval.right_open_inf(d("0.000"))) == "[0.000, +inf)"

    def test_closed_repr(self) -> None:
        iv = Interval.closed(d("0.997"), d("1.005"))
        assert repr(iv) == "Interval([Decimal(3, '0.997'), Decimal(3, '1.005')])"

    def test_empty_repr(self) -> None:
        assert "empty" in repr(Interval.empty(d("0.000")))

    def test_inf_repr(self) -> None:
        iv = Interval.right_open_inf(d("0.000"))
        assert "+inf" in repr(iv)


class TestIntersection:
    def test_overlapping_closed(self) -> None:
        a = Interval.closed(d("1.000"), d("3.000"))
        b = Interval.closed(d("2.000"), d("4.000"))
        result = a.intersection(b)
        assert result == Interval.closed(d("2.000"), d("3.000"))

    def test_non_overlapping(self) -> None:
        a = Interval.closed(d("0.000"), d("1.000"))
        b = Interval.closed(d("2.000"), d("3.000"))
        assert a.intersection(b).is_empty()

    def test_with_empty(self) -> None:
        a = Interval.closed(d("0.000"), d("1.000"))
        empty = Interval.empty(d("0.000"))
        assert a.intersection(empty).is_empty()
        assert empty.intersection(a).is_empty()

    def test_one_contains_other(self) -> None:
        outer = Interval.closed(d("0.000"), d("4.000"))
        inner = Interval.closed(d("1.000"), d("3.000"))
        assert outer.intersection(inner) == inner
        assert inner.intersection(outer) == inner

    def test_touching_closed_endpoints(self) -> None:
        a = Interval.closed(d("0.000"), d("1.000"))
        b = Interval.closed(d("1.000"), d("2.000"))
        result = a.intersection(b)
        assert result == Interval.closed(d("1.000"), d("1.000"))
        assert result.is_punctual()

    def test_touching_open_endpoints_empty(self) -> None:
        a = Interval.right_open(d("0.000"), d("1.000"))
        b = Interval.closed(d("1.000"), d("2.000"))
        assert a.intersection(b).is_empty()

    def test_mixed_closure(self) -> None:
        a = Interval.closed(d("0.000"), d("2.000"))
        b = Interval.open(d("1.000"), d("3.000"))
        result = a.intersection(b)
        # (1, 2] — open at 1 (from b), closed at 2 (from a since b has 3)
        assert result == Interval.left_open(d("1.000"), d("2.000"))

    def test_same_interval(self) -> None:
        a = Interval.closed(d("1.000"), d("2.000"))
        assert a.intersection(a) == a

    def test_with_inf(self) -> None:
        a = Interval.right_open_inf(d("1.000"))
        b = Interval.closed(d("2.000"), d("5.000"))
        result = a.intersection(b)
        assert result == Interval.closed(d("2.000"), d("5.000"))

    def test_intersection_closure_both_open(self) -> None:
        a = Interval.open(d("0.000"), d("2.000"))
        b = Interval.open(d("1.000"), d("3.000"))
        result = a.intersection(b)
        assert result == Interval.open(d("1.000"), d("2.000"))


class TestIsPunctual:
    def test_point_interval(self) -> None:
        assert Interval.closed(d("1.000"), d("1.000")).is_punctual() is True

    def test_range_interval(self) -> None:
        assert Interval.closed(d("1.000"), d("2.000")).is_punctual() is False

    def test_empty(self) -> None:
        assert Interval.empty(d("0.000")).is_punctual() is False

    def test_open_same_bounds(self) -> None:
        # (1, 1) is empty conceptually but not marked as empty
        assert Interval.open(d("1.000"), d("1.000")).is_punctual() is False

    def test_inf(self) -> None:
        assert Interval.right_open_inf(d("0.000")).is_punctual() is False

    def test_int_punctual(self) -> None:
        assert Interval.closed(1, 1).is_punctual() is True

    def test_int_not_punctual(self) -> None:
        assert Interval.closed(1, 2).is_punctual() is False


class TestIntersectionEdgeCases:
    """Test intersection edge cases for coverage."""

    def test_left_open_with_closed_at_same_lower(self) -> None:
        a = Interval.left_open(d("1.000"), d("3.000"))  # (1, 3]
        b = Interval.closed(d("1.000"), d("2.000"))  # [1, 2]
        result = a.intersection(b)
        # Lower: max of (1 open, [1 closed) → (1 open
        # Upper: min of 3], 2] → 2]
        assert result == Interval.left_open(d("1.000"), d("2.000"))

    def test_right_open_with_open(self) -> None:
        a = Interval.right_open(d("0.000"), d("2.000"))  # [0, 2)
        b = Interval.open(d("1.000"), d("3.000"))  # (1, 3)
        result = a.intersection(b)
        assert result == Interval.open(d("1.000"), d("2.000"))

    def test_point_intersect_with_range(self) -> None:
        a = Interval.closed(d("1.000"), d("1.000"))  # [1, 1]
        b = Interval.closed(d("0.000"), d("2.000"))  # [0, 2]
        result = a.intersection(b)
        assert result == a
        assert result.is_punctual()


class TestIntersectionMoreEdgeCases:
    def test_intersection_open_inf_with_closed(self) -> None:
        a = Interval.open_inf(d("0.000"))  # (0, +inf)
        b = Interval.closed(d("0.000"), d("2.000"))  # [0, 2]
        result = a.intersection(b)
        assert result == Interval.left_open(d("0.000"), d("2.000"))

    def test_right_open_inf_same_lower(self) -> None:
        a = Interval.right_open_inf(d("1.000"))
        b = Interval.closed(d("1.000"), d("1.000"))
        result = a.intersection(b)
        assert result.is_punctual()
        assert result == Interval.closed(d("1.000"), d("1.000"))

    def test_intersection_both_empty(self) -> None:
        a = Interval.empty(d("0.000"))
        b = Interval.empty(d("0.000"))
        assert a.intersection(b).is_empty()


class TestCopySupport:
    """Test that immutable types support deepcopy."""

    def test_interval_copy_returns_self(self) -> None:
        import copy

        iv = Interval.closed(d("1.000"), d("2.000"))
        assert copy.copy(iv) is iv
        assert copy.deepcopy(iv) is iv

    def test_empty_copy_returns_self(self) -> None:
        import copy

        iv = Interval.empty(d("0.000"))
        assert copy.deepcopy(iv) is iv


class TestIntersectionInfinity:
    """Test intersection with infinity bounds."""

    def test_both_inf_upper(self) -> None:
        a = Interval.right_open_inf(d("1.000"))
        b = Interval.right_open_inf(d("2.000"))
        result = a.intersection(b)
        assert result.lower == d("2.000")
        assert result.lower_closed is True
        assert result.upper_inf == 1
        assert not result.is_empty()

    def test_inf_with_finite(self) -> None:
        a = Interval.right_open_inf(d("0.000"))
        b = Interval.closed(d("1.000"), d("3.000"))
        result = a.intersection(b)
        assert result == b

    def test_both_inf(self) -> None:
        a = Interval.right_open_inf(d("0.000"))
        b = Interval.right_open_inf(d("1.000"))
        result = a.intersection(b)
        assert result.lower == d("1.000")
        assert result.lower_closed is True
        assert result.upper_inf == 1


class TestWithIntegers:
    """Verify Interval works with plain int (for Counter output, Processor jobs)."""

    def test_closed_int(self) -> None:
        iv = Interval.closed(1, 5)
        assert iv.lower == 1
        assert iv.upper == 5

    def test_minkowski_add_int(self) -> None:
        a = Interval.closed(1, 3)
        b = Interval.closed(10, 20)
        result = a + b
        assert result == Interval.closed(11, 23)

    def test_sub_int(self) -> None:
        a = Interval.closed(10, 20)
        b = Interval.closed(1, 3)
        # [10-3, 20-1] = [7, 19]
        result = a - b
        assert result == Interval.closed(7, 19)
