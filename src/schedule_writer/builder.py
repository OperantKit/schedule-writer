"""Fluent builder API for composing contingency-dsl schedule strings.

The builder produces text in the surface syntax of the contingency-dsl operant
grammar. Each method validates parameter ranges and raises :class:`ValueError`
with a descriptive message on invalid input. The output is plain text; nothing
is parsed or evaluated by this package.

Examples
--------
>>> b = ScheduleBuilder()
>>> b.fr(5)
'FR 5'
>>> b.vi(30)
'VI 30s'
>>> b.concurrent(b.vi(30), b.vi(60))
'Conc(VI 30s, VI 60s)'
>>> b.with_annotation(b.fr(5), '@reinforcer(food)')
'FR 5 @reinforcer(food)'
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

# --- Time-unit literals ----------------------------------------------------
# The DSL accepts s / ms / min as the supported wall-clock units; "s" is the
# default for time-domain schedules emitted by this builder.
TIME_UNITS: Final[frozenset[str]] = frozenset({"s", "ms", "min"})

# --- DRO mode literals -----------------------------------------------------
# These are not formal DSL grammar tokens (the spec models DRO as a modifier
# with an integer threshold); the builder emits them as annotation-style
# suffixes for readability.
DRO_MODES: Final[frozenset[str]] = frozenset({"resetting", "non-resetting", "momentary"})


# ---------------------------------------------------------------------------
# Internal formatting helpers
# ---------------------------------------------------------------------------


def _format_count(name: str, n: int) -> str:
    """Format a positive integer count for ratio-domain schedules (FR, VR)."""
    if not isinstance(n, int) or isinstance(n, bool):
        raise ValueError(f"{name} requires an integer count, got {type(n).__name__}: {n!r}")
    if n <= 0:
        raise ValueError(f"{name} requires a positive integer count, got {n}")
    return f"{name} {n}"


def _format_mean(name: str, mean: float) -> str:
    """Format a positive real mean for VR/RR-style ratio schedules."""
    _require_positive_real(name, mean)
    return f"{name} {_strip_trailing_zero(float(mean))}"


def _format_seconds(name: str, seconds: float, unit: str = "s") -> str:
    """Format a positive duration with an explicit time unit (FI, VI, FT, ...)."""
    if unit not in TIME_UNITS:
        raise ValueError(
            f"{name} requires a time unit in {sorted(TIME_UNITS)}, got {unit!r}"
        )
    _require_positive_real(name, seconds)
    return f"{name} {_strip_trailing_zero(float(seconds))}{unit}"


def _format_probability(name: str, p: float) -> str:
    """Format a probability in the half-open interval (0, 1] for RR schedules."""
    if not isinstance(p, (int, float)) or isinstance(p, bool):
        raise ValueError(f"{name} requires a numeric probability, got {type(p).__name__}: {p!r}")
    if not (0.0 < float(p) <= 1.0):
        raise ValueError(f"{name} requires a probability in (0, 1], got {p}")
    return f"{name} {_strip_trailing_zero(float(p))}"


def _require_positive_real(name: str, value: float) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} requires a numeric value, got {type(value).__name__}: {value!r}")
    if float(value) <= 0.0:
        raise ValueError(f"{name} requires a positive value, got {value}")


def _strip_trailing_zero(value: float) -> str:
    """Render a float without superfluous ``.0`` while keeping non-integer values."""
    if value == int(value):
        return str(int(value))
    # Use ``repr``-like formatting that avoids scientific notation for the ranges
    # the builder is likely to encounter (sub-second to multi-minute durations).
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _require_nonempty_schedules(combinator: str, schedules: tuple[str, ...]) -> None:
    if len(schedules) < 2:
        raise ValueError(
            f"{combinator} requires at least 2 component schedules, got {len(schedules)}"
        )
    for i, sched in enumerate(schedules):
        if not isinstance(sched, str) or not sched.strip():
            raise ValueError(
                f"{combinator} component #{i} must be a non-empty schedule string, got {sched!r}"
            )


def _format_compound(combinator: str, schedules: tuple[str, ...]) -> str:
    _require_nonempty_schedules(combinator, schedules)
    return f"{combinator}(" + ", ".join(schedules) + ")"


# ---------------------------------------------------------------------------
# Builder class
# ---------------------------------------------------------------------------


class ScheduleBuilder:
    """Fluent producer of contingency-dsl schedule strings.

    Each method returns a string; instances of this class are stateless and
    methods can be called freely in any order. The class is provided rather
    than module-level functions to keep a single typed entry point and to
    make the API discoverable via ``dir(ScheduleBuilder)``.
    """

    # --- Atomic ratio schedules (FR, VR, RR) -------------------------------

    def fr(self, n: int) -> str:
        """Fixed Ratio: every ``n``-th response is reinforced. ``FR n``."""
        return _format_count("FR", n)

    def vr(self, mean: float) -> str:
        """Variable Ratio with mean ``mean``. ``VR mean``."""
        return _format_mean("VR", mean)

    def rr(self, prob: float) -> str:
        """Random Ratio: each response reinforced with probability ``prob``. ``RR p``."""
        return _format_probability("RR", prob)

    # --- Atomic interval schedules (FI, VI, RI) ---------------------------

    def fi(self, seconds: float, unit: str = "s") -> str:
        """Fixed Interval. ``FI <seconds><unit>``."""
        return _format_seconds("FI", seconds, unit)

    def vi(self, mean: float, unit: str = "s") -> str:
        """Variable Interval with mean ``mean``. ``VI <mean><unit>``."""
        return _format_seconds("VI", mean, unit)

    def ri(self, mean: float, unit: str = "s") -> str:
        """Random Interval (exponential). ``RI <mean><unit>``."""
        return _format_seconds("RI", mean, unit)

    # --- Atomic time schedules (FT, VT, RT) -------------------------------

    def ft(self, seconds: float, unit: str = "s") -> str:
        """Fixed Time: response-independent reinforcement at fixed intervals."""
        return _format_seconds("FT", seconds, unit)

    def vt(self, mean: float, unit: str = "s") -> str:
        """Variable Time: response-independent reinforcement at variable intervals."""
        return _format_seconds("VT", mean, unit)

    def rt(self, mean: float, unit: str = "s") -> str:
        """Random Time: exponential response-independent reinforcement."""
        return _format_seconds("RT", mean, unit)

    # --- Boundary cases ---------------------------------------------------

    def crf(self) -> str:
        """Continuous Reinforcement (every response reinforced). ``CRF``."""
        return "CRF"

    def ext(self) -> str:
        """Extinction (no reinforcement). ``EXT``."""
        return "EXT"

    # --- Compound combinators --------------------------------------------

    def concurrent(self, *schedules: str) -> str:
        """Concurrent schedules running on independent operanda. ``Conc(...)``."""
        return _format_compound("Conc", schedules)

    def multiple(self, *schedules: str) -> str:
        """Multiple schedules with discriminative stimuli. ``Mult(...)``."""
        return _format_compound("Mult", schedules)

    def chained(self, *schedules: str) -> str:
        """Chained schedules: each component's completion advances to the next. ``Chain(...)``."""
        return _format_compound("Chain", schedules)

    def tandem(self, *schedules: str) -> str:
        """Tandem schedules: like Chain but without component stimuli. ``Tand(...)``."""
        return _format_compound("Tand", schedules)

    def alternative(self, *schedules: str) -> str:
        """Alternative schedules: reinforcement on first component requirement met. ``Alt(...)``."""
        return _format_compound("Alt", schedules)

    # --- Differential reinforcement modifiers ----------------------------

    def dro(self, seconds: float, *, mode: str = "resetting", unit: str = "s") -> str:
        """Differential Reinforcement of Other behaviour.

        ``DRO <seconds><unit>`` — base form. Optional ``mode`` is appended as
        an annotation (``@mode(resetting)`` etc.) because the formal DSL only
        encodes the duration; the mode is procedurally significant but spec'd
        at the annotation layer.
        """
        if mode not in DRO_MODES:
            raise ValueError(
                f"DRO mode must be one of {sorted(DRO_MODES)}, got {mode!r}"
            )
        base = _format_seconds("DRO", seconds, unit)
        # Default "resetting" matches the most common procedural form (Reynolds,
        # 1961); we omit the annotation to keep the canonical short form
        # round-trippable with the bare-DRO conformance fixtures.
        if mode == "resetting":
            return base
        return f"{base} @mode({mode})"

    def drl(self, seconds: float, unit: str = "s") -> str:
        """Differential Reinforcement of Low rate (IRT >= ``seconds``)."""
        return _format_seconds("DRL", seconds, unit)

    def drh(self, seconds: float, unit: str = "s") -> str:
        """Differential Reinforcement of High rate (IRT <= ``seconds``).

        The DSL parameterises DRH by an IRT upper bound expressed in time
        units, matching DRL. Some literature parameterises DRH by a target
        response *rate* instead; that conversion (rate -> ``1 / rate``) is the
        caller's responsibility.
        """
        return _format_seconds("DRH", seconds, unit)

    # --- Annotations ------------------------------------------------------

    def with_annotation(self, schedule: str, *annotations: str) -> str:
        """Append one or more annotation tokens to a schedule string.

        Each annotation must start with ``@`` (e.g. ``@reinforcer(food)``).
        Whitespace between the schedule and annotations is normalised to a
        single space.
        """
        if not isinstance(schedule, str) or not schedule.strip():
            raise ValueError(f"schedule must be a non-empty string, got {schedule!r}")
        if not annotations:
            raise ValueError("with_annotation requires at least one annotation")
        cleaned: list[str] = []
        for i, ann in enumerate(annotations):
            if not isinstance(ann, str) or not ann.strip():
                raise ValueError(
                    f"annotation #{i} must be a non-empty string, got {ann!r}"
                )
            stripped = ann.strip()
            if not stripped.startswith("@"):
                raise ValueError(
                    f"annotation #{i} must start with '@', got {stripped!r}"
                )
            cleaned.append(stripped)
        return schedule.strip() + " " + " ".join(cleaned)


# ---------------------------------------------------------------------------
# Module-level convenience: a single shared instance for one-off use
# ---------------------------------------------------------------------------


def _iter_atomic_constructors() -> Iterable[str]:
    """Names of atomic schedule methods. Used by the CLI's ``build`` dispatcher."""
    return (
        "fr", "vr", "rr",
        "fi", "vi", "ri",
        "ft", "vt", "rt",
        "crf", "ext",
        "drl", "drh", "dro",
    )


def _iter_compound_constructors() -> Iterable[str]:
    return ("conc", "mult", "chain", "tand", "alt")
