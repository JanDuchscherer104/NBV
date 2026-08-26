"""Focused tests for the replay/oracle golden comparator contract."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_replay_oracle_golden as golden  # noqa: E402


def _compare(expected: object, actual: object) -> list[str]:
    return golden._mismatches(expected, actual, rtol=1e-6, atol=1e-7)


def test_float_values_use_declared_tolerance() -> None:
    assert _compare({"scores": [1.0, 2.0]}, {"scores": [1.0 + 5e-8, 2.0]}) == []
    assert _compare({"scores": [1.0]}, {"scores": [1.1]})


def test_integer_float_schema_drift_is_rejected() -> None:
    assert _compare({"count": 1}, {"count": 1.0})
    assert _compare({"count": 1.0}, {"count": 1})


def test_discrete_scalars_are_exact_and_bool_is_not_an_integer() -> None:
    assert _compare({"id": "abc", "index": 3, "valid": True}, {"id": "abc", "index": 3, "valid": True}) == []
    assert _compare({"id": "abc"}, {"id": "abd"})
    assert _compare({"index": 1}, {"index": True})


def test_import_provenance_rejects_an_unrelated_editable_checkout(monkeypatch) -> None:
    monkeypatch.setattr(golden._aria_nbv_package, "__file__", "/tmp/unrelated/aria_nbv/__init__.py")

    with pytest.raises(RuntimeError, match="import provenance mismatch"):
        golden._assert_import_provenance()
