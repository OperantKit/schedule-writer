"""Command-line interface for schedule-writer.

Subcommands
-----------
``build``       Single-shot construction. ``schedule-writer build fr 5`` prints
                ``FR 5``. Compound combinators take their components as quoted
                strings: ``schedule-writer build conc "VI 30s" "VI 60s"``.
``interactive`` Guided REPL that prompts for the schedule family then its
                parameters. Useful for users who do not want to memorise the
                ``build`` argument shape.
``html``        Writes a single self-contained HTML file (no CDN dependencies)
                exposing the same builder API in the browser.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from schedule_writer.builder import DRO_MODES, TIME_UNITS, ScheduleBuilder
from schedule_writer.standalone_html import generate_standalone_html

# ---------------------------------------------------------------------------
# `build` dispatch table
# ---------------------------------------------------------------------------
#
# Each entry maps a CLI keyword (lower-case) to a callable that consumes the
# remaining positional arguments (still as strings) and returns a DSL string.
# Compound combinators take an arbitrary number of pre-built schedule strings.

# Type alias for the dispatch handler signature.
BuildHandler = Callable[[ScheduleBuilder, Sequence[str]], str]


def _atomic_count(method_name: str) -> BuildHandler:
    def handler(b: ScheduleBuilder, args: Sequence[str]) -> str:
        if len(args) != 1:
            raise SystemExit(f"{method_name} expects exactly 1 argument (count)")
        try:
            n = int(args[0])
        except ValueError as exc:
            raise SystemExit(f"{method_name} count must be an integer: {args[0]!r}") from exc
        return cast(str, getattr(b, method_name)(n))

    return handler


def _atomic_mean(method_name: str) -> BuildHandler:
    def handler(b: ScheduleBuilder, args: Sequence[str]) -> str:
        if len(args) != 1:
            raise SystemExit(f"{method_name} expects exactly 1 argument (mean)")
        try:
            mean = float(args[0])
        except ValueError as exc:
            raise SystemExit(f"{method_name} mean must be numeric: {args[0]!r}") from exc
        return cast(str, getattr(b, method_name)(mean))

    return handler


def _atomic_seconds(method_name: str) -> BuildHandler:
    def handler(b: ScheduleBuilder, args: Sequence[str]) -> str:
        if not 1 <= len(args) <= 2:
            raise SystemExit(
                f"{method_name} expects 1-2 arguments (seconds [, unit])"
            )
        try:
            seconds = float(args[0])
        except ValueError as exc:
            raise SystemExit(f"{method_name} value must be numeric: {args[0]!r}") from exc
        unit = args[1] if len(args) == 2 else "s"
        return cast(str, getattr(b, method_name)(seconds, unit))

    return handler


def _atomic_probability(method_name: str) -> BuildHandler:
    def handler(b: ScheduleBuilder, args: Sequence[str]) -> str:
        if len(args) != 1:
            raise SystemExit(f"{method_name} expects exactly 1 argument (probability)")
        try:
            p = float(args[0])
        except ValueError as exc:
            raise SystemExit(f"{method_name} probability must be numeric: {args[0]!r}") from exc
        return cast(str, getattr(b, method_name)(p))

    return handler


def _no_args(method_name: str) -> BuildHandler:
    def handler(b: ScheduleBuilder, args: Sequence[str]) -> str:
        if args:
            raise SystemExit(f"{method_name} takes no arguments, got {list(args)!r}")
        return cast(str, getattr(b, method_name)())

    return handler


def _compound(method_name: str) -> BuildHandler:
    def handler(b: ScheduleBuilder, args: Sequence[str]) -> str:
        if len(args) < 2:
            raise SystemExit(
                f"{method_name} expects at least 2 component schedule strings"
            )
        return cast(str, getattr(b, method_name)(*args))

    return handler


def _dro_handler(b: ScheduleBuilder, args: Sequence[str]) -> str:
    # dro <seconds> [unit] [mode]
    if not 1 <= len(args) <= 3:
        raise SystemExit("dro expects 1-3 arguments: <seconds> [unit] [mode]")
    try:
        seconds = float(args[0])
    except ValueError as exc:
        raise SystemExit(f"dro seconds must be numeric: {args[0]!r}") from exc
    unit = "s"
    mode = "resetting"
    for extra in args[1:]:
        if extra in TIME_UNITS:
            unit = extra
        elif extra in DRO_MODES:
            mode = extra
        else:
            raise SystemExit(
                f"dro extra argument {extra!r} must be a time unit "
                f"({sorted(TIME_UNITS)}) or DRO mode ({sorted(DRO_MODES)})"
            )
    return b.dro(seconds, mode=mode, unit=unit)


_BUILD_DISPATCH: dict[str, BuildHandler] = {
    # Atomic ratio
    "fr": _atomic_count("fr"),
    "vr": _atomic_mean("vr"),
    "rr": _atomic_probability("rr"),
    # Atomic interval
    "fi": _atomic_seconds("fi"),
    "vi": _atomic_seconds("vi"),
    "ri": _atomic_seconds("ri"),
    # Atomic time
    "ft": _atomic_seconds("ft"),
    "vt": _atomic_seconds("vt"),
    "rt": _atomic_seconds("rt"),
    # Boundary
    "crf": _no_args("crf"),
    "ext": _no_args("ext"),
    # Compound
    "conc": _compound("concurrent"),
    "concurrent": _compound("concurrent"),
    "mult": _compound("multiple"),
    "multiple": _compound("multiple"),
    "chain": _compound("chained"),
    "chained": _compound("chained"),
    "tand": _compound("tandem"),
    "tandem": _compound("tandem"),
    "alt": _compound("alternative"),
    "alternative": _compound("alternative"),
    # Differential
    "drl": _atomic_seconds("drl"),
    "drh": _atomic_seconds("drh"),
    "dro": _dro_handler,
}


# ---------------------------------------------------------------------------
# Sub-command implementations
# ---------------------------------------------------------------------------


def _cmd_build(ns: argparse.Namespace) -> int:
    schedule_kw: str = cast(str, ns.schedule)
    raw_args: list[str] = cast("list[str]", ns.args)
    keyword = schedule_kw.lower()
    handler = _BUILD_DISPATCH.get(keyword)
    if handler is None:
        sys.stderr.write(
            f"error: unknown schedule '{schedule_kw}'. "
            f"Known: {sorted(_BUILD_DISPATCH)}\n"
        )
        return 2
    builder = ScheduleBuilder()
    try:
        result = handler(builder, raw_args)
    except ValueError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    print(result)
    return 0


def _cmd_html(ns: argparse.Namespace) -> int:
    output_path = Path(cast(str, ns.output))
    generate_standalone_html(output_path)
    print(f"wrote standalone HTML to {output_path}")
    return 0


def _cmd_interactive(ns: argparse.Namespace) -> int:
    builder = ScheduleBuilder()
    print("schedule-writer interactive — type 'quit' to exit")
    print("Available schedules: " + ", ".join(sorted(_BUILD_DISPATCH)))
    while True:
        try:
            line = input("schedule> ").strip()
        except EOFError:
            print()
            return 0
        if not line or line.lower() in {"quit", "exit", ":q"}:
            return 0
        # Use shlex so users can quote multi-token components for compound
        # combinators, e.g. ``conc "VI 30s" "VI 60s"``.
        try:
            parts = shlex.split(line)
        except ValueError as exc:
            print(f"error: {exc}")
            continue
        if not parts:
            continue
        keyword = parts[0].lower()
        rest = parts[1:]
        handler = _BUILD_DISPATCH.get(keyword)
        if handler is None:
            print(
                f"unknown schedule '{parts[0]}'. "
                f"Known: {sorted(_BUILD_DISPATCH)}"
            )
            continue
        try:
            result = handler(builder, rest)
        except (ValueError, SystemExit) as exc:
            print(f"error: {exc}")
            continue
        print(result)


# ---------------------------------------------------------------------------
# argparse wiring
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="schedule-writer",
        description=(
            "Compose contingency-dsl reinforcement-schedule strings via "
            "a builder API, an interactive REPL, or a self-contained HTML page."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser(
        "build",
        help="Build a single schedule string and print it to stdout.",
        description=(
            "Build a single schedule string. Examples: "
            "'build fr 5', 'build vi 30', 'build conc \"VI 30s\" \"VI 60s\"'."
        ),
    )
    p_build.add_argument(
        "schedule", help="Schedule keyword (fr, vr, fi, vi, conc, ...)"
    )
    p_build.add_argument(
        "args",
        nargs="*",
        help="Schedule arguments (counts, durations, components)",
    )
    p_build.set_defaults(func=_cmd_build)

    p_int = sub.add_parser(
        "interactive",
        help="Start an interactive REPL that prompts for schedules.",
    )
    p_int.set_defaults(func=_cmd_interactive)

    p_html = sub.add_parser(
        "html",
        help="Generate a single self-contained HTML page.",
    )
    p_html.add_argument(
        "--output",
        "-o",
        default="schedule-writer.html",
        help="Output path for the HTML file (default: schedule-writer.html)",
    )
    p_html.set_defaults(func=_cmd_html)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)
    # ``ns.func`` is set by every subparser via ``set_defaults``.
    func = cast(Callable[[argparse.Namespace], int], ns.func)
    rc = func(ns)
    return int(rc or 0)


if __name__ == "__main__":  # pragma: no cover — exercised via console script
    raise SystemExit(main())
