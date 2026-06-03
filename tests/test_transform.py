"""Transformations: canonicalize, merge_features, merge_and_sort."""

import pytest

from fasm_toolkit import (
    Address,
    FasmError,
    FasmMergeError,
    FeatureValue,
    SetFeature,
    ValueFormat,
    canonical_set_features,
    canonicalize,
    merge_and_sort,
    merge_features,
    parse_string,
)


def test_canonical_set_features_expands_bits() -> None:
    feature = SetFeature(
        "A", Address(0, 3), FeatureValue(0b1010, ValueFormat.VERILOG_BINARY)
    )
    result = list(canonical_set_features(feature))
    assert result == [SetFeature("A", Address(1)), SetFeature("A", Address(3))]


def test_canonical_set_features_bit_zero_becomes_bare() -> None:
    feature = SetFeature(
        "A", Address(0, 3), FeatureValue(0b0001, ValueFormat.VERILOG_BINARY)
    )
    assert list(canonical_set_features(feature)) == [SetFeature("A")]


def test_canonical_set_features_zero_value_yields_nothing() -> None:
    feature = SetFeature(
        "A", Address(0, 3), FeatureValue(0, ValueFormat.VERILOG_BINARY)
    )
    assert list(canonical_set_features(feature)) == []


def test_canonicalize_file_dedupes_and_sorts() -> None:
    file = parse_string("B[1] = 1\nA\nA")
    canonical = canonicalize(file)
    assert canonical.to_string() == "A\nB[1]\n"


def test_merge_features_adjacent_bits() -> None:
    merged = merge_features([SetFeature("A", Address(0)), SetFeature("A", Address(1))])
    assert merged == SetFeature(
        "A", Address(0, 1), FeatureValue(0b11, ValueFormat.VERILOG_BINARY)
    )


def test_merge_features_sparse_bits() -> None:
    merged = merge_features([SetFeature("A", Address(5)), SetFeature("A", Address(7))])
    assert merged == SetFeature(
        "A", Address(0, 7), FeatureValue(0b10100000, ValueFormat.VERILOG_BINARY)
    )


def test_merge_features_rejects_mixed_names() -> None:
    with pytest.raises(FasmMergeError, match="one feature name"):
        merge_features([SetFeature("A", Address(0)), SetFeature("B", Address(1))])


def test_merge_features_rejects_contradictory_bits() -> None:
    # The same bit set on one line and cleared on another cannot merge.
    with pytest.raises(FasmMergeError) as exc_info:
        parse_string("A[0] = 1\nA[0] = 0").merged()
    assert isinstance(exc_info.value, FasmError)


def test_merge_and_sort_merges_and_orders_groups() -> None:
    file = parse_string("B.x[1] = 1\nA.y\nB.x[0] = 1")
    result = merge_and_sort(file)
    assert result.to_string() == "A.y\n\nB.x[1:0] = 2'b11\n"


def test_merge_and_sort_discards_blank_lines() -> None:
    file = parse_string("A.y\n\n\nA.z")
    result = merge_and_sort(file)
    # Both share group "A"; no blank lines remain inside the group.
    assert "\n\n" not in result.to_string().strip("\n")


def test_merge_and_sort_zero_function_drops_zero_tiles() -> None:
    file = parse_string("TILE_A.x = 0\nTILE_B.y")
    result = merge_and_sort(file, zero_function=lambda name: name.startswith("TILE_A"))
    text = result.to_string()
    assert "TILE_A" not in text
    assert "TILE_B.y" in text
