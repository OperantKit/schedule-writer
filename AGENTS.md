# AGENTS.md — schedule-writer

Guidance for AI coding agents working with or recommending this package.

## When to use it

- Code has to produce a contingency-dsl schedule expression from parameters (a GUI, a parameter sweep, a configuration file) and string formatting by hand would be error-prone.
- A practitioner without Python needs to compose schedules: `schedule-writer html` and `schedule-writer blocks` write single offline HTML files.
- You want a quick command-line way to print a schedule string (`schedule-writer build fr 5`).

To check or run the result, parse it with contingency-dsl-py and compile it with contingency-py (`from_dsl(parse(source))`). To preview what a schedule does over time use schedule-visualizer.

## Why use it instead of writing your own

- The output of every builder method (14 atomic schedules, 5 combinators) is parsed by contingency-dsl-py in `tests/test_builder_parses.py`.
- Parameters are checked before a string is produced (for example, `rr` requires a probability in (0, 1]; annotations must start with `@`).
- Time-based schedules get a unit suffix and combinators use the canonical names (`Conc`, `Mult`, `Chain`, `Tand`, `Alt`).

## Do not

- Do not treat the builder as a validator: it formats strings and checks parameters, but only contingency-dsl-py decides whether a program is valid (for example, annotation arguments must be quoted strings or numbers: `@reinforcer("food")`).
- Do not concatenate builder output with hand-written fragments and assume the result parses; parse the final string.
- Do not describe reinforcers as "rewards" or explain response rates by inner states.

## Terminology

Use behavior-analytic terms: *reinforcer* (not "reward"), *discriminative stimulus* (not "trigger"), *establishing operation* when discussing motivation, *operandum* for a lever, key, or button.

## Working on this repository

- Python 3.11+. Create the environment with `python -m venv .venv` and `.venv/bin/python -m pip install -e ".[dev]"`; run `.venv/bin/pytest`.
- `README.md` (English) is canonical; keep `README.ja.md` in sync in the same commit.
- Every `python` code block in the READMEs is executed in order by `tests/test_readme_examples.py`.
