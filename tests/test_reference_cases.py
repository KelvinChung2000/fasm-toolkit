"""Faithful port of the reference library's own test suite.

These cases are translated, one for one, from ``tests/test_simple.py`` in the
upstream ``chipsalliance/fasm`` (and ``FPGA-Research/fasm``) repository, adapted
to the fasm-toolkit IR. They run against the same ``examples/*.fasm`` corpus the
reference library ships.

Translation of the original IR to ours:

* ``SetFasmFeature(start=None, end=None, value=1, value_format=None)`` (an
  implicit one) becomes ``SetFeature(name, address=None, value=None)``.
* ``FasmLine(annotations=None)`` becomes an empty annotation tuple ``()``.

The original ``check_round_trip`` asserted ``parse(emit(x)) == x``; the same
invariant is checked here on the IR.
"""

from conftest import example

from fasm_toolkit import (
    FasmFile,
    FasmLine,
    SetFeature,
    parse_file,
    parse_string,
)


def check_round_trip(file: FasmFile) -> None:
    """Reference invariant: parsing the emitted text yields equal IR."""
    text = file.to_string()
    assert parse_string(text).lines == file.lines


def test_blank_file() -> None:
    # Reference test_blank_file expects a blank file to parse to no lines.
    result = parse_file(example("blank.fasm"))
    assert result.lines == ()
    check_round_trip(result)


def test_comment_file() -> None:
    # Reference: [FasmLine(set_feature=None, annotations=None,
    #                      comment=' Only a comment.')]
    result = parse_file(example("comment.fasm"))
    assert result.lines == (FasmLine(comment=" Only a comment."),)
    check_round_trip(result)


def test_one_line_feature() -> None:
    # Reference: [FasmLine(SetFasmFeature('EXAMPLE_FEATURE.X0.Y0.BLAH',
    #             start=None, end=None, value=1, value_format=None))]
    result = parse_file(example("feature_only.fasm"))
    assert result.lines == (
        FasmLine(feature=SetFeature(name="EXAMPLE_FEATURE.X0.Y0.BLAH")),
    )
    assert result.to_string() == "EXAMPLE_FEATURE.X0.Y0.BLAH\n"
    check_round_trip(result)


def test_examples_file() -> None:
    # Reference: round-trips the comprehensive many.fasm example.
    result = parse_file(example("many.fasm"))
    check_round_trip(result)
