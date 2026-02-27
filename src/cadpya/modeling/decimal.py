"""Fixed-point decimal with tracked significant digits.

Thin wrapper around stdlib decimal.Decimal that enforces a fixed number
of decimal places (the *scale*). Every arithmetic result is quantized
back to the declared scale so digits beyond it are never visible.
"""

from __future__ import annotations

import decimal as _stdlib_decimal
from functools import total_ordering

_ROUND = _stdlib_decimal.ROUND_HALF_EVEN


def _quantizer(scale: int) -> _stdlib_decimal.Decimal:
    """Return the quantizer for a given scale, e.g. Decimal('0.001') for scale=3."""
    return _stdlib_decimal.Decimal(10) ** -scale


def _validate_string_precision(s: str, scale: int) -> None:
    """Reject strings that don't have exactly ``scale`` decimal places.

    The user must write all significant digits explicitly — no silent
    zero-padding. Trailing zeros beyond the scale are tolerated.
    """
    if scale == 0:
        # scale=0 means no decimal point required
        if "." in s:
            _integer_part, _, frac = s.partition(".")
            if frac and frac.lstrip("0"):
                msg = (
                    f"Non-zero fractional digit(s) in '{s}' but scale is 0. "
                    f"Use an integer string."
                )
                raise ValueError(msg)
        return
    if "." not in s:
        msg = (
            f"String '{s}' has no decimal point but scale is {scale}. "
            f"Write exactly {scale} decimal places (e.g. '{s}." + "0" * scale + "')."
        )
        raise ValueError(msg)
    _integer_part, _, frac = s.partition(".")
    # Must have at least `scale` fractional digits
    if len(frac) < scale:
        msg = (
            f"String '{s}' has {len(frac)} decimal place(s) but scale is {scale}. "
            f"Write exactly {scale} decimal places to confirm significance."
        )
        raise ValueError(msg)
    # Reject non-zero digits beyond scale
    beyond = frac[scale:]
    if beyond and beyond.lstrip("0"):
        msg = (
            f"Non-zero digit(s) '{beyond.lstrip('0')}' beyond scale {scale} "
            f"in '{s}'. This is likely a typo — use exactly {scale} decimal places."
        )
        raise ValueError(msg)


@total_ordering
class Decimal:
    """Fixed-point decimal with tracked significant digits.

    Wraps stdlib ``decimal.Decimal`` and enforces a fixed number of
    decimal places (*scale*). All results are quantized to the scale
    after every operation — digits beyond it are masked.

    ``Decimal(3, "0.997")`` represents 0.997 with 3 significant
    decimal places.
    """

    __slots__ = ("_scale", "_value")

    _scale: int
    _value: _stdlib_decimal.Decimal

    def __init__(self, scale: int, value: str | int | _stdlib_decimal.Decimal) -> None:
        if scale < 0:
            msg = f"scale must be non-negative, got {scale}"
            raise ValueError(msg)
        if isinstance(value, str):
            _validate_string_precision(value, scale)
        q = _quantizer(scale)
        quantized = _stdlib_decimal.Decimal(value).quantize(q, rounding=_ROUND)
        object.__setattr__(self, "_scale", scale)
        object.__setattr__(self, "_value", quantized)

    # -- Frozen semantics --------------------------------------------------

    def __setattr__(self, _name: str, _value: object) -> None:
        msg = "Decimal instances are immutable"
        raise AttributeError(msg)

    def __delattr__(self, _name: str) -> None:
        msg = "Decimal instances are immutable"
        raise AttributeError(msg)

    # -- Properties --------------------------------------------------------

    @property
    def scale(self) -> int:
        return self._scale

    @property
    def value(self) -> _stdlib_decimal.Decimal:
        return self._value

    # -- Factory methods ---------------------------------------------------

    @classmethod
    def from_str(cls, scale: int, s: str) -> Decimal:
        """Create from string. ``Decimal.from_str(3, "0.997")``."""
        return cls(scale, s)

    @classmethod
    def from_int(cls, scale: int, whole: int) -> Decimal:
        """Create from whole units. ``Decimal.from_int(3, 1)`` == 1.000."""
        return cls(scale, whole)

    @classmethod
    def zero(cls, scale: int) -> Decimal:
        """Create zero value. ``Decimal.zero(3)`` == 0.000."""
        return cls(scale, 0)

    # -- Cross-scale interpretation ----------------------------------------

    def as_lower_bound(self, target_scale: int) -> Decimal:
        """Interpret this value as its minimum at a finer scale.

        Pads with zeros: ``Decimal(1, "1.2").as_lower_bound(3)`` == ``Decimal(3, "1.200")``.
        """
        if target_scale < self._scale:
            msg = (
                f"target_scale ({target_scale}) must be >= self.scale ({self._scale}); "
                f"coarser conversion is lossy"
            )
            raise ValueError(msg)
        if target_scale == self._scale:
            return self
        # Pad with zeros — just re-quantize at the finer scale
        return Decimal(target_scale, self._value)

    def as_upper_bound(self, target_scale: int) -> Decimal:
        """Interpret this value as its maximum at a finer scale.

        Pads with 9s: ``Decimal(1, "1.2").as_upper_bound(3)`` == ``Decimal(3, "1.299")``.

        Computed as (self + 1 unit at self.scale) - (1 unit at target_scale).
        """
        if target_scale < self._scale:
            msg = (
                f"target_scale ({target_scale}) must be >= self.scale ({self._scale}); "
                f"coarser conversion is lossy"
            )
            raise ValueError(msg)
        if target_scale == self._scale:
            return self
        one_at_self_scale = _quantizer(self._scale)  # e.g. 0.1 for scale=1
        one_at_target = _quantizer(target_scale)  # e.g. 0.001 for scale=3
        upper_raw = self._value + one_at_self_scale - one_at_target
        return Decimal(target_scale, upper_raw)

    # -- Arithmetic --------------------------------------------------------

    def _require_same_scale(self, other: Decimal) -> None:
        if self._scale != other._scale:
            msg = (
                f"Cannot operate on Decimals with different scales: "
                f"{self._scale} vs {other._scale}"
            )
            raise ValueError(msg)

    def __add__(self, other: object) -> Decimal:
        if not isinstance(other, Decimal):
            return NotImplemented
        self._require_same_scale(other)
        raw = self._value + other._value
        return Decimal(self._scale, raw)

    def __sub__(self, other: object) -> Decimal:
        if not isinstance(other, Decimal):
            return NotImplemented
        self._require_same_scale(other)
        raw = self._value - other._value
        return Decimal(self._scale, raw)

    # -- Comparison --------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Decimal):
            return NotImplemented
        if self._scale != other._scale:
            msg = f"Cannot compare Decimals with different scales: {self._scale} vs {other._scale}"
            raise ValueError(msg)
        return self._value == other._value

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Decimal):
            return NotImplemented
        if self._scale != other._scale:
            msg = f"Cannot compare Decimals with different scales: {self._scale} vs {other._scale}"
            raise ValueError(msg)
        return self._value < other._value

    def __hash__(self) -> int:
        return hash((self._scale, self._value))

    # -- String representations --------------------------------------------

    def __repr__(self) -> str:
        return f"Decimal({self._scale}, '{self._value}')"

    def __str__(self) -> str:
        return str(self._value)
