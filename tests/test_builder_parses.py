"""Every builder method must produce a string that contingency-dsl-py accepts."""

from __future__ import annotations

import pytest
from contingency_dsl import parse

from schedule_writer.builder import ScheduleBuilder

B = ScheduleBuilder()

ATOMIC = [
    B.crf(),
    B.ext(),
    B.fr(5),
    B.vr(20),
    B.rr(0.2),
    B.fi(30),
    B.vi(30),
    B.ri(30),
    B.ft(30),
    B.vt(30),
    B.rt(30),
    B.dro(10),
    B.drl(5),
    B.drh(5),
]

COMPOUND = [
    B.concurrent(B.vi(30), B.vi(60)),
    B.multiple(B.fr(5), B.ext()),
    B.chained(B.fr(5), B.fi(30)),
    B.tandem(B.vr(10), B.drl(2)),
    B.alternative(B.fr(10), B.ft(60)),
]


@pytest.mark.parametrize("source", ATOMIC + COMPOUND)
def test_output_parses(source: str) -> None:
    parse(source)


# ---------------------------------------------------------------------------
# Annotation examples shipped in the package must use the accepted form
# ---------------------------------------------------------------------------

import doctest  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

import contingency_dsl.annotations as _annotations  # noqa: E402
from contingency_dsl.extensions import ExtensionRegistry  # noqa: E402

from schedule_writer import builder as _builder_module  # noqa: E402
from schedule_writer.standalone_html import generate_standalone_html  # noqa: E402

REGISTRY = ExtensionRegistry.build(
    *(
        getattr(_annotations, name)()
        for name in dir(_annotations)
        if name.endswith("Extension") and name[0].isupper()
    )
)


def _docstring_annotation_examples() -> list[str]:
    finder = doctest.DocTestFinder()
    sources: list[str] = []
    for test in finder.find(_builder_module):
        for example in test.examples:
            if "with_annotation" in example.source:
                sources.append(eval(example.want.strip()))  # noqa: S307
    return sources


def test_docstring_annotation_examples_parse() -> None:
    examples = _docstring_annotation_examples()
    assert examples, "no with_annotation example in the builder docstring"
    for source in examples:
        parse(source, extensions=REGISTRY)


def test_docstring_annotation_hint_is_quoted() -> None:
    doc = ScheduleBuilder.with_annotation.__doc__ or ""
    for ann in re.findall(r"@reinforcer\([^)]*\)", doc):
        parse(f"FR 5 {ann}", extensions=REGISTRY)


def test_standalone_default_annotation_parses(tmp_path: Path) -> None:
    out = tmp_path / "writer.html"
    generate_standalone_html(out)
    text = out.read_text(encoding="utf-8")
    m = re.search(r'id="annText"[^>]*value="([^"]*)"', text)
    if m is None:
        m = re.search(r"id=\"annText\"[^>]*value='([^']*)'", text)
    assert m, "annText input not found"
    default = m.group(1).replace("&quot;", '"')
    parse(f"FR 5 {default}", extensions=REGISTRY)
    for ann in re.findall(r"<code>(@reinforcer\([^<]*\))</code>", text):
        parse(f"FR 5 {ann.replace('&quot;', chr(34))}", extensions=REGISTRY)
