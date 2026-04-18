"""Smoke tests: importability and a minimal end-to-end round trip."""

from __future__ import annotations

import schedule_writer
from schedule_writer.builder import ScheduleBuilder


def test_package_importable() -> None:
    assert hasattr(schedule_writer, "ScheduleBuilder")


def test_basic_round_trip() -> None:
    b = ScheduleBuilder()
    assert b.fr(5) == "FR 5"
    assert b.concurrent(b.vi(30), b.vi(60)) == "Conc(VI 30s, VI 60s)"
