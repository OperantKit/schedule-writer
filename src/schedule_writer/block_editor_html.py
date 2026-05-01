"""Generator for a visual block-based editor HTML page (whiteboard-style).

The output is a single ``.html`` file with vanilla CSS and JavaScript embedded,
no external network requests. It exposes a palette of blocks on the left and
a pannable / zoomable 2D canvas on the right. Top-level schedule blocks are
placed as free-floating sticky notes at arbitrary ``(x, y)`` positions. Each
block keeps its **internal tree structure** (compound slots, annotation tags)
as a familiar nested card, but **multiple top-level phases coexist** on the
canvas and can be arranged, grouped, and compared visually.

Design goals
------------
* Practitioners arrange an A-B-A-B reversal design on a whiteboard-like
  canvas; each phase is a sticky note, pan/zoom for overview.
* DSL is compiled in **reading order** (top-to-bottom, then left-to-right)
  so arrangement has a predictable semantic effect.
* Zero build step, zero network dependency; works offline; auto-saves to
  ``localStorage``.
* Separate concern from :mod:`schedule_writer.standalone_html` (form-based
  UI): this is the block-based UI.

Data model (JS)
---------------
``program = { nodes: ScheduleNode[] }``::

    ScheduleNode := {
        id: string,
        kind: "FR" | "VI" | ... | "Conc" | ...,
        category: "atomic" | "compound" | "simple",
        params: { <name>: value },
        units:  { <name>: "s" | "ms" | "min" },
        children: (ScheduleNode | null)[],  // compound only
        tags:     string[],                 // suffix annotations
        x: number, y: number,               // world-coord position (top-level only)
    }
"""

from __future__ import annotations

