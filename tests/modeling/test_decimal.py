"""Tests for the Decimal fixed-point type."""

from __future__ import annotations

import pytest

from cadpya.modeling.decimal import Decimal


class TestConstruction:
    def test_from_string_exact_scale(self) -> None:
        d = Decimal(3, "0.997")
        assert str(d) == "0.997"
        assert d.scale == 3

    def test_from_string_fewer_digits_pads_zeros(self) -> None:
        d = Decimal(3, "0.99")
        assert str(d) == "0.990"

    def test_from_string_trailing_zero_beyond_scale_ok(self) -> None:
        d = Decimal(3, "0.9970")
        assert str(d) == "0.997"

    def test_from_string_nonzero_beyond_scale_raises(self) -> None:
        with pytest.raises(ValueError, match="Non-zero digit"):
            Decimal(3, "0.9974")

    def test_from_string_nonzero_beyond_scale_raises_2(self) -> None:
        with pytest.raises(ValueError, match="Non-zero digit"):
            Decimal(3, "1.0005")

    def test_from_int(self) -> None:
        d = Decimal(3, 1)
        assert str(d) == "1.000"

    def test_from_int_factory(self) -> None:
        d = Decimal.from_int(3, 1)
        assert str(d) == "1.000"

    def test_from_str_factory(self) -> None:
        d = Decimal.from_str(3, "0.997")
        assert str(d) == "0.997"

    def test_zero_factory(self) -> None:
        d = Decimal.zero(3)
        assert str(d) == "0.000"

    def test_negative_scale_raises(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            Decimal(-1, "1.0")

    def test_scale_zero(self) -> None:
        d = Decimal(0, "42")
        assert str(d) == "42"
        assert d.scale == 0


class TestFrozen:
    def test_setattr_raises(self) -> None:
        d = Decimal(3, "1.000")
        with pytest.raises(AttributeError, match="immutable"):
            d.foo = 42  # type: ignore[attr-defined]

    def test_delattr_raises(self) -> None:
        d = Decimal(3, "1.000")
        with pytest.raises(AttributeError, match="immutable"):
            del d._scale  # type: ignore[misc]


class TestArithmetic:
    def test_add_same_scale(self) -> None:
        a = Decimal(3, "0.500")
        b = Decimal(3, "0.300")
        assert a + b == Decimal(3, "0.800")

    def test_sub_same_scale(self) -> None:
        a = Decimal(3, "1.005")
        b = Decimal(3, "0.200")
        assert a - b == Decimal(3, "0.805")

    def test_add_mismatched_scale_raises(self) -> None:
        a = Decimal(3, "0.500")
        b = Decimal(2, "0.50")
        with pytest.raises(ValueError, match="different scales"):
            a + b

    def test_sub_mismatched_scale_raises(self) -> None:
        a = Decimal(3, "0.500")
        b = Decimal(2, "0.50")
        with pytest.raises(ValueError, match="different scales"):
            a - b

    def test_add_result_is_quantized(self) -> None:
        a = Decimal(3, "0.001")
        b = Decimal(3, "0.001")
        result = a + b
        assert str(result) == "0.002"
        assert result.scale == 3

    def test_add_non_decimal_returns_not_implemented(self) -> None:
        d = Decimal(3, "1.000")
        result = d.__add__(42)
        assert result is NotImplemented

    def test_sub_non_decimal_returns_not_implemented(self) -> None:
        d = Decimal(3, "1.000")
        result = d.__sub__(42)
        assert result is NotImplemented


class TestComparison:
    def test_eq(self) -> None:
        assert Decimal(3, "0.997") == Decimal(3, "0.997")

    def test_not_eq(self) -> None:
        assert Decimal(3, "0.997") != Decimal(3, "0.998")

    def test_lt(self) -> None:
        assert Decimal(3, "0.997") < Decimal(3, "1.005")

    def test_le(self) -> None:
        assert Decimal(3, "0.997") <= Decimal(3, "0.997")
        assert Decimal(3, "0.997") <= Decimal(3, "1.005")

    def test_gt(self) -> None:
        assert Decimal(3, "1.005") > Decimal(3, "0.997")

    def test_ge(self) -> None:
        assert Decimal(3, "1.005") >= Decimal(3, "1.005")
        assert Decimal(3, "1.005") >= Decimal(3, "0.997")

    def test_eq_different_scales_raises(self) -> None:
        with pytest.raises(ValueError, match="different scales"):
            Decimal(3, "1.000") == Decimal(2, "1.00")  # noqa: B015

    def test_lt_different_scales_raises(self) -> None:
        with pytest.raises(ValueError, match="different scales"):
            Decimal(3, "1.000") < Decimal(2, "1.00")  # noqa: B015

    def test_eq_non_decimal_returns_not_implemented(self) -> None:
        assert Decimal(3, "1.000").__eq__(42) is NotImplemented


class TestHash:
    def test_equal_values_equal_hashes(self) -> None:
        a = Decimal(3, "0.997")
        b = Decimal(3, "0.997")
        assert hash(a) == hash(b)

    def test_usable_as_dict_key(self) -> None:
        d = {Decimal(3, "0.997"): "hello"}
        assert d[Decimal(3, "0.997")] == "hello"

    def test_usable_in_set(self) -> None:
        s = {Decimal(3, "0.997"), Decimal(3, "0.997")}
        assert len(s) == 1


class TestCrossScale:
    def test_as_lower_bound_pads_zeros(self) -> None:
        d = Decimal(1, "1.2")
        assert d.as_lower_bound(3) == Decimal(3, "1.200")

    def test_as_upper_bound_pads_nines(self) -> None:
        d = Decimal(1, "1.2")
        assert d.as_upper_bound(3) == Decimal(3, "1.299")

    def test_as_upper_bound_edge(self) -> None:
        d = Decimal(1, "1.9")
        assert d.as_upper_bound(3) == Decimal(3, "1.999")

    def test_as_lower_bound_same_scale_identity(self) -> None:
        d = Decimal(3, "1.200")
        assert d.as_lower_bound(3) is d

    def test_as_upper_bound_same_scale_identity(self) -> None:
        d = Decimal(3, "1.200")
        assert d.as_upper_bound(3) is d

    def test_as_lower_bound_coarser_raises(self) -> None:
        with pytest.raises(ValueError, match="coarser"):
            Decimal(3, "1.200").as_lower_bound(1)

    def test_as_upper_bound_coarser_raises(self) -> None:
        with pytest.raises(ValueError, match="coarser"):
            Decimal(3, "1.200").as_upper_bound(1)


class TestStringRepresentation:
    def test_str_shows_quantized_value(self) -> None:
        assert str(Decimal(3, "0.997")) == "0.997"

    def test_str_zero(self) -> None:
        assert str(Decimal(3, 0)) == "0.000"

    def test_repr_round_trippable(self) -> None:
        d = Decimal(3, "0.997")
        assert repr(d) == "Decimal(3, '0.997')"
        # Verify it's evaluable
        restored = eval(repr(d), {"Decimal": Decimal})
        assert restored == d
