"""Tests for the drag-and-drop block editor HTML generator."""

from __future__ import annotations

from pathlib import Path

from schedule_writer.block_editor_html import generate_block_editor_html


def test_generates_file(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_creates_parent_directories(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "dir" / "blocks.html"
    generate_block_editor_html(out)
    assert out.exists()


def test_overwrites_existing_file(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    out.write_text("OLD CONTENT", encoding="utf-8")
    generate_block_editor_html(out)
    assert "OLD CONTENT" not in out.read_text(encoding="utf-8")


def test_starts_with_doctype(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    assert out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_self_contained_no_external_resources(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    assert "<script src=" not in text
    assert "https://" not in text
    assert "http://" not in text
    assert "cdn." not in text.lower()
    assert '<link rel="stylesheet"' not in text


def test_contains_all_atomic_schedule_kinds(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    for kind in (
        "FR", "VR", "RR", "FI", "VI", "RI",
        "FT", "VT", "RT", "DRL", "DRH", "DRO",
        "CRF", "EXT",
    ):
        assert kind in text, f"missing atomic schedule: {kind}"


def test_contains_all_compound_combinators(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    for combinator in ("Conc", "Mult", "Chain", "Tand", "Alt"):
        assert combinator in text, f"missing combinator: {combinator}"


def test_contains_drag_and_drop_handlers(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    assert "dragstart" in text
    assert "dragover" in text
    assert "drop" in text
    assert 'draggable="true"' in text


def test_contains_palette_and_canvas_regions(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    assert 'id="palette"' in text
    assert 'id="viewport"' in text
    assert 'id="world"' in text
    assert 'id="output"' in text


def test_contains_compile_function(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    assert "compileNode" in text
    assert "compileProgram" in text


def test_contains_annotation_palette(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    # Common annotation chips must be present as palette items.
    for tag in (
        "@reinforcer", "@operandum", "@response", "@timeout",
        "@phase", "@session_end", "@subject", "@custom",
    ):
        assert tag in text, f"missing annotation chip: {tag}"


def test_contains_multi_root_model(tmp_path: Path) -> None:
    """The program is a list of top-level nodes (multi-phase)."""
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    # The program model must hold an array of nodes, not a single root.
    assert "program.nodes" in text or "program = { nodes" in text
    # Empty-state hint appears until the first block is placed.
    assert "begin" in text.lower()


def test_contains_reorder_controls(tmp_path: Path) -> None:
    """Blocks expose up/down reorder buttons."""
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    assert "moveNode" in text
    assert "Move up" in text
    assert "Move down" in text


def test_contains_localstorage_persistence(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    assert "localStorage" in text
    assert "STORAGE_KEY" in text


def test_contains_pannable_zoomable_viewport(tmp_path: Path) -> None:
    """The canvas supports free 2D positioning with pan and zoom."""
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    assert 'id="viewport"' in text
    assert 'id="world"' in text
    # Pan handler uses transform translate; zoom handler uses scale.
    assert "translate(" in text
    assert "scale(" in text
    # Wheel-zoom detection uses Ctrl/Meta key gating.
    assert "ctrlKey" in text
    # Reset view / zoom buttons.
    assert "resetView" in text
    assert "zoomBy" in text


def test_top_level_nodes_have_free_positions(tmp_path: Path) -> None:
    """Top-level blocks store (x, y) and are absolutely positioned."""
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    # The model assigns node.x / node.y.
    assert "node.x" in text and "node.y" in text
    # Phase wrapper uses absolute positioning.
    assert ".phase {" in text
    assert "position: absolute" in text
    # Reading-order compile uses Y then X.
    assert "compileProgram" in text


def test_phases_support_edge_drag_resize(tmp_path: Path) -> None:
    """Top-level phase blocks can be resized by dragging their right edge/corner."""
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    # Handles rendered on each phase.
    assert "resize-handle" in text
    assert "resize-handle-br" in text
    # ew-resize / nwse-resize cursors on those handles.
    assert "ew-resize" in text
    assert "nwse-resize" in text
    # Attach function.
    assert "attachPhaseResize" in text
    # Width stored on the node model.
    assert "node.w" in text


def test_annotation_structured_editing(tmp_path: Path) -> None:
    """Annotations offer preset dropdowns and structured fields per kind."""
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    # Schema table and helpers exist.
    assert "TAG_SCHEMAS" in text
    assert "makeTag" in text
    assert "compileTag" in text
    # Presets for common annotations.
    for preset in ("lever", "nose_poke", "touchscreen", "food", "water", "pellet"):
        assert preset in text, f"missing operandum/reinforcer preset: {preset}"
    # Species / strain presets.
    for species in ("rat", "mouse", "pigeon", "human"):
        assert species in text, f"missing species preset: {species}"
    for strain in ("Long-Evans", "Sprague-Dawley", "C57BL/6"):
        assert strain in text, f"missing strain preset: {strain}"
    # Datalist combobox (created at runtime).
    assert "'datalist'" in text or '"datalist"' in text
    # Structured ↔ raw toggle.
    assert "tag-toggle" in text


def test_dsl_text_import(tmp_path: Path) -> None:
    """The DSL output can be edited and parsed back into blocks."""
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    # Parser entry points.
    assert "parseProgram" in text
    assert "parseSchedule" in text
    assert "parseAtomic" in text
    assert "splitOffTags" in text
    # Edit / Apply / Cancel UI.
    assert 'id="editBtn"' in text
    assert 'id="applyBtn"' in text
    assert 'id="cancelBtn"' in text
    # Editing flag that prevents render() from clobbering user input.
    assert "editingDsl" in text
    # Keyboard shortcut: Ctrl/Cmd+Enter applies.
    assert "ctrlKey" in text and "metaKey" in text


def test_annotations_are_tags_not_wrappers(tmp_path: Path) -> None:
    """Annotations attach to a schedule as tags, not as wrapping containers."""
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    # The model stores tags on each node, and rendering has a tag row.
    assert "tags:" in text or "tags =" in text or "node.tags" in text
    assert "renderTag" in text


def test_undo_redo_history(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    assert "function undo" in text
    assert "function redo" in text
    assert "pushHistory" in text
    assert "HISTORY_LIMIT" in text
    assert 'id="undoBtn"' in text
    assert 'id="redoBtn"' in text


def test_duplicate_and_selection(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    assert "duplicateSelection" in text
    assert "duplicateTopLevel" in text
    assert "selection" in text and "selectOnly" in text and "toggleSelect" in text
    # Marquee selection rectangle.
    assert "initMarquee" in text
    assert "class: 'marquee'" in text or 'class: "marquee"' in text


def test_keyboard_shortcuts(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    # Arrow nudging, delete, duplicate, undo bindings.
    assert "ArrowLeft" in text and "ArrowRight" in text
    assert "Backspace" in text and "Delete" in text
    assert "initKeyboard" in text


def test_protocol_templates(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    assert "TEMPLATES" in text
    for tpl in (
        "A-B-A-B Reversal",
        "Multiple Baseline",
        "Progressive Ratio",
        "Concurrent VI VI Matching",
        "DRO Baseline + Treatment",
        "Chained VI",
    ):
        assert tpl in text, f"missing template: {tpl}"
    assert "applyTemplate" in text
    assert 'id="templatesBtn"' in text


def test_json_export_import(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    assert "exportJson" in text and "importJson" in text
    assert "Blob" in text
    assert "FileReader" in text
    assert 'id="exportJsonBtn"' in text
    assert 'id="importJsonBtn"' in text


def test_alignment_and_guides(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    assert "alignSelection" in text
    assert "align-guide" in text
    assert "SNAP_THRESHOLD" in text
    assert 'id="alignBtn"' in text
    # Distribute spacing.
    assert "distH" in text and "distV" in text


def test_comment_block_type(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    # Note chip in palette + comment category in render + compile excludes.
    assert 'data-kind="Note"' in text
    assert "category: 'comment'" in text or 'category: "comment"' in text
    # Comments are excluded from DSL output.
    assert "// not part of DSL" in text or "comment') return null" in text


def test_note_phase_resizes_both_axes(tmp_path: Path) -> None:
    """Note (comment) phases must support diagonal resize via the corner handle:
    width and height both. Other phase types stay width-only because their height
    is content-determined."""
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    # Two-axis bounds defined.
    assert "PHASE_MIN_H" in text
    assert "PHASE_MAX_H" in text
    # Resize helper is parameterised by axis.
    assert "function attachPhaseResize(handle, wrap, node, axes)" in text
    assert "axes === 'xy'" in text
    # Comment phases get the 'xy' axis on the corner handle, others stay 'x'.
    assert "node.category === 'comment' ? 'xy' : 'x'" in text
    # node.h is rendered onto the phase when set.
    assert "phase.style.height = node.h + 'px'" in text
    # Textarea no longer carries its own resize handle (phase corner owns it).
    assert "resize: none" in text
    # And the comment block becomes a flex column so the textarea fills the box.
    assert "phase.sized-h .block.comment" in text


def test_canvas_drop_accepts_note(tmp_path: Path) -> None:
    """Regression: the canvas-level drop handler must accept the Note (comment)
    payload as well as schedule payloads. Without this, the Note chip is silently
    discarded on drop because isSchedulePayload only returns true for
    atomic/compound/simple — Note carries cat='comment'."""
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    # A predicate broader than isSchedulePayload must exist and include 'comment'.
    assert "isCanvasNodePayload" in text
    assert "cat === 'comment'" in text
    # The viewport (vp) drop handler must use the broader predicate.
    canvas_drop_idx = text.find("// Palette drop onto canvas")
    assert canvas_drop_idx != -1, "canvas drop handler comment marker missing"
    snippet = text[canvas_drop_idx : canvas_drop_idx + 1000]
    assert "vp.addEventListener('drop'" in snippet
    assert "isCanvasNodePayload" in snippet, (
        "canvas drop handler still uses the schedule-only predicate; "
        "Note drops will be filtered out"
    )


def test_phase_color_and_link_badge(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    text = out.read_text(encoding="utf-8")
    # Phase color derived from @phase label.
    assert "phaseColor" in text
    assert "phase-color-stripe" in text
    # Annotation link map / linked badge.
    assert "annotationLinkMap" in text
    assert "linked" in text


def test_accepts_string_path(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(str(out))
    assert out.exists()
