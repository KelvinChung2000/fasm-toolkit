"""Parsing FASM text into the IR."""

import pytest

from conftest import example
from fasm_toolkit import (
    Address,
    Annotation,
    FasmLine,
    FeatureValue,
    SetFeature,
    ValueFormat,
    parse_file,
    parse_string,
)


def test_blank_file_is_empty():
    assert parse_file(example("blank.fasm")).lines == ()


def test_blank_string_is_empty():
    assert parse_string("").lines == ()
    assert parse_string("\n\n\n").lines == ()


def test_comment_only_line_keeps_text_after_hash():
    file = parse_file(example("comment.fasm"))
    assert file.lines == (FasmLine(comment=" Only a comment."),)


def test_empty_comment():
    assert parse_string("#").lines == (FasmLine(comment=""),)


def test_comment_preserves_trailing_whitespace():
    assert parse_string("#   ").lines == (FasmLine(comment="   "),)


def test_implicit_one_feature():
    file = parse_file(example("feature_only.fasm"))
    assert file.lines == (
        FasmLine(feature=SetFeature(name="EXAMPLE_FEATURE.X0.Y0.BLAH")),
    )
    # No value object: implicit one carries no FeatureValue.
    assert file.lines[0].feature.value is None


def test_explicit_one_differs_from_implicit_one():
    implicit = parse_string("feat").lines[0].feature
    explicit = parse_string("feat = 1").lines[0].feature
    assert implicit.value is None
    assert explicit.value == FeatureValue(1, ValueFormat.PLAIN)


def test_single_bit_address():
    feature = parse_string("a.b.INIT[17]").lines[0].feature
    assert feature.address == Address(low=17, high=None)
    assert feature.address.width == 1


def test_range_address_high_low_order():
    feature = parse_string("a[63:32] = 32'h1").lines[0].feature
    assert feature.address == Address(low=32, high=63)
    assert feature.address.width == 32


@pytest.mark.parametrize(
    "text, expected_value, expected_format",
    [
        ("a[7:0] = 8'hFF", 255, ValueFormat.VERILOG_HEX),
        ("a[7:0] = 8'b1010", 10, ValueFormat.VERILOG_BINARY),
        ("a[7:0] = 8'd42", 42, ValueFormat.VERILOG_DECIMAL),
        ("a[7:0] = 8'o52", 42, ValueFormat.VERILOG_OCTAL),
        ("a[7:0] = 42", 42, ValueFormat.PLAIN),
    ],
)
def test_value_formats(text, expected_value, expected_format):
    value = parse_string(text).lines[0].feature.value
    assert value == FeatureValue(expected_value, expected_format)


def test_unsized_value():
    value = parse_string("a[7:0] = 'hFF").lines[0].feature.value
    assert value == FeatureValue(255, ValueFormat.VERILOG_HEX)


def test_underscores_in_values_are_ignored():
    value = parse_string("a[31:0] = 32'b1111_0000_1111_0000").lines[0].feature.value
    assert value.value == 0xF0F0


def test_annotations():
    line = parse_string('feat { module = "top", file = "/a/b.txt" }').lines[0]
    assert line.feature.name == "feat"
    assert line.annotations == (
        Annotation("module", "top"),
        Annotation("file", "/a/b.txt"),
    )


def test_empty_annotation_value():
    line = parse_string('feat { .attr = "" }').lines[0]
    assert line.annotations == (Annotation(".attr", ""),)


def test_annotation_only_line():
    line = parse_string('{ .top_module = "/a/b/c/d.txt" }').lines[0]
    assert line.feature is None
    assert line.annotations == (Annotation(".top_module", "/a/b/c/d.txt"),)


def test_feature_annotation_and_comment_on_one_line():
    line = parse_string('feat { a = "b" } # trailing').lines[0]
    assert line.feature.name == "feat"
    assert line.annotations == (Annotation("a", "b"),)
    assert line.comment == " trailing"


def test_zero_value_is_kept():
    feature = parse_string("a[0:0] = 1'b0").lines[0].feature
    assert feature.value == FeatureValue(0, ValueFormat.VERILOG_BINARY)


def test_many_example_parses_without_error():
    file = parse_file(example("many.fasm"))
    assert len(file.lines) > 0
