"""Generator for a single self-contained HTML schedule writer.

The output is a single ``.html`` file with vanilla CSS and JavaScript embedded;
no external network requests, no script tags pointing at CDNs. The generated
page mirrors the Python builder API: dropdowns to pick the schedule family,
inputs for parameters, dropdowns for compound combinators, and a read-only
text box that displays the resulting DSL string for copying.
"""

from __future__ import annotations

from pathlib import Path

# The HTML is kept as a single triple-quoted string so the file remains literally
# self-contained and trivially diffable. The JavaScript inside intentionally
# duplicates the formatting rules from ``builder.py`` so the page can run with
# zero Python at runtime.
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>schedule-writer</title>
<style>
  :root { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  body { max-width: 760px; margin: 2rem auto; padding: 0 1rem; color: #222; }
  h1 { font-size: 1.4rem; margin-bottom: 0.25rem; }
  .subtitle { color: #666; margin-top: 0; font-size: 0.95rem; }
  fieldset { border: 1px solid #ccc; border-radius: 6px; padding: 1rem; margin: 1rem 0; }
  legend { font-weight: 600; padding: 0 0.5rem; }
  label { display: inline-block; min-width: 7rem; margin-right: 0.5rem; }
  select, input[type=number], input[type=text] {
    padding: 0.25rem 0.5rem;
    border: 1px solid #aaa;
    border-radius: 4px;
    font: inherit;
  }
  .row { display: flex; align-items: center; gap: 0.5rem; margin: 0.4rem 0; }
  .components { display: flex; flex-direction: column; gap: 0.3rem; margin-top: 0.5rem; }
  .components input { flex: 1; }
  button {
    padding: 0.4rem 0.8rem;
    border: 1px solid #888;
    background: #f4f4f4;
    border-radius: 4px;
    cursor: pointer;
    font: inherit;
  }
  button:hover { background: #e8e8e8; }
  textarea {
    width: 100%;
    min-height: 4.5rem;
    margin-top: 0.5rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.95rem;
    padding: 0.5rem;
    border: 1px solid #aaa;
    border-radius: 4px;
    resize: vertical;
    box-sizing: border-box;
  }
  .hint { color: #666; font-size: 0.85rem; margin-top: 0.25rem; }
  .err { color: #b00020; font-size: 0.9rem; min-height: 1.2em; margin-top: 0.25rem; }
</style>
</head>
<body>

<h1>schedule-writer</h1>
<p class="subtitle">Compose contingency-dsl schedule strings without writing the grammar by hand.</p>

<fieldset>
  <legend>Atomic schedule</legend>
  <div class="row">
    <label for="atomicKind">Schedule</label>
    <select id="atomicKind">
      <optgroup label="Ratio">
        <option value="FR">FR — Fixed Ratio</option>
        <option value="VR">VR — Variable Ratio</option>
        <option value="RR">RR — Random Ratio (probability)</option>
      </optgroup>
      <optgroup label="Interval">
        <option value="FI">FI — Fixed Interval</option>
        <option value="VI">VI — Variable Interval</option>
        <option value="RI">RI — Random Interval (exponential)</option>
      </optgroup>
      <optgroup label="Time (response-independent)">
        <option value="FT">FT — Fixed Time</option>
        <option value="VT">VT — Variable Time</option>
        <option value="RT">RT — Random Time</option>
      </optgroup>
      <optgroup label="Differential">
        <option value="DRL">DRL — Diff. reinf. of low rate</option>
        <option value="DRH">DRH — Diff. reinf. of high rate</option>
        <option value="DRO">DRO — Diff. reinf. of other behavior</option>
      </optgroup>
      <optgroup label="Boundary">
        <option value="CRF">CRF — Continuous Reinforcement</option>
        <option value="EXT">EXT — Extinction</option>
      </optgroup>
    </select>
  </div>
  <div class="row" id="atomicValueRow">
    <label for="atomicValue">Value</label>
    <input id="atomicValue" type="number" min="0" step="any" value="5">
    <select id="atomicUnit">
      <option value="">(none)</option>
      <option value="s" selected>s</option>
      <option value="ms">ms</option>
      <option value="min">min</option>
    </select>
  </div>
  <div class="row">
    <button id="atomicBuild">Build atomic</button>
  </div>
  <div class="err" id="atomicErr"></div>
  <textarea id="atomicOut" readonly placeholder="Atomic DSL appears here"></textarea>
</fieldset>

<fieldset>
  <legend>Compound schedule</legend>
  <div class="row">
    <label for="combinator">Combinator</label>
    <select id="combinator">
      <option value="Conc">Conc — Concurrent</option>
      <option value="Mult">Mult — Multiple</option>
      <option value="Chain">Chain — Chained</option>
      <option value="Tand">Tand — Tandem</option>
      <option value="Alt">Alt — Alternative</option>
    </select>
  </div>
  <div class="hint">Type or paste the DSL string for each component (use the atomic builder above as a source).</div>
  <div class="components" id="components">
    <input type="text" placeholder="e.g. VI 30s" value="VI 30s">
    <input type="text" placeholder="e.g. VI 60s" value="VI 60s">
  </div>
  <div class="row" style="margin-top:0.5rem;">
    <button id="addComponent">+ component</button>
    <button id="removeComponent">- component</button>
    <button id="compoundBuild">Build compound</button>
  </div>
  <div class="err" id="compoundErr"></div>
  <textarea id="compoundOut" readonly placeholder="Compound DSL appears here"></textarea>
</fieldset>

<fieldset>
  <legend>Annotation</legend>
  <div class="hint">Append annotations like <code>@reinforcer(food)</code> to a schedule string.</div>
  <div class="row">
    <label for="annTarget">Schedule</label>
    <input id="annTarget" type="text" value="FR 5">
  </div>
  <div class="row">
    <label for="annText">Annotation</label>
    <input id="annText" type="text" value="@reinforcer(food)">
    <button id="annBuild">Apply</button>
  </div>
  <div class="err" id="annErr"></div>
  <textarea id="annOut" readonly placeholder="Annotated DSL appears here"></textarea>
</fieldset>

<script>
'use strict';

const TIME_UNITS = ['s', 'ms', 'min'];
const RATIO_KINDS = new Set(['FR', 'VR']);
const PROB_KINDS = new Set(['RR']);
const TIME_KINDS = new Set(['FI', 'VI', 'RI', 'FT', 'VT', 'RT', 'DRL', 'DRH', 'DRO']);
const NULLARY_KINDS = new Set(['CRF', 'EXT']);

function stripTrailingZero(value) {
  if (Number.isInteger(value)) return String(value);
  let s = value.toFixed(6);
  s = s.replace(/0+$/, '').replace(/\\.$/, '');
  return s || '0';
}

function buildAtomic() {
  const kind = document.getElementById('atomicKind').value;
  const valueEl = document.getElementById('atomicValue');
  const unit = document.getElementById('atomicUnit').value;
  const errEl = document.getElementById('atomicErr');
  errEl.textContent = '';

  if (NULLARY_KINDS.has(kind)) {
    document.getElementById('atomicOut').value = kind;
    return;
  }

  const raw = parseFloat(valueEl.value);
  if (!Number.isFinite(raw) || raw <= 0) {
    errEl.textContent = `${kind} requires a positive numeric value`;
    return;
  }

  if (RATIO_KINDS.has(kind)) {
    if (kind === 'FR' && !Number.isInteger(raw)) {
      errEl.textContent = 'FR requires an integer count';
      return;
    }
    document.getElementById('atomicOut').value = `${kind} ${stripTrailingZero(raw)}`;
    return;
  }

  if (PROB_KINDS.has(kind)) {
    if (raw <= 0 || raw > 1) {
      errEl.textContent = 'RR probability must be in (0, 1]';
      return;
    }
    document.getElementById('atomicOut').value = `${kind} ${stripTrailingZero(raw)}`;
    return;
  }

  if (TIME_KINDS.has(kind)) {
    if (!TIME_UNITS.includes(unit)) {
      errEl.textContent = `${kind} requires a time unit (s, ms, min)`;
      return;
    }
    document.getElementById('atomicOut').value = `${kind} ${stripTrailingZero(raw)}${unit}`;
    return;
  }

  errEl.textContent = `unknown schedule kind: ${kind}`;
}

function buildCompound() {
  const combinator = document.getElementById('combinator').value;
  const inputs = Array.from(document.querySelectorAll('#components input'));
  const errEl = document.getElementById('compoundErr');
  errEl.textContent = '';
  const components = inputs.map(i => i.value.trim()).filter(v => v.length > 0);
  if (components.length < 2) {
    errEl.textContent = `${combinator} requires at least 2 components`;
    return;
  }
  document.getElementById('compoundOut').value =
    `${combinator}(` + components.join(', ') + ')';
}

function applyAnnotation() {
  const target = document.getElementById('annTarget').value.trim();
  const ann = document.getElementById('annText').value.trim();
  const errEl = document.getElementById('annErr');
  errEl.textContent = '';
  if (!target) { errEl.textContent = 'schedule must be non-empty'; return; }
  if (!ann) { errEl.textContent = 'annotation must be non-empty'; return; }
  if (!ann.startsWith('@')) { errEl.textContent = "annotation must start with '@'"; return; }
  document.getElementById('annOut').value = `${target} ${ann}`;
}

function addComponent() {
  const wrap = document.getElementById('components');
  const input = document.createElement('input');
  input.type = 'text';
  input.placeholder = 'component DSL string';
  wrap.appendChild(input);
}

function removeComponent() {
  const wrap = document.getElementById('components');
  if (wrap.children.length > 2) {
    wrap.removeChild(wrap.lastElementChild);
  }
}

document.getElementById('atomicBuild').addEventListener('click', buildAtomic);
document.getElementById('compoundBuild').addEventListener('click', buildCompound);
document.getElementById('annBuild').addEventListener('click', applyAnnotation);
document.getElementById('addComponent').addEventListener('click', addComponent);
document.getElementById('removeComponent').addEventListener('click', removeComponent);

// Build something on load so users see a working example immediately.
buildAtomic();
buildCompound();
applyAnnotation();
</script>

</body>
</html>
"""


def generate_standalone_html(output_path: str | Path) -> None:
    """Write the self-contained HTML schedule writer to ``output_path``.

    The file is overwritten if it already exists. The generated page makes no
    network requests and embeds all CSS and JavaScript inline.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_HTML_TEMPLATE, encoding="utf-8")
