"""Error handling for syntactic and semantic problems."""

import pytest

from fasm_toolkit import FasmSyntaxError, FasmValidationError, parse_string


def test_syntax_error_on_missing_feature_name() -> None:
    with pytest.raises(FasmSyntaxError):
        parse_string("[1:0] = 1")


def test_syntax_error_on_invalid_character() -> None:
    with pytest.raises(FasmSyntaxError):
        parse_string("@nope")


def test_syntax_error_on_unclosed_address() -> None:
    with pytest.raises(FasmSyntaxError):
        parse_string("feat[1 = 1")


def test_value_does_not_fit_address_width() -> None:
    with pytest.raises(FasmValidationError):
        parse_string("a[0:0] = 2")


def test_plain_value_too_wide_for_implicit_width() -> None:
    with pytest.raises(FasmValidationError):
        parse_string("feat = 2")


def test_declared_width_exceeds_address_width() -> None:
    with pytest.raises(FasmValidationError):
        parse_string("a[3:0] = 8'hFF")
