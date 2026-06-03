"""Ergonomics and round-trip integrity of the eDSL, from the code review.

Each test pins a concrete defect the review surfaced: silent round-trip
corruption, raw exceptions escaping the FasmError hierarchy, foreign/stale
selections, and inconsistent builder surface.
"""

import pytest

from fasm_toolkit import (
    Address,
    FasmBuilder,
    FasmLine,
    FeatureValue,
    ValueFormat,
    bits,
    edit,
    parse_string,
)
from fasm_toolkit.errors import FasmBuildError, FasmError, FasmMergeError

# -- round-trip integrity (unescaped / unvalidated text) ----------------------


def test_add_annotation_with_quote_round_trips() -> None:
    out = (
        edit(parse_string("X.Y\n"))
        .select(name="X.Y")
        .add_annotation("net", 'a"b')
        .commit()
    )
    assert out[0].annotations[0].value == 'a"b'  # logical value preserved
    assert parse_string(out.to_string()) == out  # and it re-parses to equal IR


def test_add_annotation_with_backslash_round_trips() -> None:
    out = (
        edit(parse_string("X.Y\n"))
        .select(name="X.Y")
        .add_annotation("path", "C:\\tmp")
        .commit()
    )
    assert out[0].annotations[0].value == "C:\\tmp"
    assert parse_string(out.to_string()) == out


def test_parser_unescapes_annotation_value() -> None:
    line = parse_string('feat { a = "x\\"y" }').lines[0]
    assert line.annotations[0].value == 'x"y'


def test_emit_escapes_annotation_value() -> None:
    out = edit(parse_string("X\n")).select(name="X").add_annotation("a", 'q"').commit()
    assert out.to_string() == 'X { a = "q\\"" }\n'


def test_comment_with_newline_raises() -> None:
    with pytest.raises(FasmBuildError, match="newline"):
        FasmBuilder().comment(" first\nINJECTED.FEATURE")


def test_add_annotation_invalid_name_raises() -> None:
    with pytest.raises(FasmBuildError, match="invalid annotation name"):
        edit(parse_string("X.Y\n")).select(name="X.Y").add_annotation("bad name", "v")


def test_add_annotation_value_with_newline_raises() -> None:
    with pytest.raises(FasmBuildError, match="newline"):
        edit(parse_string("X.Y\n")).select(name="X.Y").add_annotation("net", "a\nb")


# -- exceptions stay inside the FasmError hierarchy ---------------------------


def test_negative_value_raises_build_error() -> None:
    with pytest.raises(FasmBuildError):
        FasmBuilder().set("F", -1, width=4)


def test_negative_at_raises_build_error() -> None:
    with pytest.raises(FasmBuildError):
        FasmBuilder().enable("F", at=-1)


def test_set_value_negative_raises_build_error() -> None:
    with pytest.raises(FasmBuildError):
        edit(parse_string("F[3:0] = 4'h1\n")).select(name="F").set_value(-1)


def test_bits_reversed_raises_build_error() -> None:
    with pytest.raises(FasmBuildError):
        bits(0, 15)


def test_bool_at_rejected() -> None:
    with pytest.raises(FasmBuildError, match="int or Address"):
        FasmBuilder().enable("F", at=True)


def test_merge_features_mixed_names_raises_merge_error() -> None:
    from fasm_toolkit import SetFeature
    from fasm_toolkit.transform import merge_features

    with pytest.raises(FasmMergeError):
        merge_features([SetFeature("A"), SetFeature("B")])


def test_authoring_errors_are_all_fasm_errors() -> None:
    """A consumer catching FasmError catches every authoring mistake."""
    for call in (
        lambda: FasmBuilder().enable("F", at=-1),
        lambda: FasmBuilder().set("F", -1, width=4),
        lambda: bits(0, 15),
        lambda: FasmBuilder().enable("F", at=True),
    ):
        with pytest.raises(FasmError):
            call()


# -- set() spec / message (unaddressed feature is one bit) --------------------


