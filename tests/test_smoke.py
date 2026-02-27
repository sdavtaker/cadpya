"""Smoke test to verify project setup."""

import cadpya


def test_package_is_importable() -> None:
    assert cadpya is not None
