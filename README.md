# schedule-writer

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

## Install (development)

```bash
mise exec -- python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## Usage

### Builder API

```python
from schedule_writer.builder import ScheduleBuilder

b = ScheduleBuilder()
b.fr(5)                       # "FR 5"
b.vi(30)                      # "VI 30s"
b.concurrent(b.vi(30), b.vi(60))   # "Conc(VI 30s, VI 60s)"
b.chained(b.fr(5), b.fi(30))       # "Chain(FR 5, FI 30s)"
b.with_annotation(b.fr(5), "@reinforcer(food)")
#   "FR 5 @reinforcer(food)"
```

### CLI

```bash
schedule-writer --help
schedule-writer build fr 5
schedule-writer build vi 30
schedule-writer build conc "VI 30s" "VI 60s"
schedule-writer interactive
```

### Standalone HTML

```bash
schedule-writer html --output schedule-writer.html
# Open schedule-writer.html in any browser; works offline.
```

## Output grammar

The generated strings follow the `contingency-dsl` operant grammar (see
`apps/core/contingency-dsl/spec/en/operant/grammar.md`). Time-domain schedules
attach a unit suffix by default (`s`, `ms`, `min`); ratio-domain schedules emit
plain numbers (`FR 5`, `VR 20`). Compound schedules use the canonical
combinator names: `Conc`, `Mult`, `Chain`, `Tand`, `Alt`.

## Status

Alpha. The builder API mirrors the surface syntax of the DSL but does not
itself parse or validate the result against the formal grammar; consumers
should treat the output as input text to a downstream parser.
