"""The generation facade (FasmBuilder) and the bits helper."""

import pytest

from fasm_toolkit import (
    Address,
    FasmBuilder,
    FasmLine,
    FeatureValue,
    SetFeature,
    ValueFormat,
    bits,
    parse_string,
)
from fasm_toolkit.errors import FasmBuildError


def test_bits_orders_high_then_low() -> None:
    assert bits(15, 0) == Address(low=0, high=15)
    assert bits(15, 0).width == 16


def test_set_with_width_defaults_to_hex() -> None:
    feature = FasmBuilder().set("LUT.INIT", 0xABCD, width=16).build()[0].feature
    assert feature == SetFeature(
        name="LUT.INIT",
        address=Address(low=0, high=15),
        value=FeatureValue(0xABCD, ValueFormat.VERILOG_HEX),
    )


def test_set_single_bit_with_at() -> None:
    feature = FasmBuilder().set("F", 1, at=3).build()[0].feature
    assert feature.address == Address(low=3, high=None)
    assert feature.value == FeatureValue(1, ValueFormat.VERILOG_HEX)


def test_set_no_address_defaults_to_plain() -> None:
    feature = FasmBuilder().set("F", 1).build()[0].feature
    assert feature.address is None
    assert feature.value == FeatureValue(1, ValueFormat.PLAIN)


def test_set_with_explicit_format_override() -> None:
    feature = (
        FasmBuilder()
        .set("F", 10, width=4, fmt=ValueFormat.VERILOG_BINARY)
        .build()[0]
        .feature
    )
    assert feature.value == FeatureValue(10, ValueFormat.VERILOG_BINARY)


def test_set_with_bits_range() -> None:
    feature = FasmBuilder().set("F", 0xF, at=bits(7, 4)).build()[0].feature
    assert feature.address == Address(low=4, high=7)


def test_enable_is_implicit_one() -> None:
    feature = FasmBuilder().enable("MUX.SEL0").build()[0].feature
    assert feature == SetFeature(name="MUX.SEL0")
    assert feature.value is None


def test_clear_emits_explicit_zero() -> None:
    feature = FasmBuilder().clear("F", at=3).build()[0].feature
    assert feature.value == FeatureValue(0, ValueFormat.VERILOG_HEX)


def test_scope_prefixes_names() -> None:
    b = FasmBuilder()
    with b.scope("TILE_X0Y0"):
        b.enable("MUX.SEL0")
    assert b.build()[0].feature.name == "TILE_X0Y0.MUX.SEL0"


def test_nested_scopes_compose_left_to_right() -> None:
    b = FasmBuilder()
    with b.scope("TILE_X0Y0"), b.scope("MUX"):
        b.enable("SEL0")
    assert b.build()[0].feature.name == "TILE_X0Y0.MUX.SEL0"


def test_scope_pops_after_block() -> None:
    b = FasmBuilder()
    with b.scope("A"):
        b.enable("X")
    b.enable("Y")  # outside the scope
    names = [line.feature.name for line in b.build()]
    assert names == ["A.X", "Y"]


def test_comment_renders_body_verbatim() -> None:
    file = FasmBuilder().comment(" hello").build()
    assert file[0] == FasmLine(comment=" hello")
    assert file.to_string() == "# hello\n"


def test_line_and_extend_drop_in_raw_ir() -> None:
    raw = FasmLine(feature=SetFeature("RAW"))
    b = FasmBuilder()
    b.line(raw)
    b.extend((FasmLine(comment=" two"),))
    assert b.build().lines == (raw, FasmLine(comment=" two"))


def test_macro_is_a_plain_function() -> None:
    def lut_init(builder: FasmBuilder, value: int) -> None:
        builder.set("LUT.INIT", value, width=16)

    b = FasmBuilder()
    for x in range(3):
        with b.scope(f"TILE_X{x}Y0"):
            lut_init(b, 0x1)
    names = [line.feature.name for line in b.build()]
    assert names == [
        "TILE_X0Y0.LUT.INIT",
        "TILE_X1Y0.LUT.INIT",
        "TILE_X2Y0.LUT.INIT",
    ]


def test_round_trip_invariant() -> None:
    b = FasmBuilder()
    with b.scope("TILE_X0Y0"):
        b.set("LUT.INIT", 0xABCD, width=16)
        b.enable("MUX.SEL0")
        b.clear("CONFIG", at=2)
    b.comment(" trailer")
    file = b.build()
    assert parse_string(file.to_string()) == file


# -- validation: no fallbacks, fail loudly ------------------------------------


def test_value_too_wide_raises() -> None:
    with pytest.raises(FasmBuildError, match="one bit"):
        FasmBuilder().set("F", 42)  # unaddressed, so one bit wide


def test_addressed_value_too_wide_raises() -> None:
    with pytest.raises(FasmBuildError, match="does not fit in width"):
        FasmBuilder().set("F", 16, width=4)  # 16 needs 5 bits


def test_invalid_feature_name_raises() -> None:
    with pytest.raises(FasmBuildError, match="invalid feature name"):
        FasmBuilder().enable("0bad")


def test_invalid_scope_makes_invalid_name() -> None:
    b = FasmBuilder()
    with pytest.raises(FasmBuildError, match="invalid feature name"), b.scope("0bad"):
        b.enable("X")


def test_at_and_width_together_raise() -> None:
    with pytest.raises(FasmBuildError, match="not both"):
        FasmBuilder().set("F", 1, at=3, width=4)


def test_empty_scope_raises() -> None:
    with pytest.raises(FasmBuildError, match="non-empty"), FasmBuilder().scope(""):
        pass


def test_zero_width_raises() -> None:
    with pytest.raises(FasmBuildError, match="width must be >= 1"):
        FasmBuilder().set("F", 0, width=0)


def test_line_rejects_non_fasmline() -> None:
    with pytest.raises(FasmBuildError, match="expects a FasmLine"):
        FasmBuilder().line("not a line")  # type: ignore[arg-type]


def test_builder_is_silent_by_default() -> None:
    """The library logs nothing unless the consumer enables it (loguru rule)."""
    from loguru import logger

    logger.disable("fasm_toolkit")
    records: list[str] = []
    sink_id = logger.add(records.append, level="DEBUG")
    try:
        FasmBuilder().enable("X").build()
    finally:
        logger.remove(sink_id)
    assert records == []