from pathlib import Path

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>schedule-writer — block editor</title>
<style>
  :root { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  body { margin: 0; color: #222; background: #fafafa; height: 100vh; overflow: hidden; display: flex; flex-direction: column; }
  header.app { padding: 0.6rem 1rem; background: #fff; border-bottom: 1px solid #e0e0e0; flex: 0 0 auto; }
  header.app h1 { margin: 0 0 0.1rem 0; font-size: 1.1rem; }
  header.app p { margin: 0; color: #666; font-size: 0.82rem; }
  main { display: grid; grid-template-columns: 260px 1fr 320px; gap: 0.75rem; padding: 0.75rem; flex: 1 1 auto; min-height: 0; }
  section { background: #fff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 0.6rem; overflow: auto; min-height: 0; }
  section#viewport-section { padding: 0; overflow: hidden; display: flex; flex-direction: column; }
  section h2 { margin: 0 0 0.4rem 0; font-size: 0.95rem; color: #333; }
  .hint { color: #777; font-size: 0.78rem; margin: 0.2rem 0 0.45rem; }
  code { background: #f1f1f1; padding: 0 0.2rem; border-radius: 3px; font-size: 0.85em; }

  /* Palette */
  .palette-group { margin-bottom: 0.65rem; }
  .palette-group h3 { margin: 0 0 0.25rem 0; font-size: 0.75rem; color: #555; text-transform: uppercase; letter-spacing: 0.04em; }
  .palette-group h3 small { font-weight: normal; color: #999; text-transform: none; letter-spacing: 0; }
  .chip {
    display: inline-block;
    margin: 0.12rem 0.18rem 0.12rem 0;
    padding: 0.18rem 0.5rem;
    border-radius: 999px;
    font-size: 0.8rem;
    cursor: grab;
    user-select: none;
    border: 1px solid transparent;
  }
  .chip:active { cursor: grabbing; }
  .chip.atomic { background: #e3f2fd; color: #0b3d66; border-color: #b6dbf5; }
  .chip.compound { background: #fff3e0; color: #6b3a00; border-color: #f3d3ab; }
  .chip.annotation { background: #ede7f6; color: #3c1a79; border-color: #c8b6e8; }
  .chip.simple { background: #eceff1; color: #37474f; border-color: #cfd8dc; }

  /* Viewport / world */
  .viewport-toolbar {
    display: flex;
    gap: 0.35rem;
    padding: 0.4rem 0.6rem;
    background: #f7f7f7;
    border-bottom: 1px solid #e0e0e0;
    align-items: center;
    flex: 0 0 auto;
    font-size: 0.8rem;
    color: #666;
  }
  .viewport-toolbar button {
    padding: 0.2rem 0.55rem;
    border: 1px solid #bbb;
    background: #fff;
    border-radius: 3px;
    cursor: pointer;
    font: inherit;
    font-size: 0.78rem;
  }
  .viewport-toolbar button:hover { background: #f0f0f0; }
  .viewport-toolbar .spacer { flex: 1 1 auto; }
  #viewport {
    position: relative;
    flex: 1 1 auto;
    overflow: hidden;
    background:
      radial-gradient(circle, #d8d8d8 1px, transparent 1.2px) 0 0 / 24px 24px,
      #fafafa;
    cursor: grab;
    min-height: 0;
  }
  #viewport.panning { cursor: grabbing; }
  #world {
    position: absolute;
    left: 0; top: 0;
    width: 1px; height: 1px;
    transform-origin: 0 0;
    will-change: transform;
  }
  .empty-hint {
    position: absolute;
    left: 50%; top: 50%;
    transform: translate(-50%, -50%);
    color: #aaa;
    font-size: 0.9rem;
    pointer-events: none;
    text-align: center;
  }

  /* Blocks */
  .phase {
    position: absolute;
    min-width: 180px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    border-radius: 6px;
    user-select: none;
  }
  .phase.selected { box-shadow: 0 0 0 2px #1976d2, 0 2px 8px rgba(25,118,210,0.25); }
  .phase-color-stripe {
    position: absolute;
    top: 0; left: 0;
    width: 5px; height: 100%;
    border-radius: 6px 0 0 6px;
    pointer-events: none;
  }
  .block.comment {
    background: #fff8c4;
    border-color: #ddc56a;
    display: flex;
    flex-direction: column;
  }
  .phase.sized-h .block.comment { height: 100%; }
  .block.comment textarea {
    width: 100%;
    min-height: 4rem;
    flex: 1;
    border: none;
    background: transparent;
    font: inherit;
    font-size: 0.85rem;
    resize: none;
    padding: 0.15rem 0;
    box-sizing: border-box;
  }
  .block.comment textarea:focus { outline: 1px solid #c79a00; }
  .marquee {
    position: absolute;
    border: 1.5px dashed #1976d2;
    background: rgba(25,118,210,0.08);
    pointer-events: none;
    z-index: 50;
  }
  .align-guide {
    position: absolute;
    background: #1976d2;
    pointer-events: none;
    z-index: 49;
  }
  .align-guide.h { height: 1px; }
  .align-guide.v { width: 1px; }
  .tag.linked::after {
    content: "🔗";
    margin-left: 0.15rem;
    font-size: 0.7rem;
    opacity: 0.7;
  }
  .menu {
    position: absolute;
    background: #fff;
    border: 1px solid #ccc;
    border-radius: 4px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.15);
    padding: 0.25rem 0;
    z-index: 100;
    min-width: 240px;
    max-height: 360px;
    overflow: auto;
  }
  .menu-item {
    padding: 0.35rem 0.75rem;
    font-size: 0.85rem;
    cursor: pointer;
    white-space: nowrap;
  }
  .menu-item:hover { background: #eef6ff; }
  .menu-item small { display: block; color: #888; font-size: 0.72rem; }
  .phase:not(.sized) { max-width: 440px; }
  .resize-handle {
    position: absolute;
    right: -4px;
    top: 10%;
    width: 8px;
    height: 80%;
    cursor: ew-resize;
    background: transparent;
    z-index: 2;
  }
  .resize-handle:hover,
  .resize-handle.active {
    background: linear-gradient(to right, transparent, rgba(25,118,210,0.45));
    border-right: 2px solid #1976d2;
    border-radius: 0 3px 3px 0;
  }
  .resize-handle-br {
    position: absolute;
    right: -2px;
    bottom: -2px;
    width: 12px;
    height: 12px;
    cursor: nwse-resize;
    background: transparent;
    z-index: 2;
  }
  .resize-handle-br::after {
    content: "";
    position: absolute;
    right: 2px; bottom: 2px;
    width: 8px; height: 8px;
    border-right: 2px solid #888;
    border-bottom: 2px solid #888;
    border-radius: 0 0 3px 0;
    opacity: 0;
    transition: opacity 0.12s;
  }
  .phase:hover .resize-handle-br::after { opacity: 0.6; }
  .resize-handle-br:hover::after,
  .resize-handle-br.active::after { opacity: 1; border-color: #1976d2; }
  .block {
    border-radius: 6px;
    border: 1px solid #ccc;
    background: #fff;
    padding: 0.45rem 0.6rem;
  }
  .block.atomic { background: #e3f2fd; border-color: #90caf9; }
  .block.compound { background: #fff3e0; border-color: #f5c77e; }
  .block.simple { background: #eceff1; border-color: #b0bec5; }
  .block.has-error { outline: 2px solid #b00020; outline-offset: 1px; }

  .block-head {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex-wrap: wrap;
  }
  .drag-handle {
    cursor: grab;
    color: #888;
    font-size: 1rem;
    line-height: 1;
    user-select: none;
    padding: 0 0.15rem;
  }
  .drag-handle:active { cursor: grabbing; }
  .block-title { font-weight: 600; font-size: 0.88rem; white-space: nowrap; }
  .block .params { display: inline-flex; gap: 0.3rem; align-items: center; flex-wrap: wrap; }
  .block input[type=number], .block input[type=text], .block select {
    padding: 0.1rem 0.3rem;
    border: 1px solid #bbb;
    border-radius: 3px;
    font: inherit;
    font-size: 0.82rem;
    background: #fff;
  }
  .block input[type=number] { width: 4.8rem; }
  .block-actions { margin-left: auto; display: inline-flex; gap: 0.2rem; }
  .icon-btn {
    background: transparent;
    border: 1px solid #bbb;
    border-radius: 3px;
    padding: 0 0.35rem;
    cursor: pointer;
    font-size: 0.8rem;
    color: #555;
    line-height: 1.3;
  }
  .icon-btn:hover { background: #f0f0f0; }
  .icon-btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .icon-btn.remove:hover { background: #fee; color: #b00020; border-color: #e88; }

  .block.drag-tag { outline: 2px dashed #6a1b9a; outline-offset: 2px; }

  /* Tags */
  .tag-row {
    margin-top: 0.35rem;
    display: flex;
    gap: 0.25rem;
    flex-wrap: wrap;
    align-items: center;
  }
  .tag {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    background: #ede7f6;
    border: 1px solid #b39ddb;
    color: #3c1a79;
    padding: 0.05rem 0.4rem;
    border-radius: 999px;
    font-size: 0.78rem;
  }
  .tag input[type=text] {
    background: transparent;
    border: none;
    font: inherit;
    font-size: 0.78rem;
    padding: 0;
    color: #3c1a79;
  }
  .tag input[type=text]:focus { outline: 1px solid #7e57c2; background: #fff; }
  .tag-kind {
    font-weight: 600;
    color: #4a1670;
  }
  .tag-select, .tag-num, .tag-text {
    padding: 0 0.25rem;
    border: 1px solid #b39ddb;
    border-radius: 3px;
    background: #fff;
    font: inherit;
    font-size: 0.78rem;
    color: #3c1a79;
    min-width: 3rem;
  }
  .tag-num { width: 3.5rem; }
  .tag-combo-wrap { display: inline-block; }
  .tag-toggle {
    background: transparent;
    border: 1px solid #d1c4e9;
    border-radius: 3px;
    padding: 0 0.3rem;
    color: #6a1b9a;
    cursor: pointer;
    font-size: 0.7rem;
    margin-left: 0.15rem;
  }
  .tag-toggle:hover { background: #f3e5f5; }
  .tag-remove {
    background: transparent;
    border: none;
    color: #6a1b9a;
    cursor: pointer;
    font-size: 0.8rem;
    padding: 0;
    line-height: 1;
  }
  .tag-hint { color: #aaa; font-size: 0.72rem; font-style: italic; }

  /* Slots (compound children) */
  .slot {
    margin-top: 0.35rem;
    padding: 0.3rem 0.45rem 0.3rem 1.0rem;
    border-left: 3px solid #e0a657;
  }
  .slot-label { font-size: 0.72rem; color: #8a5a00; margin-bottom: 0.1rem; }
  .slot-drop {
    border: 1px dashed #b39256;
    border-radius: 4px;
    padding: 0.3rem 0.5rem;
    background: rgba(255, 255, 255, 0.5);
    color: #b39256;
    font-size: 0.78rem;
    font-style: italic;
    text-align: center;
  }
  .slot-drop.drag-over { background: #fff6e3; border-color: #e08a00; border-style: solid; color: #6b3a00; }

  /* Output sidebar */
  #output-section { display: flex; flex-direction: column; }
  #output {
    width: 100%;
    flex: 1 1 auto;
    min-height: 6rem;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.88rem;
    padding: 0.5rem;
    border: 1px solid #aaa;
    border-radius: 4px;
    box-sizing: border-box;
    resize: vertical;
    background: #fff;
    white-space: pre;
  }
  .err { color: #b00020; font-size: 0.82rem; min-height: 1.1em; margin-top: 0.35rem; }
  .toolbar { display: flex; gap: 0.4rem; margin-top: 0.5rem; flex-wrap: wrap; }
  .toolbar button {
    padding: 0.3rem 0.7rem;
    border: 1px solid #888;
    background: #f4f4f4;
    border-radius: 4px;
    cursor: pointer;
    font: inherit;
    font-size: 0.85rem;
  }
  .toolbar button:hover { background: #e8e8e8; }
</style>
</head>
<body>

<header class="app">
  <h1>schedule-writer — block editor</h1>
  <p>Drag blocks from the palette onto the canvas; each phase is a sticky note you can drag freely. Drop annotations onto a block to attach them. DSL is compiled in reading order (top→bottom, then left→right). Ctrl+wheel to zoom, drag empty canvas to pan.</p>
</header>

<main>

<section id="palette" aria-label="Block palette">
  <h2>Palette</h2>

  <div class="palette-group">
    <h3>Ratio</h3>
    <span class="chip atomic" draggable="true" data-kind="FR" data-cat="atomic" title="Fixed Ratio">FR</span>
    <span class="chip atomic" draggable="true" data-kind="VR" data-cat="atomic" title="Variable Ratio">VR</span>
    <span class="chip atomic" draggable="true" data-kind="RR" data-cat="atomic" title="Random Ratio (probability)">RR</span>
  </div>
  <div class="palette-group">
    <h3>Interval</h3>
    <span class="chip atomic" draggable="true" data-kind="FI" data-cat="atomic" title="Fixed Interval">FI</span>
    <span class="chip atomic" draggable="true" data-kind="VI" data-cat="atomic" title="Variable Interval (Fleshler-Hoffman)">VI</span>
    <span class="chip atomic" draggable="true" data-kind="RI" data-cat="atomic" title="Random Interval (exponential)">RI</span>
  </div>
  <div class="palette-group">
    <h3>Time (response-independent)</h3>
    <span class="chip atomic" draggable="true" data-kind="FT" data-cat="atomic" title="Fixed Time">FT</span>
    <span class="chip atomic" draggable="true" data-kind="VT" data-cat="atomic" title="Variable Time">VT</span>
    <span class="chip atomic" draggable="true" data-kind="RT" data-cat="atomic" title="Random Time">RT</span>
  </div>
  <div class="palette-group">
    <h3>Differential</h3>
    <span class="chip atomic" draggable="true" data-kind="DRL" data-cat="atomic">DRL</span>
    <span class="chip atomic" draggable="true" data-kind="DRH" data-cat="atomic">DRH</span>
    <span class="chip atomic" draggable="true" data-kind="DRO" data-cat="atomic">DRO</span>
  </div>
  <div class="palette-group">
    <h3>Continuous / Extinction</h3>
    <span class="chip simple" draggable="true" data-kind="CRF" data-cat="simple" title="Continuous Reinforcement">CRF</span>
    <span class="chip simple" draggable="true" data-kind="EXT" data-cat="simple" title="Extinction">EXT</span>
  </div>
  <div class="palette-group">
    <h3>Compound</h3>
    <span class="chip compound" draggable="true" data-kind="Conc" data-cat="compound" title="Concurrent">Conc</span>
    <span class="chip compound" draggable="true" data-kind="Mult" data-cat="compound" title="Multiple">Mult</span>
    <span class="chip compound" draggable="true" data-kind="Chain" data-cat="compound" title="Chained">Chain</span>
    <span class="chip compound" draggable="true" data-kind="Tand" data-cat="compound" title="Tandem">Tand</span>
    <span class="chip compound" draggable="true" data-kind="Alt" data-cat="compound" title="Alternative">Alt</span>
  </div>
  <div class="palette-group">
    <h3>Note <small>(visual only, not in DSL)</small></h3>
    <span class="chip" draggable="true" data-kind="Note" data-cat="comment" title="Sticky note for comments / references" style="background:#fff8c4;color:#7d5e00;border-color:#ddc56a;">Note</span>
  </div>

  <div class="palette-group">
    <h3>Annotation <small>(drop onto a block)</small></h3>
    <p class="hint">Suffix tags on a schedule. Drop onto an existing block to attach; text is editable.</p>
    <span class="chip annotation" draggable="true" data-kind="@reinforcer" data-cat="annotation">@reinforcer</span>
    <span class="chip annotation" draggable="true" data-kind="@operandum" data-cat="annotation">@operandum</span>
    <span class="chip annotation" draggable="true" data-kind="@response" data-cat="annotation">@response</span>
    <span class="chip annotation" draggable="true" data-kind="@timeout" data-cat="annotation">@timeout</span>
    <span class="chip annotation" draggable="true" data-kind="@phase" data-cat="annotation">@phase</span>
    <span class="chip annotation" draggable="true" data-kind="@session_end" data-cat="annotation">@session_end</span>
    <span class="chip annotation" draggable="true" data-kind="@subject" data-cat="annotation">@subject</span>
    <span class="chip annotation" draggable="true" data-kind="@custom" data-cat="annotation">@custom</span>
  </div>
</section>

<section id="viewport-section" aria-label="Program canvas">
  <div class="viewport-toolbar">
    <button id="undoBtn" type="button" title="Undo (Ctrl+Z)">↶ Undo</button>
    <button id="redoBtn" type="button" title="Redo (Ctrl+Shift+Z)">↷ Redo</button>
    <button id="templatesBtn" type="button" title="Insert a protocol template">Templates ▾</button>
    <button id="alignBtn" type="button" title="Align selected blocks">Align ▾</button>
    <span class="spacer"></span>
    <button id="resetViewBtn" type="button" title="Fit all blocks">Reset view</button>
    <button id="zoomInBtn" type="button">＋</button>
    <button id="zoomOutBtn" type="button">－</button>
    <span id="zoomLabel">100%</span>
    <span class="spacer"></span>
    <button id="exportJsonBtn" type="button" title="Download program as .json">Export</button>
    <button id="importJsonBtn" type="button" title="Load program from .json">Import</button>
    <input type="file" id="importJsonFile" accept="application/json,.json" style="display:none;">
    <button id="clearBtn" type="button">Clear</button>
  </div>
  <div id="viewport" aria-label="Program canvas (pan with empty-area drag, zoom with Ctrl+wheel)">
    <div id="world"></div>
    <div id="emptyHint" class="empty-hint">
      Drag a block from the palette onto the canvas to begin.<br>
      <small>Ctrl+wheel zoom · drag empty area to pan · Shift+drag to marquee-select<br>
        Ctrl+Z undo · Ctrl+D duplicate · Backspace delete · arrows to nudge</small>
    </div>
  </div>
</section>

<section id="output-section" aria-label="DSL output">
  <h2>DSL output</h2>
  <p class="hint">Compiled in reading order. Click <b>Edit</b> to paste or type DSL text and have it parsed back into blocks.</p>
  <textarea id="output" readonly placeholder="Drop a block onto the canvas to begin, or click Edit to paste DSL"></textarea>
  <div class="err" id="err"></div>
  <div class="toolbar">
    <button id="copyBtn" type="button">Copy DSL</button>
    <button id="editBtn" type="button">Edit</button>
    <button id="applyBtn" type="button" style="display:none;">Apply</button>
    <button id="cancelBtn" type="button" style="display:none;">Cancel</button>
    <span class="hint" style="margin-left:auto;align-self:center;">Auto-saves locally.</span>
  </div>
</section>

</main>

<script>
'use strict';

// ==========================================================================
// Specifications
// ==========================================================================

const TIME_UNITS = ['s', 'ms', 'min'];
const DRO_MODES = ['resetting', 'non-resetting'];
const STORAGE_KEY = 'schedule-writer-block-editor:program:v3';

const ATOMIC_SPECS = {
  FR:  { params: [{ name: 'n',    kind: 'int',   default: 5  }] },
  VR:  { params: [{ name: 'mean', kind: 'float', default: 10 }] },
  RR:  { params: [{ name: 'p',    kind: 'prob',  default: 0.1 }] },
  FI:  { params: [{ name: 't',    kind: 'time',  default: 30 }] },
  VI:  { params: [{ name: 't',    kind: 'time',  default: 30 }] },
  RI:  { params: [{ name: 't',    kind: 'time',  default: 30 }] },
  FT:  { params: [{ name: 't',    kind: 'time',  default: 30 }] },
  VT:  { params: [{ name: 't',    kind: 'time',  default: 30 }] },
  RT:  { params: [{ name: 't',    kind: 'time',  default: 30 }] },
  DRL: { params: [{ name: 't',    kind: 'time',  default: 10 }] },
  DRH: { params: [{ name: 't',    kind: 'time',  default: 10 }] },
  DRO: { params: [
    { name: 't',    kind: 'time', default: 10 },
    { name: 'mode', kind: 'mode', default: 'resetting' },
  ] },
};
const SIMPLE_KINDS = { CRF: true, EXT: true };
const COMPOUND_SPECS = {
  Conc:  { minChildren: 2 },
  Mult:  { minChildren: 2 },
  Chain: { minChildren: 2 },
  Tand:  { minChildren: 2 },
  Alt:   { minChildren: 2 },
};
// Strain presets keyed by species — empirical defaults for behavior research.
const STRAIN_PRESETS = {
  rat:    ['Long-Evans', 'Sprague-Dawley', 'Wistar', 'Lister Hooded'],
  mouse:  ['C57BL/6', 'BALB/c', 'DBA/2', '129S', 'CD-1'],
  pigeon: ['White Carneau', 'Silver King', 'Homing'],
  human:  [],
  other:  [],
};

// TAG_SCHEMAS drives structured annotation editing.
//   params[i] := { name, type: 'combo'|'select'|'number'|'text', presets?, options?, default }
//   format(values) -> DSL tag string
//   parse: RegExp; parseMap(match) -> values (used when migrating a raw string)
const TAG_SCHEMAS = {
  '@reinforcer': {
    params: [{ name: 'kind', type: 'combo',
               presets: ['food', 'water', 'pellet', 'sucrose', 'milk', 'saccharin', 'brain-stimulation'],
               default: 'food' }],
    format: (v) => '@reinforcer(' + (v.kind || '') + ')',
    parse:  /^@reinforcer\(\s*([^)]+?)\s*\)$/,
    parseMap: (m) => ({ kind: m[1] }),
  },
  '@operandum': {
    params: [{ name: 'kind', type: 'combo',
               presets: ['lever', 'nose_poke', 'key', 'touchscreen', 'wheel', 'chain', 'chamber'],
               default: 'lever' }],
    format: (v) => '@operandum(' + (v.kind || '') + ')',
    parse:  /^@operandum\(\s*([^)]+?)\s*\)$/,
    parseMap: (m) => ({ kind: m[1] }),
  },
  '@response': {
    params: [
      { name: 'key',   type: 'combo', presets: ['force', 'duration', 'topography'], default: 'force' },
      { name: 'value', type: 'text',  default: '0.15N' },
    ],
    format: (v) => '@response(' + (v.key || '') + '=' + (v.value || '') + ')',
    parse:  /^@response\(\s*(\w+)\s*=\s*([^)]+?)\s*\)$/,
    parseMap: (m) => ({ key: m[1], value: m[2] }),
  },
  '@timeout': {
    params: [
      { name: 't',    type: 'number', default: 5 },
      { name: 'unit', type: 'select', options: ['s', 'ms', 'min'], default: 's' },
    ],
    format: (v) => '@timeout(' + (v.t ?? '') + (v.unit || 's') + ')',
    parse:  /^@timeout\(\s*(\d*\.?\d+)\s*(s|ms|min)\s*\)$/,
    parseMap: (m) => ({ t: m[1], unit: m[2] }),
  },
  '@phase': {
    params: [{ name: 'label', type: 'text', default: 'A1-baseline' }],
    format: (v) => '@phase("' + (v.label || '') + '")',
    parse:  /^@phase\(\s*"?([^"()]+?)"?\s*\)$/,
    parseMap: (m) => ({ label: m[1] }),
  },
  '@session_end': {
    params: [
      { name: 'key',   type: 'combo', presets: ['reinforcers', 'responses', 'duration', 'time'], default: 'reinforcers' },
      { name: 'value', type: 'text',  default: '60' },
    ],
    format: (v) => '@session_end(' + (v.key || '') + '=' + (v.value || '') + ')',
    parse:  /^@session_end\(\s*(\w+)\s*=\s*([^)]+?)\s*\)$/,
    parseMap: (m) => ({ key: m[1], value: m[2] }),
  },
  '@subject': {
    params: [
      { name: 'species', type: 'combo', presets: ['rat', 'mouse', 'pigeon', 'human', 'other'], default: 'rat' },
      { name: 'strain',  type: 'combo', presets: STRAIN_PRESETS.rat, default: 'Long-Evans' },
    ],
    // Dynamic strain presets driven by species selection.
    strainFor: (species) => STRAIN_PRESETS[species] || [],
    format: (v) => {
      const sp = (v.species || '').trim();
      const st = (v.strain || '').trim();
      if (!sp) return '@subject()';
      if (!st) return '@subject(species="' + sp + '")';
      return '@subject(species="' + sp + '", strain="' + st + '")';
    },
    parse:  /^@subject\(\s*species\s*=\s*"([^"]+)"(?:\s*,\s*strain\s*=\s*"([^"]+)")?\s*\)$/,
    parseMap: (m) => ({ species: m[1], strain: m[2] || '' }),
  },
  '@custom': null,  // free-form raw tag only
};

function makeTag(kind) {
  if (kind === '@custom' || !(kind in TAG_SCHEMAS) || !TAG_SCHEMAS[kind]) {
    return { kind: '@custom', values: {}, raw: '@tag' };
  }
  const schema = TAG_SCHEMAS[kind];
  const values = {};
  for (const p of schema.params) values[p.name] = p.default;
  return { kind, values, raw: null };
}

// Convert a legacy string tag into the object form.
function migrateTag(x) {
  if (x && typeof x === 'object') return x;
  if (typeof x !== 'string') return { kind: '@custom', values: {}, raw: '@tag' };
  for (const k in TAG_SCHEMAS) {
    const s = TAG_SCHEMAS[k];
    if (!s) continue;
    const m = x.match(s.parse);
    if (m) return { kind: k, values: s.parseMap(m), raw: null };
  }
  return { kind: '@custom', values: {}, raw: x };
}

function compileTag(tag) {
  if (!tag) return '';
  if (tag.raw != null) return tag.raw.trim();
  const schema = TAG_SCHEMAS[tag.kind];
  if (!schema) return '';
  return schema.format(tag.values || {});
}

// ==========================================================================
// Model
// ==========================================================================

let nextId = 1;
function genId() { return 'b' + (nextId++); }

let program = { nodes: [] };
let view = { tx: 40, ty: 40, scale: 1 };

function makeSchedule(kind) {
  if (kind === 'Note') {
    return { id: genId(), kind: 'Note', category: 'comment',
             params: {}, units: {}, children: [], tags: [],
             text: '', x: 0, y: 0 };
  }
  if (SIMPLE_KINDS[kind]) {
    return { id: genId(), kind, category: 'simple', params: {}, units: {},
             children: [], tags: [], x: 0, y: 0 };
  }
  if (kind in ATOMIC_SPECS) {
    const params = {}, units = {};
    for (const p of ATOMIC_SPECS[kind].params) {
      params[p.name] = p.default;
      if (p.kind === 'time') units[p.name] = 's';
    }
    return { id: genId(), kind, category: 'atomic', params, units,
             children: [], tags: [], x: 0, y: 0 };
  }
  if (kind in COMPOUND_SPECS) {
    return { id: genId(), kind, category: 'compound', params: {}, units: {},
             children: [null, null], tags: [], x: 0, y: 0 };
  }
  throw new Error('unknown schedule kind: ' + kind);
}


function findParent(id) {
  for (let i = 0; i < program.nodes.length; i++) {
    if (program.nodes[i] && program.nodes[i].id === id) return { list: program.nodes, index: i };
    const inner = findInNode(program.nodes[i], id);
    if (inner) return inner;
  }
  return null;
}
function findInNode(node, id) {
  if (!node || !node.children) return null;
  for (let i = 0; i < node.children.length; i++) {
    if (node.children[i] && node.children[i].id === id) return { list: node.children, index: i };
    const r = findInNode(node.children[i], id);
    if (r) return r;
  }
  return null;
}
function removeNode(id) {
  const loc = findParent(id);
  if (!loc) return;
  if (loc.list === program.nodes) loc.list.splice(loc.index, 1);
  else loc.list[loc.index] = null;
}
function moveChildInCompound(id, delta) {
  const loc = findParent(id);
  if (!loc || loc.list === program.nodes) return;
  const j = loc.index + delta;
  if (j < 0 || j >= loc.list.length) return;
  const tmp = loc.list[loc.index];
  loc.list[loc.index] = loc.list[j];
  loc.list[j] = tmp;
}

// ==========================================================================
// Compile
// ==========================================================================

function stripTrailingZero(v) {
  if (Number.isInteger(v)) return String(v);
  let s = Number(v).toFixed(6);
  s = s.replace(/0+$/, '').replace(/\.$/, '');
  return s || '0';
}

function compileBase(node) {
  if (node.category === 'comment') return null;  // not part of DSL
  if (node.category === 'simple') return node.kind;
  if (node.category === 'atomic') return compileAtomic(node);
  if (node.category === 'compound') {
    const spec = COMPOUND_SPECS[node.kind];
    const filled = node.children.filter(c => c != null);
    if (filled.length < spec.minChildren) {
      throw new Error(node.kind + ' needs at least ' + spec.minChildren + ' components');
    }
    const parts = node.children.map((c, i) => {
      if (c == null) throw new Error(node.kind + ' slot ' + (i + 1) + ' is empty');
      return compileNode(c);
    });
    return node.kind + '(' + parts.join(', ') + ')';
  }
  throw new Error('unknown category: ' + node.category);
}

function compileAtomic(node) {
  const kind = node.kind;
  if (kind === 'FR') {
    const n = parseInt(node.params.n, 10);
    if (!Number.isFinite(n) || n <= 0) throw new Error('FR requires a positive integer');
    return 'FR ' + n;
  }
  if (kind === 'VR') {
    const v = parseFloat(node.params.mean);
    if (!Number.isFinite(v) || v <= 0) throw new Error('VR requires a positive mean');
    return 'VR ' + stripTrailingZero(v);
  }
  if (kind === 'RR') {
    const p = parseFloat(node.params.p);
    if (!Number.isFinite(p) || p <= 0 || p > 1) throw new Error('RR probability must be in (0, 1]');
    return 'RR ' + stripTrailingZero(p);
  }
  const t = parseFloat(node.params.t);
  if (!Number.isFinite(t) || t <= 0) throw new Error(kind + ' requires a positive duration');
  const unit = node.units.t || 's';
  if (!TIME_UNITS.includes(unit)) throw new Error(kind + ' unit invalid: ' + unit);
  let out = kind + ' ' + stripTrailingZero(t) + unit;
  if (kind === 'DRO') {
    const mode = node.params.mode || 'resetting';
    if (mode !== 'resetting') {
      if (!DRO_MODES.includes(mode)) throw new Error('DRO mode invalid: ' + mode);
      out += ' ' + mode;
    }
  }
  return out;
}

function compileNode(node) {
  let s = compileBase(node);
  if (s == null) return null;  // comment / note — no DSL output
  for (const tag of (node.tags || [])) {
    const t = compileTag(tag).trim();
    if (!t) continue;
    if (!t.startsWith('@')) throw new Error("annotation must start with '@': " + JSON.stringify(t));
    s += ' ' + t;
  }
  return s;
}

function compileProgram() {
  // Reading order: top→bottom, then left→right, banded by Y within ~80px.
  const nodes = program.nodes.filter(n => n);
  const ordered = [...nodes].sort((a, b) => {
    const dy = (a.y || 0) - (b.y || 0);
    if (Math.abs(dy) > 40) return dy;
    return (a.x || 0) - (b.x || 0);
  });
  const lines = [];
  const errors = {};
  for (const node of ordered) {
    try {
      const s = compileNode(node);
      if (s != null) lines.push(s);
    }
    catch (exc) { errors[node.id] = exc.message; markDescendantErrors(node, errors); lines.push(''); }
  }
  return { text: lines.join('\n'), errors };
}

function markDescendantErrors(node, errors) {
  if (!node) return;
  try { compileBase(node); } catch (exc) { errors[node.id] = exc.message; }
  if (node.children) for (const c of node.children) markDescendantErrors(c, errors);
}

// ==========================================================================
// Parser (DSL text -> node tree)
// ==========================================================================
//
// Grammar (informal, matches builder output):
//   program  := line ("\n" line)*
//   line     := schedule (WS tag)*              -- top-level suffix tags
//   schedule := atomic | compound
//   atomic   := KIND
//             | KIND WS <num>                   -- ratio / probability
//             | KIND WS <num><unit> (WS mode)?  -- time-based, DRO optional mode
//   compound := COMPOUND_KIND "(" arg ("," arg)* ")"
//   arg      := schedule (WS tag)*              -- children may carry tags
//   tag      := "@" IDENT ("(" ... ")")?

function splitOffTags(line) {
  // Return { schedule, tags: string[] } for "SCHEDULE @tag1 @tag2".
  let depth = 0, inStr = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (inStr) { if (c === '"') inStr = false; continue; }
    if (c === '"') { inStr = true; continue; }
    else if (c === '(') depth++;
    else if (c === ')') depth--;
    else if (c === '@' && depth === 0 &&
             (i === 0 || /\s/.test(line[i - 1]))) {
      return {
        schedule: line.slice(0, i).trim(),
        tags: splitTopLevelTags(line.slice(i)),
      };
    }
  }
  return { schedule: line.trim(), tags: [] };
}

function splitTopLevelTags(text) {
  const tags = [];
  let depth = 0, inStr = false, start = 0;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inStr) { if (c === '"') inStr = false; continue; }
    if (c === '"') { inStr = true; continue; }
    else if (c === '(') depth++;
    else if (c === ')') depth--;
    else if (depth === 0 && /\s/.test(c) && text[i + 1] === '@') {
      tags.push(text.slice(start, i).trim());
      start = i + 1;
    }
  }
  if (start < text.length) {
    const last = text.slice(start).trim();
    if (last) tags.push(last);
  }
  return tags;
}

function splitTopLevelArgs(s) {
  const out = [];
  let depth = 0, inStr = false, start = 0;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (inStr) { if (c === '"') inStr = false; continue; }
    if (c === '"') { inStr = true; continue; }
    else if (c === '(') depth++;
    else if (c === ')') depth--;
    else if (c === ',' && depth === 0) {
      out.push(s.slice(start, i).trim());
      start = i + 1;
    }
  }
  if (start < s.length) {
    const last = s.slice(start).trim();
    if (last) out.push(last);
  }
  return out;
}

function parseAtomic(src) {
  const s = src.trim();
  if (SIMPLE_KINDS[s]) return makeSchedule(s);
  const m = s.match(/^([A-Z]+)(?:\s+(.+))?$/);
  if (!m) throw new Error('cannot parse atomic: ' + JSON.stringify(src));
  const kind = m[1];
  const rest = (m[2] || '').trim();
  if (!(kind in ATOMIC_SPECS)) throw new Error('unknown schedule kind: ' + kind);
  const node = makeSchedule(kind);
  const spec = ATOMIC_SPECS[kind];
  if (spec.params.length === 0) return node;

  if (kind === 'FR') {
    const n = parseInt(rest, 10);
    if (!Number.isFinite(n)) throw new Error('FR needs integer count: ' + JSON.stringify(rest));
    node.params.n = n;
    return node;
  }
  if (kind === 'VR') {
    const v = parseFloat(rest);
    if (!Number.isFinite(v)) throw new Error('VR needs numeric mean: ' + JSON.stringify(rest));
    node.params.mean = v;
    return node;
  }
  if (kind === 'RR') {
    const p = parseFloat(rest);
    if (!Number.isFinite(p)) throw new Error('RR needs numeric probability: ' + JSON.stringify(rest));
    node.params.p = p;
    return node;
  }

  // Time-based: <num><unit?> possibly followed by space-separated mode / unit.
  const tokens = rest.split(/\s+/);
  const first = tokens[0] || '';
  const tm = first.match(/^(\d*\.?\d+)(s|ms|min)?$/);
  if (!tm) throw new Error(kind + ' needs a duration: ' + JSON.stringify(rest));
  node.params.t = parseFloat(tm[1]);
  let unit = tm[2] || null;
  for (const tok of tokens.slice(1)) {
    if (TIME_UNITS.includes(tok)) unit = tok;
    else if (kind === 'DRO' && DRO_MODES.includes(tok)) node.params.mode = tok;
    else throw new Error(kind + ' has extra token: ' + JSON.stringify(tok));
  }
  node.units.t = unit || 's';
  return node;
}

function parseSchedule(src) {
  const s = src.trim();
  const m = s.match(/^([A-Za-z]+)\s*\((.*)\)\s*$/s);
  if (m && m[1] in COMPOUND_SPECS) {
    const kind = m[1];
    const args = splitTopLevelArgs(m[2]);
    if (args.length === 0) throw new Error(kind + ' has no components');
    const children = args.map(parseArg);
    const node = makeSchedule(kind);
    node.children = children;
    return node;
  }
  return parseAtomic(s);
}

function parseArg(src) {
  // A compound child may carry its own tags.
  const parts = splitOffTags(src);
  const node = parseSchedule(parts.schedule);
  node.tags = parts.tags.map(migrateTag);
  return node;
}

function parseProgram(text) {
  const lines = text.split('\n');
  const nodes = [];
  let autoX = 40, autoY = 40;
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i].trim();
    if (!raw) continue;
    let node;
    try {
      const parts = splitOffTags(raw);
      node = parseSchedule(parts.schedule);
      node.tags = parts.tags.map(migrateTag);
    } catch (exc) {
      const err = new Error('line ' + (i + 1) + ': ' + exc.message);
      err.lineNo = i + 1;
      throw err;
    }
    node.x = autoX;
    node.y = autoY;
    autoY += 160;
    if (autoY > 720) { autoY = 40; autoX += 300; }
    nodes.push(node);
  }
  return { nodes };
}

// ==========================================================================
// Persistence
// ==========================================================================

function save() {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ program, nextId, view })); }
  catch (_) { /* quota/private mode */ }
}
function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw);
    if (parsed && parsed.program && Array.isArray(parsed.program.nodes)) {
      program = parsed.program;
      if (typeof parsed.nextId === 'number') nextId = parsed.nextId;
      if (parsed.view && typeof parsed.view.scale === 'number') view = parsed.view;
      // Migrate legacy string tags to the object form.
      const walk = (n) => {
        if (!n) return;
        if (Array.isArray(n.tags)) n.tags = n.tags.map(migrateTag);
        if (Array.isArray(n.children)) n.children.forEach(walk);
      };
      program.nodes.forEach(walk);
    }
  } catch (_) { /* corrupt: start fresh */ }
}

// ==========================================================================
// DOM helpers
// ==========================================================================

function el(tag, attrs, children) {
  const e = document.createElement(tag);
  if (attrs) {
    for (const k in attrs) {
      const v = attrs[k];
      if (v == null) continue;
      if (k === 'class') e.className = v;
      else if (k === 'dataset') Object.assign(e.dataset, v);
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else if (typeof v === 'boolean') { if (v) e.setAttribute(k, ''); }
      else e.setAttribute(k, v);
    }
  }
  if (children) for (const c of children) {
    if (c == null || c === false) continue;
    e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  }
  return e;
}

// ==========================================================================
// Viewport (pan + zoom)
// ==========================================================================

function applyView() {
  const world = document.getElementById('world');
  world.style.transform = 'translate(' + view.tx + 'px, ' + view.ty + 'px) scale(' + view.scale + ')';
  const lbl = document.getElementById('zoomLabel');
  if (lbl) lbl.textContent = Math.round(view.scale * 100) + '%';
}

function clientToWorld(cx, cy) {
  const vp = document.getElementById('viewport');
  const r = vp.getBoundingClientRect();
  return {
    x: (cx - r.left - view.tx) / view.scale,
    y: (cy - r.top  - view.ty) / view.scale,
  };
}

function initViewport() {
  const vp = document.getElementById('viewport');

  // Pan (Shift = marquee select instead, see initMarquee)
  let pan = null;
  let panMoved = false;
  vp.addEventListener('mousedown', (e) => {
    if (e.shiftKey) return;
    if (e.target !== vp && e.target.id !== 'world' && e.target.id !== 'emptyHint') return;
    if (e.button !== 0) return;
    pan = { sx: e.clientX, sy: e.clientY, tx0: view.tx, ty0: view.ty };
    panMoved = false;
    vp.classList.add('panning');
  });
  window.addEventListener('mousemove', (e) => {
    if (!pan) return;
    const dx = e.clientX - pan.sx, dy = e.clientY - pan.sy;
    if (dx * dx + dy * dy > 9) panMoved = true;
    view.tx = pan.tx0 + dx;
    view.ty = pan.ty0 + dy;
    applyView();
  });
  window.addEventListener('mouseup', () => {
    if (pan) {
      const wasPan = pan;
      pan = null;
      vp.classList.remove('panning');
      if (!panMoved && selection.size > 0) {
        // Click on empty canvas without drag → clear selection.
        clearSelection();
      } else if (panMoved) {
        save();
      }
    }
  });

  // Zoom
  vp.addEventListener('wheel', (e) => {
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    const r = vp.getBoundingClientRect();
    const px = e.clientX - r.left, py = e.clientY - r.top;
    const wx = (px - view.tx) / view.scale;
    const wy = (py - view.ty) / view.scale;
    const factor = Math.exp(-e.deltaY * 0.001);
    const newScale = Math.max(0.25, Math.min(3, view.scale * factor));
    view.scale = newScale;
    view.tx = px - wx * view.scale;
    view.ty = py - wy * view.scale;
    applyView();
    save();
  }, { passive: false });

  // Palette drop onto canvas
  vp.addEventListener('dragover', (e) => {
    // Accept schedule drops (annotation drops are caught by block handlers first).
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  });
  vp.addEventListener('drop', (e) => {
    const { cat, kind } = decodePayload(e.dataTransfer.getData('text/plain'));
    if (!isCanvasNodePayload(cat)) return;  // annotations attach to blocks, not the canvas
    e.preventDefault();
    const w = clientToWorld(e.clientX, e.clientY);
    const node = makeSchedule(kind);
    node.x = w.x - 20;   // small offset so the grip sits under the cursor
    node.y = w.y - 12;
    program.nodes.push(node);
    dirty();
  });
}

function resetView() {
  const nodes = program.nodes.filter(n => n);
  if (nodes.length === 0) { view = { tx: 40, ty: 40, scale: 1 }; applyView(); save(); return; }
  const xs = nodes.map(n => n.x || 0);
  const ys = nodes.map(n => n.y || 0);
  const minX = Math.min(...xs), minY = Math.min(...ys);
  const maxX = Math.max(...xs) + 260, maxY = Math.max(...ys) + 180;
  const vp = document.getElementById('viewport');
  const r = vp.getBoundingClientRect();
  const sx = (r.width  - 40) / Math.max(1, maxX - minX);
  const sy = (r.height - 40) / Math.max(1, maxY - minY);
  view.scale = Math.max(0.25, Math.min(1.5, Math.min(sx, sy)));
  view.tx = 20 - minX * view.scale;
  view.ty = 20 - minY * view.scale;
  applyView();
  save();
}

function zoomBy(factor) {
  const vp = document.getElementById('viewport');
  const r = vp.getBoundingClientRect();
  const px = r.width / 2, py = r.height / 2;
  const wx = (px - view.tx) / view.scale;
  const wy = (py - view.ty) / view.scale;
  view.scale = Math.max(0.25, Math.min(3, view.scale * factor));
  view.tx = px - wx * view.scale;
  view.ty = py - wy * view.scale;
  applyView();
  save();
}

// ==========================================================================
// Drag & drop payload
// ==========================================================================

function encodePayload(cat, kind) { return cat + ':' + kind; }
function decodePayload(raw) {
  const i = (raw || '').indexOf(':');
  if (i < 0) return { cat: '', kind: raw || '' };
  return { cat: raw.slice(0, i), kind: raw.slice(i + 1) };
}
function isSchedulePayload(cat) {
  return cat === 'atomic' || cat === 'compound' || cat === 'simple';
}
function isCanvasNodePayload(cat) {
  // Canvas root accepts schedules and free-floating sticky notes.
  return isSchedulePayload(cat) || cat === 'comment';
}

function attachScheduleDropTarget(elt, onSchedule) {
  elt.addEventListener('dragover', (e) => {
    e.preventDefault(); e.stopPropagation();
    elt.classList.add('drag-over');
  });
  elt.addEventListener('dragleave', () => elt.classList.remove('drag-over'));
  elt.addEventListener('drop', (e) => {
    e.preventDefault(); e.stopPropagation();
    elt.classList.remove('drag-over');
    const { cat, kind } = decodePayload(e.dataTransfer.getData('text/plain'));
    if (!isSchedulePayload(cat)) return;
    onSchedule(kind);
    dirty();
  });
}

function attachAnnotationDropTarget(elt, node) {
  elt.addEventListener('dragover', (e) => {
    if (!(e.dataTransfer.types || []).includes('text/plain')) return;
    e.preventDefault();
    elt.classList.add('drag-tag');
  });
  elt.addEventListener('dragleave', () => elt.classList.remove('drag-tag'));
  elt.addEventListener('drop', (e) => {
    const { cat, kind } = decodePayload(e.dataTransfer.getData('text/plain'));
    elt.classList.remove('drag-tag');
    if (cat !== 'annotation') return;  // schedule drops bubble up to viewport
    e.preventDefault();
    e.stopPropagation();
    node.tags.push(makeTag(kind));
    dirty();
  });
}

// ==========================================================================
// Block-move (2D free drag of top-level phase)
// ==========================================================================

const PHASE_MIN_W = 180;
const PHASE_MAX_W = 900;
const PHASE_MIN_H = 80;
const PHASE_MAX_H = 800;

function attachPhaseResize(handle, wrap, node, axes) {
  // axes: 'x' = width only (default, edge handle / non-comment corner)
  //       'xy' = both axes (sticky-note style, comment corner)
  axes = axes || 'x';
  handle.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    const rect = wrap.getBoundingClientRect();
    const startW = node.w || rect.width / view.scale;
    const startH = node.h || rect.height / view.scale;
    const start = { cx: e.clientX, cy: e.clientY, w0: startW, h0: startH };
    handle.classList.add('active');
    const onMove = (ev) => {
      let w = start.w0 + (ev.clientX - start.cx) / view.scale;
      w = Math.max(PHASE_MIN_W, Math.min(PHASE_MAX_W, w));
      node.w = w;
      wrap.classList.add('sized');
      wrap.style.width = w + 'px';
      if (axes === 'xy') {
        let h = start.h0 + (ev.clientY - start.cy) / view.scale;
        h = Math.max(PHASE_MIN_H, Math.min(PHASE_MAX_H, h));
        node.h = h;
        wrap.classList.add('sized-h');
        wrap.style.height = h + 'px';
      }
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      handle.classList.remove('active');
      dirty();
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  });
  // Double-click to reset to content-fit size.
  handle.addEventListener('dblclick', (e) => {
    e.stopPropagation();
    delete node.w;
    wrap.classList.remove('sized');
    wrap.style.width = '';
    if (axes === 'xy') {
      delete node.h;
      wrap.classList.remove('sized-h');
      wrap.style.height = '';
    }
    dirty();
  });
}

const SNAP_THRESHOLD = 6;  // screen-px tolerance before snapping to alignment

function attachPhaseSelect(wrap, node) {
  // Click (no drag) on the phase wrapper toggles / sets selection.
  let downAt = null;
  wrap.addEventListener('mousedown', (e) => {
    if (e.target.closest('input, select, button, textarea, .tag-toggle, .tag-remove, .resize-handle, .resize-handle-br')) return;
    if (e.button !== 0) return;
    downAt = { x: e.clientX, y: e.clientY, shift: e.shiftKey };
  });
  wrap.addEventListener('mouseup', (e) => {
    if (!downAt) return;
    const dx = e.clientX - downAt.x, dy = e.clientY - downAt.y;
    if (dx * dx + dy * dy < 9) {  // click threshold (3px)
      if (downAt.shift) toggleSelect(node.id);
      else selectOnly(node.id);
    }
    downAt = null;
  });
}

function attachPhaseMove(wrap, node) {
  wrap.addEventListener('mousedown', (e) => {
    if (e.target.closest('input, select, button, textarea, .tag-toggle, .tag-remove, .slot-drop, .resize-handle, .resize-handle-br')) return;
    if (e.button !== 0) return;
    e.stopPropagation();

    // Movers: if this node is part of selection, move all selected together.
    // Otherwise, move just this node (and select only it).
    let movers;
    if (selection.has(node.id) && selection.size > 1) {
      movers = program.nodes.filter(n => n && selection.has(n.id));
    } else {
      movers = [node];
      if (!selection.has(node.id)) {
        selection = new Set([node.id]);
      }
    }
    const startPos = movers.map(m => ({ node: m, x0: m.x || 0, y0: m.y || 0 }));
    const start = { cx: e.clientX, cy: e.clientY };
    const guides = [];

    const others = program.nodes.filter(n => n && !movers.includes(n));
    const phaseEls = {};
    document.querySelectorAll('#world .phase').forEach((p) => { phaseEls[p.dataset.id] = p; });

    const moverDims = movers.map(m => {
      const r = phaseEls[m.id] ? phaseEls[m.id].getBoundingClientRect() : { width: 220, height: 80 };
      return { id: m.id, w: r.width / view.scale, h: r.height / view.scale };
    });
    const otherSpans = others.map(o => {
      const r = phaseEls[o.id] ? phaseEls[o.id].getBoundingClientRect() : { width: 220, height: 80 };
      return {
        x1: o.x || 0, y1: o.y || 0,
        x2: (o.x || 0) + r.width / view.scale,
        y2: (o.y || 0) + r.height / view.scale,
      };
    });

    const onMove = (ev) => {
      let dx = (ev.clientX - start.cx) / view.scale;
      let dy = (ev.clientY - start.cy) / view.scale;

      // Compute snap candidates from the FIRST mover only.
      const m0 = startPos[0];
      const md0 = moverDims[0];
      const snapTol = SNAP_THRESHOLD / view.scale;
      let snapDx = null, snapDy = null;
      let guideX = null, guideY = null;
      const candX = [m0.x0 + dx, m0.x0 + dx + md0.w / 2, m0.x0 + dx + md0.w];
      const candY = [m0.y0 + dy, m0.y0 + dy + md0.h / 2, m0.y0 + dy + md0.h];
      for (const o of otherSpans) {
        const oxs = [o.x1, (o.x1 + o.x2) / 2, o.x2];
        const oys = [o.y1, (o.y1 + o.y2) / 2, o.y2];
        for (let ci = 0; ci < candX.length; ci++) {
          for (const ox of oxs) {
            const d = ox - candX[ci];
            if (Math.abs(d) < snapTol && (snapDx == null || Math.abs(d) < Math.abs(snapDx))) {
              snapDx = d; guideX = ox;
            }
          }
        }
        for (let ci = 0; ci < candY.length; ci++) {
          for (const oy of oys) {
            const d = oy - candY[ci];
            if (Math.abs(d) < snapTol && (snapDy == null || Math.abs(d) < Math.abs(snapDy))) {
              snapDy = d; guideY = oy;
            }
          }
        }
      }
      if (snapDx != null) dx += snapDx;
      if (snapDy != null) dy += snapDy;

      // Apply to all movers.
      for (const sp of startPos) {
        sp.node.x = sp.x0 + dx;
        sp.node.y = sp.y0 + dy;
        const elt = phaseEls[sp.node.id];
        if (elt) {
          elt.style.left = sp.node.x + 'px';
          elt.style.top  = sp.node.y + 'px';
        }
      }

      // Render guides as world-coord overlays.
      const world = document.getElementById('world');
      guides.forEach(g => g.remove());
      guides.length = 0;
      if (guideX != null) {
        const g = el('div', { class: 'align-guide v' });
        g.style.left = guideX + 'px';
        g.style.top = (Math.min(m0.y0 + dy, ...otherSpans.map(o => o.y1)) - 200) + 'px';
        g.style.height = '4000px';
        world.appendChild(g);
        guides.push(g);
      }
      if (guideY != null) {
        const g = el('div', { class: 'align-guide h' });
        g.style.top = guideY + 'px';
        g.style.left = (Math.min(m0.x0 + dx, ...otherSpans.map(o => o.x1)) - 200) + 'px';
        g.style.width = '4000px';
        world.appendChild(g);
        guides.push(g);
      }
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      guides.forEach(g => g.remove());
      dirty();
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  });
}

// ==========================================================================
// Marquee selection
// ==========================================================================

function initMarquee() {
  const vp = document.getElementById('viewport');
  vp.addEventListener('mousedown', (e) => {
    if (!e.shiftKey) return;
    if (e.target !== vp && e.target.id !== 'world' && e.target.id !== 'emptyHint') return;
    if (e.button !== 0) return;
    e.preventDefault();
    const r = vp.getBoundingClientRect();
    const startCx = e.clientX, startCy = e.clientY;
    const box = el('div', { class: 'marquee' });
    vp.appendChild(box);
    const onMove = (ev) => {
      const x1 = Math.min(startCx, ev.clientX), y1 = Math.min(startCy, ev.clientY);
      const x2 = Math.max(startCx, ev.clientX), y2 = Math.max(startCy, ev.clientY);
      box.style.left = (x1 - r.left) + 'px';
      box.style.top  = (y1 - r.top) + 'px';
      box.style.width = (x2 - x1) + 'px';
      box.style.height = (y2 - y1) + 'px';
    };
    const onUp = (ev) => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      const w1 = clientToWorld(Math.min(startCx, ev.clientX), Math.min(startCy, ev.clientY));
      const w2 = clientToWorld(Math.max(startCx, ev.clientX), Math.max(startCy, ev.clientY));
      box.remove();
      const sel = new Set();
      const phases = document.querySelectorAll('#world .phase');
      for (const p of phases) {
        const id = p.dataset.id;
        const node = program.nodes.find(n => n && n.id === id);
        if (!node) continue;
        const pr = p.getBoundingClientRect();
        const wp = node.w || (pr.width / view.scale);
        const hp = pr.height / view.scale;
        const cx = (node.x || 0) + wp / 2;
        const cy = (node.y || 0) + hp / 2;
        if (cx >= w1.x && cx <= w2.x && cy >= w1.y && cy <= w2.y) sel.add(id);
      }
      selection = sel;
      render();
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  });
}

// ==========================================================================
// Rendering
// ==========================================================================

function renderNode(node, parentList, indexInParent, errors) {
  const wrap = el('div', { class: 'block ' + node.category, dataset: { id: node.id } });
  if (errors[node.id]) { wrap.classList.add('has-error'); wrap.title = errors[node.id]; }

  const head = el('div', { class: 'block-head' });
  const isTopLevel = parentList === program.nodes;
  if (isTopLevel) {
    head.appendChild(el('span', { class: 'drag-handle', title: 'Drag to move phase' }, ['⠿']));
  }
  head.appendChild(el('span', { class: 'block-title' }, [node.kind]));

  if (node.category === 'atomic') head.appendChild(renderParams(node));
  head.appendChild(renderBlockActions(node, parentList, indexInParent));
  wrap.appendChild(head);

  if (node.category === 'comment') {
    const ta = el('textarea', { placeholder: 'Notes (not part of DSL)' });
    ta.value = node.text || '';
    ta.addEventListener('input', () => { node.text = ta.value; save(); });
    ta.addEventListener('mousedown', (e) => e.stopPropagation());
    wrap.appendChild(ta);
    return wrap;
  }

  wrap.appendChild(renderTagRow(node));

  if (node.category === 'compound') {
    for (let i = 0; i < node.children.length; i++) {
      wrap.appendChild(renderSlot(node, i, errors));
    }
    wrap.appendChild(renderSlotControls(node));
  }

  attachAnnotationDropTarget(wrap, node);
  return wrap;
}

function renderParams(node) {
  const params = el('span', { class: 'params' });
  const spec = ATOMIC_SPECS[node.kind];
  for (const p of spec.params) {
    if (p.kind === 'time') {
      const num = el('input', { type: 'number', min: '0', step: 'any', value: node.params[p.name] });
      num.addEventListener('input', () => { node.params[p.name] = num.value; dirty(); });
      const unit = el('select');
      for (const u of TIME_UNITS) {
        const opt = el('option', { value: u }, [u]);
        if (node.units[p.name] === u) opt.selected = true;
        unit.appendChild(opt);
      }
      unit.addEventListener('change', () => { node.units[p.name] = unit.value; dirty(); });
      params.appendChild(num); params.appendChild(unit);
    } else if (p.kind === 'mode') {
      const sel = el('select');
      for (const m of DRO_MODES) {
        const opt = el('option', { value: m }, [m]);
        if (node.params[p.name] === m) opt.selected = true;
        sel.appendChild(opt);
      }
      sel.addEventListener('change', () => { node.params[p.name] = sel.value; dirty(); });
      params.appendChild(sel);
    } else {
      const num = el('input', { type: 'number', min: '0', step: 'any', value: node.params[p.name] });
      num.addEventListener('input', () => { node.params[p.name] = num.value; dirty(); });
      params.appendChild(num);
    }
  }
  return params;
}

function renderBlockActions(node, parentList, indexInParent) {
  const actions = el('div', { class: 'block-actions' });
  const isCompoundChild = parentList && parentList !== program.nodes;
  if (isCompoundChild) {
    const upBtn = el('button', { class: 'icon-btn', type: 'button', title: 'Move up' }, ['↑']);
    const dnBtn = el('button', { class: 'icon-btn', type: 'button', title: 'Move down' }, ['↓']);
    upBtn.disabled = indexInParent === 0;
    dnBtn.disabled = indexInParent === parentList.length - 1;
    upBtn.addEventListener('click', (e) => { e.stopPropagation(); moveChildInCompound(node.id, -1); dirty(); });
    dnBtn.addEventListener('click', (e) => { e.stopPropagation(); moveChildInCompound(node.id,  1); dirty(); });
    actions.appendChild(upBtn); actions.appendChild(dnBtn);
  }
  const rmBtn = el('button', { class: 'icon-btn remove', type: 'button', title: 'Remove' }, ['×']);
  rmBtn.addEventListener('click', (e) => { e.stopPropagation(); removeNode(node.id); dirty(); });
  actions.appendChild(rmBtn);
  return actions;
}

function renderTagRow(node) {
  const row = el('div', { class: 'tag-row' });
  if (!node.tags || node.tags.length === 0) {
    row.appendChild(el('span', { class: 'tag-hint' }, ['(drop an annotation here)']));
    return row;
  }
  for (let i = 0; i < node.tags.length; i++) row.appendChild(renderTag(node, i));
  return row;
}

function renderTag(node, tagIndex) {
  const tag = node.tags[tagIndex];
  const chip = el('span', { class: 'tag', dataset: { kind: tag.kind || '@custom' } });
  // Stop phase-move / pan when interacting with any part of the tag.
  chip.addEventListener('mousedown', (e) => e.stopPropagation());

  const schema = TAG_SCHEMAS[tag.kind];
  const isRaw = tag.raw != null || !schema;

  if (isRaw) {
    chip.appendChild(renderTagRawInput(node, tagIndex));
  } else {
    chip.appendChild(el('span', { class: 'tag-kind' }, [tag.kind]));
    for (const p of schema.params) {
      chip.appendChild(renderTagField(node, tagIndex, p));
    }
  }

  // Toggle between structured ↔ raw text entry.
  if (schema) {
    const toggleLabel = isRaw ? 'fields' : 'raw';
    const toggleTitle = isRaw
      ? 'Switch to structured fields'
      : 'Switch to free-form text';
    const toggle = el('button', {
      class: 'tag-toggle', type: 'button', title: toggleTitle,
    }, [toggleLabel]);
    toggle.addEventListener('click', (e) => {
      e.stopPropagation();
      if (isRaw) {
        // Try to parse current raw text back into values.
        const parsed = migrateTag(tag.raw || '');
        if (parsed.kind === tag.kind) {
          tag.values = parsed.values;
          tag.raw = null;
        } else {
          // Parsing failed — reset to defaults for this kind.
          const fresh = makeTag(tag.kind);
          tag.values = fresh.values;
          tag.raw = null;
        }
      } else {
        // Freeze current structured rendering into raw text.
        tag.raw = compileTag(tag);
      }
      dirty();
    });
    chip.appendChild(toggle);
  }

  const rm = el('button', { class: 'tag-remove', type: 'button', title: 'Remove tag' }, ['×']);
  rm.addEventListener('click', (e) => { e.stopPropagation(); node.tags.splice(tagIndex, 1); dirty(); });
  chip.appendChild(rm);
  return chip;
}

function renderTagRawInput(node, tagIndex) {
  const tag = node.tags[tagIndex];
  const input = el('input', {
    type: 'text', value: tag.raw || '', spellcheck: 'false',
    'aria-label': 'Annotation text',
  });
  const sizeToContent = () => { input.size = Math.max(6, (input.value || '').length + 1); };
  input.addEventListener('input', () => { tag.raw = input.value; sizeToContent(); dirty(); });
  sizeToContent();
  return input;
}

function renderTagField(node, tagIndex, param) {
  const tag = node.tags[tagIndex];
  const current = tag.values[param.name] ?? '';

  // Dynamic presets: @subject strain depends on species.
  let presets = param.presets || [];
  if (tag.kind === '@subject' && param.name === 'strain') {
    const sch = TAG_SCHEMAS['@subject'];
    presets = sch.strainFor(tag.values.species);
  }

  const setValue = (v) => {
    tag.values[param.name] = v;
    // If species changed, snap strain to the new species' default if invalid.
    if (tag.kind === '@subject' && param.name === 'species') {
      const strains = TAG_SCHEMAS['@subject'].strainFor(v);
      const cur = tag.values.strain || '';
      if (strains.length === 0) tag.values.strain = '';
      else if (!strains.includes(cur)) tag.values.strain = strains[0];
    }
    dirty();
  };

  if (param.type === 'select') {
    const sel = el('select', { class: 'tag-select' });
    for (const opt of (param.options || [])) {
      const o = el('option', { value: opt }, [opt]);
      if (String(current) === String(opt)) o.selected = true;
      sel.appendChild(o);
    }
    sel.addEventListener('change', () => setValue(sel.value));
    return sel;
  }

  if (param.type === 'number') {
    const input = el('input', {
      type: 'number', step: 'any', class: 'tag-num',
      value: String(current),
    });
    input.addEventListener('input', () => setValue(input.value));
    return input;
  }

  // 'text' or 'combo'
  const wrap = el('span', { class: 'tag-combo-wrap' });
  const listId = 'dl-' + tag.kind.replace(/[^a-zA-Z]/g, '') + '-' + param.name + '-' + node.id + '-' + tagIndex;
  const input = el('input', {
    type: 'text', class: 'tag-text',
    value: String(current),
    spellcheck: 'false',
    list: (param.type === 'combo' ? listId : null),
    'aria-label': param.name,
  });
  const sizeToContent = () => { input.size = Math.max(5, (input.value || '').length + 1); };
  input.addEventListener('input', () => { setValue(input.value); sizeToContent(); });
  sizeToContent();
  wrap.appendChild(input);
  if (param.type === 'combo') {
    const dl = el('datalist', { id: listId });
    for (const p of presets) dl.appendChild(el('option', { value: p }));
    wrap.appendChild(dl);
  }
  return wrap;
}

function renderSlot(parent, index, errors) {
  const slot = el('div', { class: 'slot' });
  slot.appendChild(el('div', { class: 'slot-label' }, ['slot ' + (index + 1)]));
  const child = parent.children[index];
  if (child) {
    slot.appendChild(renderNode(child, parent.children, index, errors));
  } else {
    const drop = el('div', { class: 'slot-drop' }, ['(drop a schedule here)']);
    attachScheduleDropTarget(drop, (kind) => { parent.children[index] = makeSchedule(kind); });
    slot.appendChild(drop);
  }
  return slot;
}

function renderSlotControls(node) {
  const bar = el('div', { class: 'toolbar' });
  const addBtn = el('button', { type: 'button' }, ['+ slot']);
  addBtn.addEventListener('click', (e) => { e.stopPropagation(); node.children.push(null); dirty(); });
  const subBtn = el('button', { type: 'button' }, ['- slot']);
  subBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (node.children.length > COMPOUND_SPECS[node.kind].minChildren) { node.children.pop(); dirty(); }
  });
  bar.appendChild(addBtn); bar.appendChild(subBtn);
  return bar;
}

// ==========================================================================
// Top-level render
// ==========================================================================

let editingDsl = false;

// ==========================================================================
// History (undo / redo)
// ==========================================================================

const HISTORY_LIMIT = 100;
let history = { past: [], future: [] };
let lastSnapshot = null;

function snapshot() {
  return JSON.parse(JSON.stringify({ program, view, nextId }));
}
function applySnapshot(s) {
  program = s.program;
  view = s.view || view;
  nextId = s.nextId || nextId;
}
function pushHistory() {
  if (lastSnapshot) {
    history.past.push(lastSnapshot);
    history.future = [];
    if (history.past.length > HISTORY_LIMIT) history.past.shift();
  }
  lastSnapshot = snapshot();
}
function undo() {
  if (history.past.length === 0) return;
  const cur = snapshot();
  const prev = history.past.pop();
  history.future.push(cur);
  applySnapshot(prev);
  lastSnapshot = snapshot();
  save(); render();
}
function redo() {
  if (history.future.length === 0) return;
  const cur = snapshot();
  const nxt = history.future.pop();
  history.past.push(cur);
  applySnapshot(nxt);
  lastSnapshot = snapshot();
  save(); render();
}

function dirty() {
  pushHistory();
  save(); render();
}

// ==========================================================================
// Selection
// ==========================================================================

let selection = new Set();

function selectOnly(id) { selection = new Set([id]); render(); }
function toggleSelect(id) {
  if (selection.has(id)) selection.delete(id); else selection.add(id);
  render();
}
function clearSelection() { selection = new Set(); render(); }
function selectedTopLevel() {
  return program.nodes.filter(n => n && selection.has(n.id));
}

// ==========================================================================
// Duplicate
// ==========================================================================

function deepCloneWithNewIds(node) {
  if (!node) return null;
  const clone = JSON.parse(JSON.stringify(node));
  function reId(n) {
    if (!n) return;
    n.id = genId();
    if (Array.isArray(n.children)) n.children.forEach(reId);
  }
  reId(clone);
  return clone;
}
function duplicateTopLevel(id) {
  const idx = program.nodes.findIndex(n => n && n.id === id);
  if (idx < 0) return null;
  const clone = deepCloneWithNewIds(program.nodes[idx]);
  clone.x = (clone.x || 0) + 24;
  clone.y = (clone.y || 0) + 24;
  program.nodes.splice(idx + 1, 0, clone);
  return clone;
}
function duplicateSelection() {
  const ids = [...selection];
  if (ids.length === 0) return;
  const newIds = [];
  for (const id of ids) {
    const c = duplicateTopLevel(id);
    if (c) newIds.push(c.id);
  }
  selection = new Set(newIds);
  dirty();
}

// ==========================================================================
// Templates
// ==========================================================================

function _phaseTag(label) {
  const t = makeTag('@phase'); t.values.label = label; return t;
}
function _reinforcerTag(kind) {
  const t = makeTag('@reinforcer'); t.values.kind = kind; return t;
}
function _operandumTag(kind) {
  const t = makeTag('@operandum'); t.values.kind = kind; return t;
}
function _subjectTag(species, strain) {
  const t = makeTag('@subject');
  t.values.species = species;
  t.values.strain = strain;
  return t;
}
function _sessionEndTag(key, value) {
  const t = makeTag('@session_end'); t.values.key = key; t.values.value = value; return t;
}
function _sched(kind, params, units) {
  const n = makeSchedule(kind);
  if (params) Object.assign(n.params, params);
  if (units)  Object.assign(n.units, units);
  return n;
}
function _at(node, x, y) { node.x = x; node.y = y; return node; }
function _withTags(node, tags) { node.tags = tags; return node; }

const TEMPLATES = [
  { name: 'A-B-A-B Reversal',
    description: 'Baseline → treatment → reversal → replication',
    build: () => ({ nodes: [
      _at(_withTags(_sched('EXT'),                 [_phaseTag('A1-baseline')]),    40,  40),
      _at(_withTags(_sched('FR', { n: 5 }),        [_phaseTag('B1-treatment'),
                                                     _reinforcerTag('food')]),     320,  40),
      _at(_withTags(_sched('EXT'),                 [_phaseTag('A2-reversal')]),    600,  40),
      _at(_withTags(_sched('FR', { n: 5 }),        [_phaseTag('B2-replication'),
                                                     _reinforcerTag('food')]),     880,  40),
    ] }),
  },
  { name: 'Multiple Baseline (3 subjects)',
    description: 'Staggered onset of treatment across 3 subjects',
    build: () => ({ nodes: [
      _at(_withTags(_sched('EXT'),                 [_phaseTag('S1-baseline'),
                                                     _subjectTag('rat', 'Long-Evans')]), 40,   40),
      _at(_withTags(_sched('FR', { n: 5 }),        [_phaseTag('S1-treatment'),
                                                     _subjectTag('rat', 'Long-Evans'),
                                                     _reinforcerTag('food')]),     320,  40),
      _at(_withTags(_sched('EXT'),                 [_phaseTag('S2-baseline'),
                                                     _subjectTag('rat', 'Long-Evans')]), 40,   200),
      _at(_withTags(_sched('FR', { n: 5 }),        [_phaseTag('S2-treatment'),
                                                     _subjectTag('rat', 'Long-Evans'),
                                                     _reinforcerTag('food')]),     480,  200),
      _at(_withTags(_sched('EXT'),                 [_phaseTag('S3-baseline'),
                                                     _subjectTag('rat', 'Long-Evans')]), 40,   360),
      _at(_withTags(_sched('FR', { n: 5 }),        [_phaseTag('S3-treatment'),
                                                     _subjectTag('rat', 'Long-Evans'),
                                                     _reinforcerTag('food')]),     640,  360),
    ] }),
  },
  { name: 'Progressive Ratio',
    description: 'Ascending FR steps in series',
    build: () => ({ nodes: [
      _at(_withTags(_sched('FR', { n: 1 }),        [_phaseTag('PR-step1'),
                                                     _reinforcerTag('food')]),     40,   40),
      _at(_withTags(_sched('FR', { n: 2 }),        [_phaseTag('PR-step2'),
                                                     _reinforcerTag('food')]),     320,  40),
      _at(_withTags(_sched('FR', { n: 4 }),        [_phaseTag('PR-step3'),
                                                     _reinforcerTag('food')]),     600,  40),
      _at(_withTags(_sched('FR', { n: 8 }),        [_phaseTag('PR-step4'),
                                                     _reinforcerTag('food')]),     880,  40),
      _at(_withTags(_sched('FR', { n: 16 }),       [_phaseTag('PR-step5'),
                                                     _reinforcerTag('food')]),     1160, 40),
    ] }),
  },
  { name: 'Concurrent VI VI Matching',
    description: 'Two concurrently available VI schedules',
    build: () => {
      const c = makeSchedule('Conc');
      c.children = [
        _sched('VI', { t: 30 }, { t: 's' }),
        _sched('VI', { t: 60 }, { t: 's' }),
      ];
      return { nodes: [
        _at(_withTags(c, [_phaseTag('matching'),
                          _reinforcerTag('food'),
                          _operandumTag('lever')]), 40, 40),
      ]};
    },
  },
  { name: 'DRO Baseline + Treatment',
    description: 'EXT baseline, then DRO',
    build: () => ({ nodes: [
      _at(_withTags(_sched('EXT'),                  [_phaseTag('A1-baseline')]),   40,   40),
      _at(_withTags(_sched('DRO', { t: 10, mode: 'resetting' }, { t: 's' }),
                                                     [_phaseTag('B1-DRO'),
                                                      _reinforcerTag('food')]),    320,  40),
    ] }),
  },
  { name: 'Chained VI → FR',
    description: 'Two-link chain schedule',
    build: () => {
      const ch = makeSchedule('Chain');
      ch.children = [
        _sched('VI', { t: 30 }, { t: 's' }),
        _sched('FR', { n: 10 }),
      ];
      return { nodes: [
        _at(_withTags(ch, [_phaseTag('chain-VI-FR'),
                            _reinforcerTag('food')]), 40, 40),
      ]};
    },
  },
];

function applyTemplate(name, mode) {
  const tpl = TEMPLATES.find(t => t.name === name);
  if (!tpl) return;
  const built = tpl.build();
  if (mode === 'replace') {
    program = built;
  } else {
    // Append mode: shift template Y by current max Y + 200.
    let maxY = 0;
    for (const n of program.nodes) if (n) maxY = Math.max(maxY, (n.y || 0) + 160);
    for (const n of built.nodes) {
      n.y = (n.y || 0) + (maxY === 0 ? 0 : maxY + 40);
      program.nodes.push(n);
    }
  }
  selection = new Set(built.nodes.map(n => n.id));
  dirty();
}

// ==========================================================================
// JSON Export / Import
// ==========================================================================

function exportJson() {
  const data = JSON.stringify({ version: 1, program, view, nextId }, null, 2);
  const blob = new Blob([data], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'schedule-writer.json';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function importJson(file) {
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const data = JSON.parse(e.target.result);
      if (!data || !data.program || !Array.isArray(data.program.nodes)) {
        throw new Error('not a schedule-writer JSON file');
      }
      program = data.program;
      if (data.view) view = data.view;
      if (typeof data.nextId === 'number') nextId = data.nextId;
      // Migrate legacy string tags.
      const walk = (n) => {
        if (!n) return;
        if (Array.isArray(n.tags)) n.tags = n.tags.map(migrateTag);
        if (Array.isArray(n.children)) n.children.forEach(walk);
      };
      program.nodes.forEach(walk);
      selection = new Set();
      dirty();
    } catch (exc) {
      const errEl = document.getElementById('err');
      if (errEl) errEl.textContent = 'import failed: ' + exc.message;
    }
  };
  reader.readAsText(file);
}

// ==========================================================================
// Phase color (derived from @phase label)
// ==========================================================================

function phaseColor(node) {
  if (!node || !Array.isArray(node.tags)) return null;
  const phaseTag = node.tags.find(t => t && t.kind === '@phase');
  if (!phaseTag) return null;
  const label = phaseTag.raw != null ? phaseTag.raw : (phaseTag.values && phaseTag.values.label) || '';
  if (!label) return null;
  // Use the first letter+digit token (e.g. "A1") as the salient slug; fall back
  // to the whole label.
  const m = label.match(/[A-Za-z]+\d*/);
  const slug = (m ? m[0] : label).toLowerCase();
  let h = 0;
  for (let i = 0; i < slug.length; i++) h = (h * 31 + slug.charCodeAt(i)) | 0;
  const hue = ((h % 360) + 360) % 360;
  return 'hsl(' + hue + ', 65%, 50%)';
}

// ==========================================================================
// Annotation linking (detect repeated tag values across blocks)
// ==========================================================================

function annotationLinkMap() {
  const map = {};
  const visit = (n) => {
    if (!n) return;
    (n.tags || []).forEach((t) => {
      const s = compileTag(t);
      if (!s) return;
      map[s] = (map[s] || 0) + 1;
    });
    (n.children || []).forEach(visit);
  };
  program.nodes.forEach(visit);
  return map;
}

function render() {
  const world = document.getElementById('world');
  world.innerHTML = '';
  const { text, errors } = compileProgram();

  // Auto-layout any top-level node that lacks a position (legacy / imported).
  let autoX = 40, autoY = 40;
  for (const n of program.nodes) {
    if (!n) continue;
    if (typeof n.x !== 'number' || typeof n.y !== 'number') {
      n.x = autoX; n.y = autoY;
      autoY += 160;
      if (autoY > 720) { autoY = 40; autoX += 280; }
    }
  }

  const linkMap = annotationLinkMap();
  for (let i = 0; i < program.nodes.length; i++) {
    const node = program.nodes[i];
    if (!node) continue;
    const phase = el('div', { class: 'phase', dataset: { id: node.id } });
    phase.style.left = (node.x || 0) + 'px';
    phase.style.top  = (node.y || 0) + 'px';
    if (typeof node.w === 'number') {
      phase.classList.add('sized');
      phase.style.width = node.w + 'px';
    }
    if (typeof node.h === 'number') {
      phase.classList.add('sized-h');
      phase.style.height = node.h + 'px';
    }
    if (selection.has(node.id)) phase.classList.add('selected');
    const color = phaseColor(node);
    if (color) {
      const stripe = el('div', { class: 'phase-color-stripe' });
      stripe.style.background = color;
      phase.appendChild(stripe);
    }
    phase.appendChild(renderNode(node, program.nodes, i, errors));
    // Link badges on tags whose compiled form occurs more than once.
    phase.querySelectorAll('.tag').forEach((chip) => {
      // Identify by walking node.tags and checking compileTag values.
    });
    if (Array.isArray(node.tags)) {
      const tagEls = phase.querySelectorAll('.tag');
      node.tags.forEach((t, j) => {
        const compiled = compileTag(t);
        if (compiled && (linkMap[compiled] || 0) > 1 && tagEls[j]) {
          tagEls[j].classList.add('linked');
          tagEls[j].title = 'Used by ' + linkMap[compiled] + ' blocks';
        }
      });
    }
    const cornerAxes = node.category === 'comment' ? 'xy' : 'x';
    const cornerTitle = cornerAxes === 'xy'
      ? 'Drag to resize · double-click to reset'
      : 'Drag to resize width · double-click to reset';
    const edgeHandle = el('div', { class: 'resize-handle', title: 'Drag to resize width · double-click to reset' });
    const cornerHandle = el('div', { class: 'resize-handle-br', title: cornerTitle });
    phase.appendChild(edgeHandle);
    phase.appendChild(cornerHandle);
    attachPhaseResize(edgeHandle, phase, node, 'x');
    attachPhaseResize(cornerHandle, phase, node, cornerAxes);
    attachPhaseMove(phase, node);
    attachPhaseSelect(phase, node);
    world.appendChild(phase);
  }

  document.getElementById('emptyHint').style.display =
    program.nodes.filter(n => n).length === 0 ? '' : 'none';

  const output = document.getElementById('output');
  const errEl = document.getElementById('err');
  if (!editingDsl) output.value = text;
  const errList = Object.values(errors);
  errEl.textContent = errList.length === 0 ? '' : errList[0];

  applyView();
}

function setDslEditing(on) {
  editingDsl = on;
  const output = document.getElementById('output');
  const editBtn = document.getElementById('editBtn');
  const applyBtn = document.getElementById('applyBtn');
  const cancelBtn = document.getElementById('cancelBtn');
  if (on) {
    output.removeAttribute('readonly');
    output.focus();
    editBtn.style.display = 'none';
    applyBtn.style.display = '';
    cancelBtn.style.display = '';
  } else {
    output.setAttribute('readonly', '');
    editBtn.style.display = '';
    applyBtn.style.display = 'none';
    cancelBtn.style.display = 'none';
  }
}

function applyDslFromOutput() {
  const output = document.getElementById('output');
  const errEl = document.getElementById('err');
  let parsed;
  try {
    parsed = parseProgram(output.value);
  } catch (exc) {
    errEl.textContent = 'parse error — ' + exc.message;
    return;
  }
  program = parsed;
  setDslEditing(false);
  dirty();
}

function initPalette() {
  const chips = document.querySelectorAll('#palette .chip');
  chips.forEach(chip => {
    chip.addEventListener('dragstart', (e) => {
      const cat = chip.dataset.cat || 'atomic';
      e.dataTransfer.setData('text/plain', encodePayload(cat, chip.dataset.kind));
      e.dataTransfer.effectAllowed = 'copy';
    });
  });
}

function initToolbar() {
  document.getElementById('clearBtn').addEventListener('click', () => {
    if (program.nodes.length === 0 || confirm('Clear the entire canvas?')) {
      program = { nodes: [] };
      dirty();
    }
  });
  document.getElementById('copyBtn').addEventListener('click', () => {
    const output = document.getElementById('output');
    if (!output.value) return;
    output.select();
    try { document.execCommand('copy'); } catch (_) {}
    if (navigator.clipboard) navigator.clipboard.writeText(output.value).catch(() => {});
  });
  document.getElementById('resetViewBtn').addEventListener('click', resetView);
  document.getElementById('zoomInBtn').addEventListener('click', () => zoomBy(1.2));
  document.getElementById('zoomOutBtn').addEventListener('click', () => zoomBy(1 / 1.2));

  document.getElementById('undoBtn').addEventListener('click', undo);
  document.getElementById('redoBtn').addEventListener('click', redo);
  document.getElementById('templatesBtn').addEventListener('click', openTemplatesMenu);
  document.getElementById('alignBtn').addEventListener('click', openAlignMenu);
  document.getElementById('exportJsonBtn').addEventListener('click', exportJson);
  document.getElementById('importJsonBtn').addEventListener('click', () => {
    document.getElementById('importJsonFile').click();
  });
  document.getElementById('importJsonFile').addEventListener('change', (e) => {
    const f = e.target.files && e.target.files[0];
    if (f) importJson(f);
    e.target.value = '';
  });

  document.getElementById('editBtn').addEventListener('click', () => setDslEditing(true));
  document.getElementById('cancelBtn').addEventListener('click', () => {
    setDslEditing(false);
    render();  // restore textarea from current program
  });
  document.getElementById('applyBtn').addEventListener('click', applyDslFromOutput);
  document.getElementById('output').addEventListener('keydown', (e) => {
    if (!editingDsl) return;
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      applyDslFromOutput();
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setDslEditing(false);
      render();
    }
  });
}

// ==========================================================================
// Menus (Templates, Align)
// ==========================================================================

function openMenu(anchorBtn, items) {
  closeMenus();
  const menu = el('div', { class: 'menu' });
  for (const item of items) {
    const row = el('div', { class: 'menu-item' });
    row.appendChild(el('div', null, [item.label]));
    if (item.hint) row.appendChild(el('small', null, [item.hint]));
    row.addEventListener('click', () => { closeMenus(); item.onClick(); });
    menu.appendChild(row);
  }
  const r = anchorBtn.getBoundingClientRect();
  menu.style.left = r.left + 'px';
  menu.style.top  = (r.bottom + 4) + 'px';
  document.body.appendChild(menu);
  setTimeout(() => {
    document.addEventListener('mousedown', closeMenusOnClickOutside, { once: true });
  }, 0);
}
function closeMenus() {
  document.querySelectorAll('.menu').forEach(m => m.remove());
}
function closeMenusOnClickOutside(e) {
  if (e.target.closest('.menu')) {
    document.addEventListener('mousedown', closeMenusOnClickOutside, { once: true });
    return;
  }
  closeMenus();
}

function openTemplatesMenu() {
  const items = TEMPLATES.map(tpl => ({
    label: tpl.name,
    hint: tpl.description,
    onClick: () => {
      const mode = (program.nodes.length > 0 &&
        confirm('Replace current program with template "' + tpl.name + '"?\n\nClick OK to replace, Cancel to append below.'))
        ? 'replace' : 'append';
      applyTemplate(tpl.name, mode);
    },
  }));
  openMenu(document.getElementById('templatesBtn'), items);
}

function openAlignMenu() {
  const sel = selectedTopLevel();
  const enabled = sel.length >= 2;
  const items = [
    { label: 'Align left',     hint: enabled ? null : '(select 2+ blocks first)', onClick: () => alignSelection('left') },
    { label: 'Align right',    onClick: () => alignSelection('right') },
    { label: 'Align top',      onClick: () => alignSelection('top') },
    { label: 'Align bottom',   onClick: () => alignSelection('bottom') },
    { label: 'Align center X', onClick: () => alignSelection('cx') },
    { label: 'Align center Y', onClick: () => alignSelection('cy') },
    { label: 'Distribute horizontally', onClick: () => alignSelection('distH') },
    { label: 'Distribute vertically',   onClick: () => alignSelection('distV') },
  ];
  if (!enabled) items[0].onClick = () => {};
  openMenu(document.getElementById('alignBtn'), items);
}

function alignSelection(mode) {
  const sel = selectedTopLevel();
  if (sel.length < 2) return;
  const phaseEls = {};
  document.querySelectorAll('#world .phase').forEach((p) => { phaseEls[p.dataset.id] = p; });
  const dims = sel.map(n => {
    const r = phaseEls[n.id] ? phaseEls[n.id].getBoundingClientRect() : { width: 220, height: 80 };
    return { node: n, w: r.width / view.scale, h: r.height / view.scale };
  });
  if (mode === 'left') {
    const x = Math.min(...dims.map(d => d.node.x || 0));
    dims.forEach(d => { d.node.x = x; });
  } else if (mode === 'right') {
    const x2 = Math.max(...dims.map(d => (d.node.x || 0) + d.w));
    dims.forEach(d => { d.node.x = x2 - d.w; });
  } else if (mode === 'top') {
    const y = Math.min(...dims.map(d => d.node.y || 0));
    dims.forEach(d => { d.node.y = y; });
  } else if (mode === 'bottom') {
    const y2 = Math.max(...dims.map(d => (d.node.y || 0) + d.h));
    dims.forEach(d => { d.node.y = y2 - d.h; });
  } else if (mode === 'cx') {
    const cx = dims.reduce((a, d) => a + (d.node.x || 0) + d.w / 2, 0) / dims.length;
    dims.forEach(d => { d.node.x = cx - d.w / 2; });
  } else if (mode === 'cy') {
    const cy = dims.reduce((a, d) => a + (d.node.y || 0) + d.h / 2, 0) / dims.length;
    dims.forEach(d => { d.node.y = cy - d.h / 2; });
  } else if (mode === 'distH') {
    dims.sort((a, b) => (a.node.x || 0) - (b.node.x || 0));
    const x1 = dims[0].node.x || 0;
    const x2 = (dims[dims.length - 1].node.x || 0);
    if (dims.length >= 3) {
      const step = (x2 - x1) / (dims.length - 1);
      dims.forEach((d, i) => { d.node.x = x1 + step * i; });
    }
  } else if (mode === 'distV') {
    dims.sort((a, b) => (a.node.y || 0) - (b.node.y || 0));
    const y1 = dims[0].node.y || 0;
    const y2 = (dims[dims.length - 1].node.y || 0);
    if (dims.length >= 3) {
      const step = (y2 - y1) / (dims.length - 1);
      dims.forEach((d, i) => { d.node.y = y1 + step * i; });
    }
  }
  dirty();
}

// ==========================================================================
// Keyboard
// ==========================================================================

function initKeyboard() {
  window.addEventListener('keydown', (e) => {
    // Ignore when typing in an input / textarea / contenteditable.
    const t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) {
      // Still allow undo/redo while editing the DSL textarea (it has its own
      // Ctrl+Enter / Esc shortcuts; default browser undo applies inside).
      return;
    }
    const cmd = e.metaKey || e.ctrlKey;
    if (cmd && e.key.toLowerCase() === 'z' && !e.shiftKey) { e.preventDefault(); undo(); return; }
    if (cmd && (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey))) {
      e.preventDefault(); redo(); return;
    }
    if (cmd && e.key.toLowerCase() === 'd') {
      e.preventDefault(); duplicateSelection(); return;
    }
    if (cmd && e.key.toLowerCase() === 'a') {
      e.preventDefault();
      selection = new Set(program.nodes.filter(n => n).map(n => n.id));
      render();
      return;
    }
    if (e.key === 'Escape') {
      if (selection.size > 0) { clearSelection(); e.preventDefault(); return; }
    }
    if (e.key === 'Backspace' || e.key === 'Delete') {
      if (selection.size > 0) {
        for (const id of [...selection]) removeNode(id);
        selection = new Set();
        e.preventDefault();
        dirty();
        return;
      }
    }
    const arrowMap = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    if (arrowMap[e.key] && selection.size > 0) {
      const [ax, ay] = arrowMap[e.key];
      const step = e.shiftKey ? 32 : 8;
      for (const n of selectedTopLevel()) {
        n.x = (n.x || 0) + ax * step;
        n.y = (n.y || 0) + ay * step;
      }
      e.preventDefault();
      dirty();
      return;
    }
  });
}

load();
lastSnapshot = snapshot();
initPalette();
initViewport();
initMarquee();
initToolbar();
initKeyboard();
render();
</script>

</body>
</html>
"""


def generate_block_editor_html(output_path: str | Path) -> None:
    """Write the self-contained drag-and-drop block editor HTML to ``output_path``.

    The file is overwritten if it already exists. The generated page makes no
    network requests and embeds all CSS and JavaScript inline.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_HTML_TEMPLATE, encoding="utf-8")
