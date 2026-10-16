# schedule-writer

:jp: [日本語版 README](README.ja.md)

Builder API, CLI, and standalone HTML tool for composing reinforcement-schedule
DSL programs (the surface syntax of `contingency-dsl`) without writing DSL text by
hand.

The intended audience is practitioners and researchers who want to assemble
schedules like `Conc(VI 30s, VI 60s)` from dropdowns and parameter inputs rather
than memorising the grammar.

## Components

- **`schedule_writer.builder`** — Pure-Python fluent API. Functions return DSL
  strings; nothing is parsed, evaluated, or executed. Consumers can pipe the
  output to `contingency-dsl-py` for validation if desired.
- **`schedule_writer.cli`** — Command-line entry point with two subcommands:
  - `schedule-writer build <schedule> <args...>` — single-shot construction
    (e.g. `schedule-writer build fr 5` prints `FR 5`).
  - `schedule-writer interactive` — guided REPL that prompts for the schedule
    family and parameters, then prints the resulting DSL string.
- **`schedule_writer.standalone_html`** — Generates a single self-contained
  HTML file (no CDN, no external scripts) with vanilla-JS dropdowns and inputs
  that compute DSL strings client-side. Useful for distributing the tool to
  users who do not have a Python environment.
- **`schedule_writer.block_editor_html`** — Generates a visual block-based
  drag-and-drop editor as a single self-contained HTML file. A palette
  of atomic-schedule, combinator, and annotation blocks is dragged onto a
  canvas; compound blocks expose nested slots that themselves accept dropped
  blocks. The resulting DSL string is compiled live from the block tree.
  Targets practitioners who are not engineers.

## Install (development)

```bash
mise exec -- python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## 30-second example

```bash
pip install git+https://github.com/OperantKit/schedule-writer
pip install contingency-dsl-py   # only needed to check the output, as below
```

Build a schedule without writing DSL syntax, and confirm that the parser accepts it:

```python
from schedule_writer.builder import ScheduleBuilder
from contingency_dsl import parse

b = ScheduleBuilder()
source = b.concurrent(b.vi(30), b.vi(60))
print(source)  # Conc(VI 30s, VI 60s)
print(type(parse(source)).__name__)  # Program — the string is valid contingency-dsl

try:
    b.rr(5)  # a random-ratio schedule takes a probability, not a count
except ValueError as error:
    print(error)  # RR requires a probability in (0, 1], got 5
```

The string can be passed to [contingency-py](https://github.com/OperantKit/contingency-py) (`from_dsl(parse(source))`) to run the schedule, or to [operantkit-cli](https://github.com/OperantKit/operantkit-cli) (`operant run --schedule "Conc(VI 30s, VI 60s)"`).

## Why not write the DSL strings by hand?

- **Every builder method produces parseable DSL.** All 14 atomic schedules (CRF, EXT, FR, VR, RR, FI, VI, RI, FT, VT, RT, DRO, DRL, DRH) and 5 combinators (`Conc`, `Mult`, `Chain`, `Tand`, `Alt`) are checked against contingency-dsl-py in `tests/test_builder_parses.py`.
- **Parameters are checked before a string is produced.** For example, `rr` requires a probability in (0, 1] and annotations must start with `@`.
- **Units and spelling follow the grammar.** Time-based schedules get a unit suffix (`s`, `ms`, `min`) and combinators use the canonical names.
- **No Python needed for end users.** `schedule-writer html` and `schedule-writer blocks` write single offline HTML files (a form and a drag-and-drop block editor) that compose the same strings in the browser.

## Usage

### Builder API

```python
from schedule_writer.builder import ScheduleBuilder

b = ScheduleBuilder()
b.fr(5)                       # "FR 5"
b.vi(30)                      # "VI 30s"
b.concurrent(b.vi(30), b.vi(60))   # "Conc(VI 30s, VI 60s)"
b.chained(b.fr(5), b.fi(30))       # "Chain(FR 5, FI 30s)"
b.with_annotation(b.fr(5), '@reinforcer("food")')
#   'FR 5 @reinforcer("food")'
```

### CLI

```bash
schedule-writer --help
schedule-writer build fr 5
schedule-writer build vi 30
schedule-writer build conc "VI 30s" "VI 60s"
schedule-writer interactive
```

### Standalone HTML (form-based)

```bash
schedule-writer html --output schedule-writer.html
# Open schedule-writer.html in any browser; works offline.
```

### Block editor HTML (visual block-based, drag-and-drop)

```bash
schedule-writer blocks --output schedule-writer-blocks.html
# Open in any browser. Drag blocks from the left palette onto the canvas;
# drop compound blocks into each other to nest. Works offline.
```

## Output grammar

The generated strings follow the `contingency-dsl` operant grammar.
Time-domain schedules attach a unit suffix by default (`s`, `ms`, `min`);
ratio-domain schedules emit plain numbers (`FR 5`, `VR 20`). Compound
schedules use the canonical combinator names: `Conc`, `Mult`, `Chain`,
`Tand`, `Alt`.

## Status

Alpha. The builder API mirrors the surface syntax of the DSL but does not
itself parse or validate the result against the formal grammar; consumers
should treat the output as input text to a downstream parser.
