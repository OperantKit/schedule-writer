"""Tests for the ScheduleBuilder fluent API.

The builder produces text in the surface syntax of the contingency-dsl operant
grammar; these tests pin the canonical formatting and the validation rules.
"""

from __future__ import annotations

import pytest

from schedule_writer.builder import ScheduleBuilder


@pytest.fixture
def b() -> ScheduleBuilder:
    return ScheduleBuilder()


# ---------------------------------------------------------------------------
# Atomic ratio schedules
# ---------------------------------------------------------------------------


class TestRatioSchedules:
    def test_fr_basic(self, b: ScheduleBuilder) -> None:
        assert b.fr(5) == "FR 5"

    def test_fr_large(self, b: ScheduleBuilder) -> None:
        assert b.fr(100) == "FR 100"

    def test_fr_rejects_zero(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="positive"):
            b.fr(0)

    def test_fr_rejects_negative(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="positive"):
            b.fr(-3)

    def test_fr_rejects_float(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="integer"):
            b.fr(2.5)  # type: ignore[arg-type]

    def test_fr_rejects_bool(self, b: ScheduleBuilder) -> None:
        # bool is a subclass of int in Python; the builder should still reject it.
        with pytest.raises(ValueError, match="integer"):
            b.fr(True)  # type: ignore[arg-type]

    def test_vr_integer_mean(self, b: ScheduleBuilder) -> None:
        assert b.vr(20) == "VR 20"

    def test_vr_float_mean(self, b: ScheduleBuilder) -> None:
        assert b.vr(2.5) == "VR 2.5"

    def test_vr_rejects_nonpositive(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="positive"):
            b.vr(0)

    def test_rr_basic(self, b: ScheduleBuilder) -> None:
        assert b.rr(0.1) == "RR 0.1"

    def test_rr_one(self, b: ScheduleBuilder) -> None:
        # p == 1 is allowed (degenerate FR 1 / CRF case)
        assert b.rr(1.0) == "RR 1"

    def test_rr_rejects_zero(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match=r"\(0, 1\]"):
            b.rr(0.0)

    def test_rr_rejects_above_one(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match=r"\(0, 1\]"):
            b.rr(1.5)


# ---------------------------------------------------------------------------
# Atomic interval and time schedules
# ---------------------------------------------------------------------------


class TestIntervalSchedules:
    def test_fi_default_unit(self, b: ScheduleBuilder) -> None:
        assert b.fi(30) == "FI 30s"

    def test_fi_minutes(self, b: ScheduleBuilder) -> None:
        assert b.fi(5, unit="min") == "FI 5min"

    def test_fi_milliseconds(self, b: ScheduleBuilder) -> None:
        assert b.fi(500, unit="ms") == "FI 500ms"

    def test_vi_basic(self, b: ScheduleBuilder) -> None:
        assert b.vi(30) == "VI 30s"

    def test_vi_float(self, b: ScheduleBuilder) -> None:
        assert b.vi(30.5) == "VI 30.5s"

    def test_ri_basic(self, b: ScheduleBuilder) -> None:
        assert b.ri(15) == "RI 15s"

    def test_ft_basic(self, b: ScheduleBuilder) -> None:
        assert b.ft(10) == "FT 10s"

    def test_vt_basic(self, b: ScheduleBuilder) -> None:
        assert b.vt(20) == "VT 20s"

    def test_rt_basic(self, b: ScheduleBuilder) -> None:
        assert b.rt(15) == "RT 15s"

    def test_interval_rejects_invalid_unit(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="time unit"):
            b.fi(30, unit="hours")

    def test_interval_rejects_nonpositive(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="positive"):
            b.fi(0)

    def test_interval_rejects_negative(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="positive"):
            b.vi(-5)


# ---------------------------------------------------------------------------
# Boundary cases
# ---------------------------------------------------------------------------


class TestBoundary:
    def test_crf(self, b: ScheduleBuilder) -> None:
        assert b.crf() == "CRF"

    def test_ext(self, b: ScheduleBuilder) -> None:
        assert b.ext() == "EXT"


# ---------------------------------------------------------------------------
# Differential reinforcement modifiers
# ---------------------------------------------------------------------------


