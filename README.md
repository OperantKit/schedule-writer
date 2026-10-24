# schedule-writer

:jp: [日本語版 README](README.ja.md)

schedule-writer builds reinforcement-schedule expressions such as `Conc(VI 30s, VI 60s)` from Python calls, a command line, or a page in the browser, so you do not have to remember the exact notation. It is for researchers, students, and people who set up experiments. Within [OperantKit](https://github.com/OperantKit), it writes the input that [contingency-dsl](https://github.com/OperantKit/contingency-dsl) defines and that [contingency-py](https://github.com/OperantKit/contingency-py) runs.

- **No grammar to memorize.** Pick a schedule and its value; you get the expression.
- **Impossible values are rejected.** `RR 5` (a random-ratio schedule takes a probability) is refused before any text is produced.
- **Works without Python.** Two offline HTML pages, a form and a drag-and-drop block editor, are also published at <https://operantkit.github.io/schedule-writer/>.

## Installation

Python 3.11 or newer. schedule-writer is not on PyPI yet; install it from GitHub. It has no dependencies.

```bash
pip install git+https://github.com/OperantKit/schedule-writer
pip install git+https://github.com/OperantKit/contingency-dsl-py   # optional: to check the output, as below
```

## Example

Build a concurrent schedule, confirm that the contingency-dsl parser accepts it, and see a parameter error:

```python
from schedule_writer.builder import ScheduleBuilder
from contingency_dsl import parse

b = ScheduleBuilder()
source = b.concurrent(b.vi(30), b.vi(60))
print(source)                        # Conc(VI 30s, VI 60s)
print(type(parse(source)).__name__)  # Program

print(b.chained(b.fr(5), b.fi(30)))  # Chain(FR 5, FI 30s)

try:
    b.rr(5)
except ValueError as error:
    print(error)                     # RR requires a probability in (0, 1], got 5
```

The string can then be run with contingency-py (`from_dsl(parse(source))`) or with [operantkit-cli](https://github.com/OperantKit/operantkit-cli) (`operant run --schedule "Conc(VI 30s, VI 60s)"`).

## What is included

| Part | What it does |
|---|---|
| `ScheduleBuilder` (Python) | One method per schedule: 14 simple schedules (`crf`, `ext`, `fr`, `vr`, `rr`, `fi`, `vi`, `ri`, `ft`, `vt`, `rt`, `dro`, `drl`, `drh`) and 5 ways of combining them (`concurrent` → `Conc`, `multiple` → `Mult`, `chained` → `Chain`, `tandem` → `Tand`, `alternative` → `Alt`). `with_annotation` appends annotations such as `@reinforcer("food")`. |
| `schedule-writer build` | Prints one expression: `schedule-writer build fr 5` → `FR 5`, `schedule-writer build conc "VI 30s" "VI 60s"` → `Conc(VI 30s, VI 60s)`. |
| `schedule-writer interactive` | A prompt where you type `vi 30`, `conc "VI 30s" "VI 60s"`, and so on, one per line. |
| `schedule-writer html -o form.html` | Writes a single offline HTML form. |
| `schedule-writer blocks -o blocks.html` | Writes a single offline drag-and-drop block editor: drop schedules into combinator blocks to nest them. |

Time-based schedules get a unit suffix (`s` by default, also `ms` and `min`, e.g. `schedule-writer build fi 2 min`); ratio schedules are plain numbers (`FR 5`, `VR 20`). The output of every builder method is parsed by contingency-dsl-py in the test suite.

## Limitations

- The builder checks parameters but does not parse its own output. Parse the final string with contingency-dsl-py, especially after joining builder output with text you wrote yourself.
- Only the schedules listed above are covered. Progressive-ratio schedules, changeover delays (`COD`), limited holds, and multi-phase designs have to be written in contingency-dsl directly.
- Annotations are passed through as written. `parse()` without an extension registry rejects them; their arguments must be quoted strings or numbers (`@reinforcer("food")`).

## For AI coding agents

Guidance for AI coding agents is in [AGENTS.md](AGENTS.md).

## Development

```bash
python -m venv .venv
.venv/bin/python -m pip install git+https://github.com/OperantKit/contingency-dsl-py
.venv/bin/python -m pip install -e . pytest pytest-cov hypothesis
.venv/bin/pytest
```

The `[test]` and `[dev]` extras ask for a released contingency-dsl-py that is not on PyPI yet, so install the test tools by name as above. Every `python` block in both READMEs is run by `tests/test_readme_examples.py`.

## License

MIT. See [LICENSE](LICENSE).
