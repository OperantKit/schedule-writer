"""Functional tests for the embedded JS parser.

These tests extract the <script> block from the generated HTML and execute
the parser under Node.js, asserting round-trip equivalence between DSL
text -> node tree -> DSL text.

Skipped automatically if ``node`` is not on PATH.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from schedule_writer.block_editor_html import generate_block_editor_html

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not available")


def _extract_script(html_path: Path) -> str:
    text = html_path.read_text(encoding="utf-8")
    m = re.search(r"<script>\s*'use strict';(.*?)</script>", text, re.DOTALL)
    assert m, "no inline <script> block found"
    return m.group(1)


def _run_node(html_path: Path, probe: str) -> str:
    """Run ``probe`` JS in an environment with the parser defined.

    The DOM-dependent parts of the script are replaced by a minimal stub so
    the parser, compiler, tag schema, and model factories all load without a
    browser. Node's output (a single JSON line from the probe) is returned.
    """
    script = _extract_script(html_path)
    # Strip DOM initialisation at the very end of the script.
    script = re.sub(
        r"\nload\(\);\s*initPalette\(\);\s*initViewport\(\);\s*initToolbar\(\);\s*render\(\);\s*$",
        "\n",
        script,
    )
    dom_stub = """
    // Minimal DOM stub: parser & compile logic do not need real DOM elements
    // except during render(). We replace document/localStorage with no-ops.
    var document = {
      getElementById: function () { return {
        style: {}, classList: { add() {}, remove() {}, contains() { return false; } },
        addEventListener() {}, removeEventListener() {},
        appendChild() {}, removeAttribute() {}, setAttribute() {},
        getBoundingClientRect() { return { left:0, top:0, width:0, height:0 }; },
        focus() {}, innerHTML: '', textContent: '', value: '',
      }; },
      querySelectorAll: function () { return []; },
      createElement: function () { return {
        style: {}, classList: { add(){}, remove(){}, contains(){return false;} },
        dataset: {}, addEventListener(){}, appendChild(){}, setAttribute(){},
      }; },
      createTextNode: function () { return {}; },
    };
    var window = { addEventListener() {}, removeEventListener() {} };
    var localStorage = { getItem() { return null; }, setItem() {} };
    """
    full = dom_stub + "\n" + script + "\n" + probe
    r = subprocess.run(
        [NODE, "-e", full],
        capture_output=True, text=True, timeout=10,
    )
    if r.returncode != 0:
        raise RuntimeError("node failed:\nstdout:\n" + r.stdout + "\nstderr:\n" + r.stderr)
    return r.stdout.strip()


def test_parse_round_trip_simple(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    probe = """
    const prog = parseProgram('FR 5\\nVI 30s\\nEXT');
    const lines = prog.nodes.map(compileNode).join('\\n');
    console.log(JSON.stringify({ lines: lines, count: prog.nodes.length }));
    """
    result = json.loads(_run_node(out, probe))
    assert result["count"] == 3
    assert result["lines"] == "FR 5\nVI 30s\nEXT"


def test_parse_round_trip_compound_with_tags(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    probe = """
    const src = 'Conc(VI 30s, VI 60s) @reinforcer(food) @timeout(5s)';
    const prog = parseProgram(src);
    const lines = prog.nodes.map(compileNode).join('\\n');
    console.log(JSON.stringify({ lines: lines, count: prog.nodes.length }));
    """
    result = json.loads(_run_node(out, probe))
    assert result["count"] == 1
    assert result["lines"] == "Conc(VI 30s, VI 60s) @reinforcer(food) @timeout(5s)"


def test_parse_multiline_phases(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    probe = """
    const src = [
      'EXT @phase("A1-baseline")',
      'FR 5 @reinforcer(food) @operandum(lever) @phase("B1")',
      'Chain(FR 10, VI 30s) @phase("B2")',
    ].join('\\n');
    const prog = parseProgram(src);
    const lines = prog.nodes.map(compileNode).join('\\n');
    console.log(JSON.stringify({ lines: lines, count: prog.nodes.length }));
    """
    result = json.loads(_run_node(out, probe))
    assert result["count"] == 3
    assert 'EXT @phase("A1-baseline")' in result["lines"]
    assert "FR 5 @reinforcer(food) @operandum(lever)" in result["lines"]
    assert "Chain(FR 10, VI 30s)" in result["lines"]


def test_parse_dro_mode(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    probe = """
    const prog = parseProgram('DRO 10s non-resetting');
    const lines = prog.nodes.map(compileNode).join('\\n');
    console.log(JSON.stringify({ lines: lines }));
    """
    result = json.loads(_run_node(out, probe))
    assert result["lines"] == "DRO 10s non-resetting"


def test_template_a_b_a_b_compiles(tmp_path: Path) -> None:
    """The A-B-A-B Reversal template compiles to four DSL lines."""
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    probe = """
    const tpl = TEMPLATES.find(t => t.name === 'A-B-A-B Reversal');
    program = tpl.build();
    const lines = program.nodes.map(compileNode).filter(s => s != null);
    console.log(JSON.stringify({ lines: lines, count: lines.length }));
    """
    result = json.loads(_run_node(out, probe))
    assert result["count"] == 4
    assert any("A1-baseline" in line for line in result["lines"])
    assert any("B1-treatment" in line and "FR 5" in line for line in result["lines"])
    assert any("A2-reversal" in line for line in result["lines"])
    assert any("B2-replication" in line for line in result["lines"])


def test_undo_redo_round_trip(tmp_path: Path) -> None:
    """Undo / redo restores program state through history snapshots."""
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    probe = """
    lastSnapshot = snapshot();
    program.nodes.push(makeSchedule('FR'));
    pushHistory();
    const afterAdd = program.nodes.length;
    // Reach into undo logic without invoking save/render which need DOM.
    const cur = snapshot();
    const prev = history.past.pop();
    history.future.push(cur);
    applySnapshot(prev);
    const afterUndo = program.nodes.length;
    // Redo
    const cur2 = snapshot();
    const nxt = history.future.pop();
    history.past.push(cur2);
    applySnapshot(nxt);
    const afterRedo = program.nodes.length;
    console.log(JSON.stringify({ afterAdd, afterUndo, afterRedo }));
    """
    result = json.loads(_run_node(out, probe))
    assert result["afterAdd"] == 1
    assert result["afterUndo"] == 0
    assert result["afterRedo"] == 1


def test_duplicate_creates_new_ids(tmp_path: Path) -> None:
    """duplicateTopLevel creates a deep clone with fresh IDs."""
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    probe = """
    const tpl = TEMPLATES.find(t => t.name === 'Concurrent VI VI Matching');
    program = tpl.build();
    const origId = program.nodes[0].id;
    const childId = program.nodes[0].children[0].id;
    const cloned = duplicateTopLevel(origId);
    console.log(JSON.stringify({
      origCount: program.nodes.length,
      origId, cloneId: cloned.id,
      origChildId: childId, cloneChildId: cloned.children[0].id,
    }));
    """
    result = json.loads(_run_node(out, probe))
    assert result["origCount"] == 2  # original + clone
    assert result["origId"] != result["cloneId"]
    assert result["origChildId"] != result["cloneChildId"]


def test_parse_error_has_line_number(tmp_path: Path) -> None:
    out = tmp_path / "blocks.html"
    generate_block_editor_html(out)
    probe = """
    try {
      parseProgram('FR 5\\nBOGUS_SCHEDULE');
      console.log(JSON.stringify({ ok: true }));
    } catch (e) {
      console.log(JSON.stringify({ err: e.message, line: e.lineNo }));
    }
    """
    result = json.loads(_run_node(out, probe))
    assert "ok" not in result
    assert result["line"] == 2
    assert "line 2" in result["err"]