class TestDifferential:
    def test_drl_basic(self, b: ScheduleBuilder) -> None:
        assert b.drl(5) == "DRL 5s"

    def test_drh_basic(self, b: ScheduleBuilder) -> None:
        assert b.drh(2) == "DRH 2s"

    def test_dro_default_resetting(self, b: ScheduleBuilder) -> None:
        # Resetting mode is the canonical default; no annotation appended.
        assert b.dro(10) == "DRO 10s"

    def test_dro_explicit_resetting(self, b: ScheduleBuilder) -> None:
        assert b.dro(10, mode="resetting") == "DRO 10s"

    def test_dro_non_resetting(self, b: ScheduleBuilder) -> None:
        assert b.dro(10, mode="non-resetting") == "DRO 10s @mode(non-resetting)"

    def test_dro_momentary(self, b: ScheduleBuilder) -> None:
        assert b.dro(10, mode="momentary") == "DRO 10s @mode(momentary)"

    def test_dro_rejects_unknown_mode(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="DRO mode"):
            b.dro(10, mode="bogus")

    def test_dro_rejects_nonpositive_seconds(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="positive"):
            b.dro(0)


# ---------------------------------------------------------------------------
# Compound combinators
# ---------------------------------------------------------------------------


class TestCompounds:
    def test_concurrent_two(self, b: ScheduleBuilder) -> None:
        assert b.concurrent(b.vi(30), b.vi(60)) == "Conc(VI 30s, VI 60s)"

    def test_concurrent_three(self, b: ScheduleBuilder) -> None:
        assert (
            b.concurrent(b.vi(30), b.vi(60), b.vi(120))
            == "Conc(VI 30s, VI 60s, VI 120s)"
        )

    def test_multiple(self, b: ScheduleBuilder) -> None:
        assert b.multiple(b.fr(5), b.ext()) == "Mult(FR 5, EXT)"

    def test_chained(self, b: ScheduleBuilder) -> None:
        assert b.chained(b.fr(5), b.fi(30)) == "Chain(FR 5, FI 30s)"

    def test_tandem(self, b: ScheduleBuilder) -> None:
        assert b.tandem(b.vr(20), b.drl(5)) == "Tand(VR 20, DRL 5s)"

    def test_alternative(self, b: ScheduleBuilder) -> None:
        assert b.alternative(b.fr(10), b.fi(5, unit="min")) == "Alt(FR 10, FI 5min)"

    def test_nested_concurrent_chain(self, b: ScheduleBuilder) -> None:
        # Conc(Chain(FR 5, VI 60s), FR 10) — the example given in grammar.md §4.B
        inner = b.chained(b.fr(5), b.vi(60))
        outer = b.concurrent(inner, b.fr(10))
        assert outer == "Conc(Chain(FR 5, VI 60s), FR 10)"

    def test_compound_rejects_single_component(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            b.concurrent(b.fr(5))

    def test_compound_rejects_empty_args(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            b.concurrent()

    def test_compound_rejects_empty_string_component(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            b.concurrent(b.fr(5), "")


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------


class TestAnnotations:
    def test_single_annotation(self, b: ScheduleBuilder) -> None:
        assert (
            b.with_annotation(b.fr(5), "@reinforcer(food)")
            == "FR 5 @reinforcer(food)"
        )

    def test_multiple_annotations(self, b: ScheduleBuilder) -> None:
        assert (
            b.with_annotation(b.vi(30), "@reinforcer(food)", "@operandum(lever-left)")
            == "VI 30s @reinforcer(food) @operandum(lever-left)"
        )

    def test_annotation_strips_surrounding_whitespace(self, b: ScheduleBuilder) -> None:
        assert (
            b.with_annotation("  FR 5  ", "  @reinforcer(food)  ")
            == "FR 5 @reinforcer(food)"
        )

    def test_annotation_requires_at_sign(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="must start with '@'"):
            b.with_annotation(b.fr(5), "reinforcer(food)")

    def test_annotation_requires_nonempty_schedule(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            b.with_annotation("", "@reinforcer(food)")

    def test_annotation_requires_at_least_one(self, b: ScheduleBuilder) -> None:
        with pytest.raises(ValueError, match="at least one"):
            b.with_annotation(b.fr(5))


# ---------------------------------------------------------------------------
# Property-style spot checks
# ---------------------------------------------------------------------------


def test_fr_round_trip_format(b: ScheduleBuilder) -> None:
    # The output should be exactly the canonical short form so that downstream
    # parsers do not need to handle whitespace variations beyond a single space.
    for n in (1, 2, 5, 10, 100, 1000):
        assert b.fr(n) == f"FR {n}"


def test_vi_seconds_strip_trailing_zero(b: ScheduleBuilder) -> None:
    assert b.vi(30.0) == "VI 30s"
    assert b.vi(30.50) == "VI 30.5s"
    assert b.vi(0.5) == "VI 0.5s"
