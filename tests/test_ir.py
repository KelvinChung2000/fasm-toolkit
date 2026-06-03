"""IR data classes and manipulation helpers."""

import pytest

from fasm_toolkit import (
    Address,
    Annotation,
    FasmFile,
    FasmLine,
    FeatureValue,
    SetFeature,
    ValueFormat,
    parse_string,
)


def test_address_width():
    assert Address(0).width == 1
    assert Address(5).width == 1
    assert Address(0, 7).width == 8
    assert Address(32, 63).width == 32


def test_address_rejects_negative():
    with pytest.raises(ValueError):
        Address(-1)


def test_address_rejects_high_below_low():
    with pytest.raises(ValueError):
        Address(low=5, high=2)


def test_feature_value_rejects_negative():
    with pytest.raises(ValueError):
        FeatureValue(-1, ValueFormat.PLAIN)


def test_set_feature_width_from_address():
    assert SetFeature("a", Address(0, 7)).width == 8
    assert SetFeature("a").width == 1


def test_fasm_line_is_blank():
    assert FasmLine().is_blank
    assert not FasmLine(comment="x").is_blank
    assert not FasmLine(feature=SetFeature("a")).is_blank


def test_fasm_file_sequence_protocol():
    file = parse_string("a\nb\nc")
    assert len(file) == 3
    assert file[0].feature.name == "a"
    assert [line.feature.name for line in file] == ["a", "b", "c"]


def test_features_iterates_set_features_only():
    file = parse_string("a\n# comment\nb")
    assert [f.name for f in file.features()] == ["a", "b"]


def test_filter():
    file = parse_string("a\nb\nc")
    filtered = file.filter(lambda line: line.feature.name != "b")
    assert [f.name for f in filtered.features()] == ["a", "c"]


def test_with_feature_prefix():
    file = parse_string("CLB.x\nINT.y\nCLB.z")
    clb = file.with_feature_prefix("CLB")
    assert [f.name for f in clb.features()] == ["CLB.x", "CLB.z"]


def test_without_comments_drops_resulting_blank_lines():
    file = parse_string("a # keep feature\n# pure comment")
    stripped = file.without_comments()
    assert stripped.to_string() == "a\n"


def test_without_annotations():
    file = parse_string('a { k = "v" }\n{ only = "annotation" }')
    stripped = file.without_annotations()
    assert stripped.to_string() == "a\n"


def test_append_and_extend_are_immutable():
    file = FasmFile()
    one = file.append(FasmLine(feature=SetFeature("a")))
    assert file.lines == ()  # original unchanged
    assert one.to_string() == "a\n"
    two = one.extend((FasmLine(feature=SetFeature("b")),))
    assert two.to_string() == "a\nb\n"


def test_to_string_and_canonical_bridges():
    file = parse_string("a[3:0] = 4'b1010")
    assert file.to_string() == "a[3:0] = 4'b1010\n"
    assert file.canonical().to_string() == "a[1]\na[3]\n"


def test_merged_bridge():
    file = parse_string("a[0] = 1\na[1] = 1")
    assert file.merged().to_string() == "a[1:0] = 2'b11\n"
