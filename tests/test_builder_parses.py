"""Every builder method must produce a string that contingency-dsl-py accepts."""

from __future__ import annotations

import pytest
from contingency_dsl import parse

from schedule_writer.builder import ScheduleBuilder

B = ScheduleBuilder()

ATOMIC = [
    B.crf(),
    B.ext(),
    B.fr(5),
    B.vr(20),
    B.rr(0.2),
    B.fi(30),
    B.vi(30),
    B.ri(30),
    B.ft(30),
    B.vt(30),
    B.rt(30),
    B.dro(10),
    B.drl(5),
    B.drh(5),
]

COMPOUND = [
    B.concurrent(B.vi(30), B.vi(60)),
    B.multiple(B.fr(5), B.ext()),
    B.chained(B.fr(5), B.fi(30)),
    B.tandem(B.vr(10), B.drl(2)),
    B.alternative(B.fr(10), B.ft(60)),
]


@pytest.mark.parametrize("source", ATOMIC + COMPOUND)
def test_output_parses(source: str) -> None:
    parse(source)
