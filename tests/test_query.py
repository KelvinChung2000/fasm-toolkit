"""The editing facade (edit / Editor / Selection)."""

import pytest

from fasm_toolkit import (
    FasmBuilder,
    FasmFile,
    FasmLine,
    bits,
    edit,
    parse_string,
)
from fasm_toolkit.errors import FasmBuildError

SOURCE = (
    "# header comment\n"
    "TILE_X0Y0.LUT.INIT[15:0] = 16'hABCD\n"
    "TILE_X0Y0.MUX.SEL0\n"
    "TILE_X1Y0.LUT.INIT[15:0] = 16'h1234\n"
    'TILE_X1Y0.MUX.SEL0 { net = "clk" }\n'
)


def _file() -> FasmFile:
    return parse_string(SOURCE)


def test_edit_without_changes_preserves_file() -> None:
    file = _file()
    assert edit(file).commit() == file


def test_select_by_prefix_matches_only_those_lines() -> None:
    sel = edit(_file()).select(prefix="TILE_X0Y0.LUT")
    assert len(sel) == 1
    assert next(iter(sel)).feature.name == "TILE_X0Y0.LUT.INIT"


def test_select_by_name_is_exact() -> None:
    sel = edit(_file()).select(name="TILE_X0Y0.MUX.SEL0")
    assert len(sel) == 1


def test_select_by_predicate() -> None:
    sel = edit(_file()).select(predicate=lambda line: line.comment is not None)
    assert len(sel) == 1
    assert next(iter(sel)).comment == " header comment"


def test_select_by_annotation() -> None:
    sel = edit(_file()).select(has_annotation="net")
    assert len(sel) == 1
    assert next(iter(sel)).feature.name == "TILE_X1Y0.MUX.SEL0"


def test_set_value_changes_only_selected_and_keeps_format() -> None:
    out = edit(_file()).select(prefix="TILE_X0Y0.LUT").set_value(0).commit()
    lines = out.to_string().splitlines()
    assert lines[1] == "TILE_X0Y0.LUT.INIT[15:0] = 16'h0"  # format preserved
    assert lines[3] == "TILE_X1Y0.LUT.INIT[15:0] = 16'h1234"  # untouched


def test_untouched_lines_are_byte_identical() -> None:
    out = (
        edit(_file())
        .select(name="TILE_X0Y0.MUX.SEL0")
        .add_annotation("note", "x")
        .commit()
    )
    out_lines = out.to_string().splitlines()
    src_lines = SOURCE.splitlines()
    # Only line index 2 (the selected MUX.SEL0) changed.
    for i in (0, 1, 3, 4):
        assert out_lines[i] == src_lines[i]


def test_set_address_revalidates_width() -> None:
    src = parse_string("F[15:0] = 16'hFFFF\n")
    with pytest.raises(FasmBuildError, match="does not fit"):
        edit(src).select(name="F").set_address(bits(3, 0))


def test_rename_adds_prefix() -> None:
    out = (
        edit(_file()).select(prefix="TILE_X0Y0").rename(lambda n: "BLOCK." + n).commit()
    )
    names = [line.feature.name for line in out.feature_lines()]
    assert "BLOCK.TILE_X0Y0.LUT.INIT" in names
    assert "TILE_X1Y0.LUT.INIT" in names  # other tile untouched


def test_rename_validates_result() -> None:
    with pytest.raises(FasmBuildError, match="invalid feature name"):
        edit(_file()).select(prefix="TILE_X0Y0.LUT").rename(lambda n: "0" + n)


def test_remove_drops_selected_lines() -> None:
    out = edit(_file()).select(prefix="TILE_X1Y0").remove().commit()
    names = [line.feature.name for line in out.feature_lines()]
    assert all(not n.startswith("TILE_X1Y0") for n in names)
    assert len(out) == 3  # comment + two X0Y0 lines


def test_map_applies_arbitrary_transform() -> None:
    from dataclasses import replace

    out = (
        edit(_file())
        .select(prefix="TILE_X0Y0.MUX")
        .map(lambda line: replace(line, comment=" mapped"))
        .commit()
    )
    line = next(
        ln for ln in out if ln.feature and ln.feature.name == "TILE_X0Y0.MUX.SEL0"
    )
    assert line.comment == " mapped"


def test_insert_after_selection() -> None:
    extra = FasmBuilder().enable("TILE_X0Y0.EXTRA").build()
    editor = edit(_file())
    out = editor.insert_after(editor.select(name="TILE_X0Y0.MUX.SEL0"), extra).commit()
    names = [line.feature.name for line in out.feature_lines()]
    assert names.index("TILE_X0Y0.EXTRA") == names.index("TILE_X0Y0.MUX.SEL0") + 1


def test_insert_before_selection() -> None:
    extra = (FasmLine(comment=" section: tile 1"),)
    editor = edit(_file())
    out = editor.insert_before(editor.select(name="TILE_X1Y0.LUT.INIT"), extra).commit()
    text = out.to_string()
    assert "# section: tile 1\nTILE_X1Y0.LUT.INIT" in text


def test_append_adds_to_end() -> None:
    out = edit(_file()).append((FasmLine(comment=" end"),)).commit()
    assert out[-1].comment == " end"


def test_chained_edits_read_top_to_bottom() -> None:
    out = (
        edit(_file())
        .select(prefix="TILE_X0Y0.LUT")
        .set_value(0)
        .select(prefix="TILE_X1Y0.LUT")
        .set_value(1)
        .commit()
    )
    text = out.to_string()
    assert "TILE_X0Y0.LUT.INIT[15:0] = 16'h0" in text
    assert "TILE_X1Y0.LUT.INIT[15:0] = 16'h1" in text


def test_editor_is_immutable() -> None:
    file = _file()
    editor = edit(file)
    editor.select(prefix="TILE_X0Y0.LUT").set_value(0)  # discard result
    assert editor.commit() == file  # original editor unchanged


# -- validation ---------------------------------------------------------------


def test_set_value_on_non_feature_line_raises() -> None:
    with pytest.raises(FasmBuildError, match="requires a feature line"):
        edit(_file()).select(predicate=lambda line: line.comment is not None).set_value(
            0
        )


def test_insert_before_empty_selection_raises() -> None:
    editor = edit(_file())
    empty = editor.select(name="does.not.exist")
    with pytest.raises(FasmBuildError, match="empty"):
        editor.insert_before(empty, (FasmLine(comment=" x"),))


def test_insert_rejects_non_fasmline() -> None:
    editor = edit(_file())
    with pytest.raises(FasmBuildError, match="expected FasmLine"):
        editor.append(["not a line"])  # type: ignore[list-item]


def test_map_must_return_fasmline() -> None:
    with pytest.raises(FasmBuildError, match="must return a FasmLine"):
        edit(_file()).select(prefix="TILE_X0Y0.MUX").map(lambda _line: "nope")
