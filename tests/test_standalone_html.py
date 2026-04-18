"""Tests for the standalone HTML generator."""

from __future__ import annotations

from pathlib import Path

from schedule_writer.standalone_html import generate_standalone_html


def test_generates_file(tmp_path: Path) -> None:
    out = tmp_path / "writer.html"
    generate_standalone_html(out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_creates_parent_directories(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "dir" / "writer.html"
    generate_standalone_html(out)
    assert out.exists()


def test_overwrites_existing_file(tmp_path: Path) -> None:
    out = tmp_path / "writer.html"
    out.write_text("OLD CONTENT", encoding="utf-8")
    generate_standalone_html(out)
    assert "OLD CONTENT" not in out.read_text(encoding="utf-8")


def test_contains_doctype(tmp_path: Path) -> None:
    out = tmp_path / "writer.html"
    generate_standalone_html(out)
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<!DOCTYPE html>")


def test_self_contained_no_external_scripts(tmp_path: Path) -> None:
    out = tmp_path / "writer.html"
    generate_standalone_html(out)
    text = out.read_text(encoding="utf-8")
    # No CDN imports or external script tags.
    assert "<script src=" not in text
    assert "https://" not in text
    assert "http://" not in text
    assert "cdn." not in text.lower()
    # No stylesheet links either.
    assert "<link rel=\"stylesheet\"" not in text


def test_contains_atomic_schedule_markers(tmp_path: Path) -> None:
    out = tmp_path / "writer.html"
    generate_standalone_html(out)
    text = out.read_text(encoding="utf-8")
    for kind in ("FR", "VR", "FI", "VI", "RI", "FT", "VT", "RT", "DRL", "DRH", "DRO", "CRF", "EXT"):
        assert kind in text, f"missing schedule marker: {kind}"


def test_contains_compound_combinator_markers(tmp_path: Path) -> None:
    out = tmp_path / "writer.html"
    generate_standalone_html(out)
    text = out.read_text(encoding="utf-8")
    for combinator in ("Conc", "Mult", "Chain", "Tand", "Alt"):
        assert combinator in text, f"missing combinator marker: {combinator}"


def test_contains_inline_script_block(tmp_path: Path) -> None:
    out = tmp_path / "writer.html"
    generate_standalone_html(out)
    text = out.read_text(encoding="utf-8")
    # Inline script (no src=) producing the builder logic.
    assert "<script>" in text
    assert "buildAtomic" in text
    assert "buildCompound" in text


def test_accepts_string_path(tmp_path: Path) -> None:
    out = tmp_path / "writer.html"
    generate_standalone_html(str(out))
    assert out.exists()
