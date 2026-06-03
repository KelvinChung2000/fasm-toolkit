"""Emission of IR back to FASM text."""

import pytest

from fasm_toolkit import (
    Address,
    FasmFile,
    FasmLine,
    FeatureValue,
    SetFeature,
    ValueFormat,
    parse_string,
    to_string,
)


def test_implicit_one_emits_without_equals() -> None:
    assert parse_string("feat").to_string() == "feat\n"


def test_explicit_one_emits_with_equals() -> None:
    assert parse_string("feat = 1").to_string() == "feat = 1\n"


def test_single_bit_address_emits_index_form() -> None:
    assert parse_string("a.INIT[17]").to_string() == "a.INIT[17]\n"


def test_range_emits_high_low() -> None:
    assert parse_string("a[63:32] = 32'hFF").to_string() == "a[63:32] = 32'hFF\n"


def test_width_is_derived_from_address_not_literal() -> None:
    # 5'h1F written at a 32-bit address re-emits with the address width.
    assert parse_string("a[63:32] = 5'h1F").to_string() == "a[63:32] = 32'h1F\n"


@pytest.mark.parametrize(
    ("fmt", "expected"),
    [
        (ValueFormat.VERILOG_HEX, "a[7:0] = 8'hFF\n"),
        (ValueFormat.VERILOG_BINARY, "a[7:0] = 8'b11111111\n"),
        (ValueFormat.VERILOG_OCTAL, "a[7:0] = 8'o377\n"),
        (ValueFormat.VERILOG_DECIMAL, "a[7:0] = 8'd255\n"),
    ],
)
def test_value_format_emission(fmt: ValueFormat, expected: str) -> None:
    file = FasmFile((FasmLine(SetFeature("a", Address(0, 7), FeatureValue(255, fmt))),))
    assert file.to_string() == expected


def test_annotations_emission() -> None:
    file = parse_string('feat { a = "b", c = "d" }')
    assert file.to_string() == 'feat { a = "b", c = "d" }\n'


def test_comment_only_emission() -> None:
    assert parse_string("# hi").to_string() == "# hi\n"


def test_blank_file_emits_single_newline() -> None:
    assert FasmFile().to_string() == "\n"
    assert to_string(FasmFile()) == "\n"


def test_canonical_expands_and_sorts() -> None:
    text = "Z[1] = 1\nA[0] = 1\nA[3:0] = 4'b0100"
    assert parse_string(text).to_string(canonical=True) == "A\nA[2]\nZ[1]\n"


def test_canonical_drops_zero_values() -> None:
    assert parse_string("a[7:0] = 8'b0").to_string(canonical=True) == "\n"