def test_bare_value_over_one_bit_has_clear_message() -> None:
    with pytest.raises(FasmBuildError, match="one bit"):
        FasmBuilder().set("F", 42)


# -- insertion: ergonomic, safe against foreign/stale selections --------------


def _source() -> str:
    return (
        "# header\n"
        "TILE_X0Y0.LUT.INIT[15:0] = 16'hABCD\n"
        "TILE_X0Y0.MUX.SEL0\n"
        "TILE_X1Y0.LUT.INIT[15:0] = 16'h1234\n"
    )


def test_selection_insert_after_is_chainable() -> None:
    extra = FasmBuilder().enable("TILE_X0Y0.EXTRA").build()
    out = (
        edit(parse_string(_source()))
        .select(name="TILE_X0Y0.MUX.SEL0")
        .insert_after(extra)
        .commit()
    )
    names = [line.feature.name for line in out.feature_lines()]
    assert names.index("TILE_X0Y0.EXTRA") == names.index("TILE_X0Y0.MUX.SEL0") + 1


def test_selection_insert_before_is_chainable() -> None:
    out = (
        edit(parse_string(_source()))
        .select(name="TILE_X1Y0.LUT.INIT")
        .insert_before(FasmLine(comment=" section"))
        .commit()
    )
    assert "# section\nTILE_X1Y0.LUT.INIT" in out.to_string()


def test_insert_with_foreign_selection_raises() -> None:
    a = edit(parse_string("A\n"))
    b = edit(parse_string("B\n"))
    with pytest.raises(FasmBuildError, match="different editor"):
        a.insert_before(b.select(name="B"), (FasmLine(comment=" x"),))


def test_insert_with_stale_selection_raises() -> None:
    ed = edit(parse_string("A.X\nB.Y\n"))
    stale = ed.select(name="A.X")
    ed2 = stale.remove()  # transforms return a fresh editor; stale is now invalid
    with pytest.raises(FasmBuildError, match="different editor"):
        ed2.insert_after(stale, (FasmLine(comment=" x"),))


def test_append_accepts_single_line() -> None:
    out = edit(parse_string("A\n")).append(FasmLine(comment=" end")).commit()
    assert out[-1].comment == " end"


def test_insert_after_accepts_single_line() -> None:
    out = (
        edit(parse_string("A\n"))
        .select(name="A")
        .insert_after(FasmLine(comment=" x"))
        .commit()
    )
    assert out[1].comment == " x"


# -- consistent builder surface: width= on enable/clear, Iterable extend ------


def test_enable_with_width() -> None:
    feature = FasmBuilder().enable("F", width=8).build()[0].feature
    assert feature.address == Address(low=0, high=7)
    assert feature.value is None


def test_clear_with_width() -> None:
    feature = FasmBuilder().clear("F", width=8).build()[0].feature
    assert feature.address == Address(low=0, high=7)
    assert feature.value == FeatureValue(0, ValueFormat.VERILOG_HEX)


def test_extend_accepts_any_iterable() -> None:
    b = FasmBuilder()
    b.extend([FasmLine(comment=" a"), FasmLine(comment=" b")])  # a list, not a tuple
    assert len(b.build()) == 2


# -- discoverability: feature-requiring transforms name the offending line ----


def test_transform_error_names_the_offending_line() -> None:
    with pytest.raises(FasmBuildError, match="header"):
        edit(parse_string("# header\nA.X\n")).select().set_value(0)


# -- cleanup guard: the builder's feature pattern tracks the grammar ----------


def test_feature_regex_matches_grammar_terminal() -> None:
    import re
    from importlib import resources

    from fasm_toolkit.dsl.builder import _FEATURE_RE

    grammar = resources.files("fasm_toolkit.grammar").joinpath("fasm.lark").read_text()
    match = re.search(r"FEATURE:\s*/(.+)/", grammar)
    assert match is not None
    assert _FEATURE_RE.pattern == match.group(1)
