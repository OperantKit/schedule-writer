"""Tests for the ``schedule-writer`` CLI entry point."""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from schedule_writer import cli


def _run(argv: list[str]) -> tuple[int, str, str]:
    """Run ``cli.main`` and capture stdout / stderr / exit code.

    ``SystemExit`` may carry either an int code (argparse) or a string message
    (``raise SystemExit("...")``); the latter is treated as exit code 2 and the
    message is written to stderr to mimic real CLI behaviour.
    """
    out = io.StringIO()
    err = io.StringIO()
    rc = 0
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = cli.main(argv)
        except SystemExit as exc:
            code = exc.code
            if isinstance(code, int):
                rc = code
            elif code is None:
                rc = 0
            else:
                # String message: print to stderr, exit code 2.
                err.write(str(code) + "\n")
                rc = 2
    return rc, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------


def test_cli_help_exits_zero() -> None:
    rc, out, _err = _run(["--help"])
    assert rc == 0
    assert "schedule-writer" in out


def test_cli_no_command_errors() -> None:
    rc, _out, err = _run([])
    # argparse exits with code 2 when required subcommand is missing.
    assert rc == 2
    assert "command" in err.lower() or "required" in err.lower()


# ---------------------------------------------------------------------------
# `build` subcommand
# ---------------------------------------------------------------------------


def test_build_fr_5() -> None:
    rc, out, _err = _run(["build", "fr", "5"])
    assert rc == 0
    assert out.strip() == "FR 5"


def test_build_vi_30_default_unit() -> None:
    rc, out, _err = _run(["build", "vi", "30"])
    assert rc == 0
    assert out.strip() == "VI 30s"


def test_build_vi_with_explicit_unit() -> None:
    rc, out, _err = _run(["build", "vi", "5", "min"])
    assert rc == 0
    assert out.strip() == "VI 5min"


def test_build_crf_no_args() -> None:
    rc, out, _err = _run(["build", "crf"])
    assert rc == 0
    assert out.strip() == "CRF"


def test_build_ext_no_args() -> None:
    rc, out, _err = _run(["build", "ext"])
    assert rc == 0
    assert out.strip() == "EXT"


def test_build_concurrent() -> None:
    rc, out, _err = _run(["build", "conc", "VI 30s", "VI 60s"])
    assert rc == 0
    assert out.strip() == "Conc(VI 30s, VI 60s)"


def test_build_chain() -> None:
    rc, out, _err = _run(["build", "chain", "FR 5", "FI 30s"])
    assert rc == 0
    assert out.strip() == "Chain(FR 5, FI 30s)"


def test_build_dro_default() -> None:
    rc, out, _err = _run(["build", "dro", "10"])
    assert rc == 0
    assert out.strip() == "DRO 10s"


def test_build_dro_with_mode() -> None:
    rc, out, _err = _run(["build", "dro", "10", "momentary"])
    assert rc == 0
    assert out.strip() == "DRO 10s @mode(momentary)"


def test_build_unknown_schedule() -> None:
    rc, _out, err = _run(["build", "bogus", "1"])
    assert rc == 2
    assert "unknown schedule" in err


def test_build_fr_invalid_arg() -> None:
    rc, _out, err = _run(["build", "fr", "0"])
    assert rc == 2
    assert "positive" in err.lower()


def test_build_fr_non_integer() -> None:
    rc, _out, err = _run(["build", "fr", "abc"])
    assert rc != 0
    assert "integer" in err.lower()


def test_build_compound_too_few_components() -> None:
    rc, _out, err = _run(["build", "conc", "VI 30s"])
    assert rc != 0
    assert "at least 2" in err.lower()


# ---------------------------------------------------------------------------
# `html` subcommand
# ---------------------------------------------------------------------------


def test_html_subcommand_writes_file(tmp_path: Path) -> None:
    output = tmp_path / "out" / "writer.html"
    rc, out, _err = _run(["html", "--output", str(output)])
    assert rc == 0
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in text
    assert "schedule-writer" in text
    assert str(output) in out


def test_blocks_subcommand_writes_file(tmp_path: Path) -> None:
    output = tmp_path / "out" / "blocks.html"
    rc, out, _err = _run(["blocks", "--output", str(output)])
    assert rc == 0
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in text
    assert "block editor" in text.lower()
    assert 'id="palette"' in text
    assert 'id="viewport"' in text
    assert str(output) in out


# ---------------------------------------------------------------------------
# `interactive` subcommand (stdin-driven)
# ---------------------------------------------------------------------------


def test_interactive_basic_session(monkeypatch: pytest.MonkeyPatch) -> None:
    # Components with internal whitespace must be quoted (shlex splitting).
    inputs = iter(["fr 5", 'conc "VI 30s" "VI 60s"', "quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    rc, out, _err = _run(["interactive"])
    assert rc == 0
    assert "FR 5" in out
    assert "Conc(VI 30s, VI 60s)" in out


def test_interactive_handles_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = iter(["bogus 1", "quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    rc, out, _err = _run(["interactive"])
    assert rc == 0
    assert "unknown schedule" in out


def test_interactive_handles_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = iter(["fr 0", "quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    rc, out, _err = _run(["interactive"])
    assert rc == 0
    assert "error" in out.lower()


def test_interactive_eof_terminates(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_eof(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    rc, _out, _err = _run(["interactive"])
    assert rc == 0
