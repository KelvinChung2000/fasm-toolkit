"""Parse FASM text into the IR.

The parser is a two-stage pipeline: Lark builds a parse tree with an LALR(1)
grammar, then :class:`_ToIR` lowers that tree into the dataclasses in
:mod:`fasm_toolkit.ir`. Keeping the transform as a separate pass (rather than
running it inside the Lark constructor) leaves the grammar decoupled from the
IR and makes the lowering independently testable.
"""

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from lark import Lark, Token, Transformer, v_args
from lark.exceptions import LarkError, UnexpectedInput, VisitError
from loguru import logger

from fasm_toolkit.errors import FasmError, FasmSyntaxError, FasmValidationError
from fasm_toolkit.ir import (
    Address,
    Annotation,
    FasmFile,
    FasmLine,
    FeatureValue,
    SetFeature,
    ValueFormat,
)

__all__ = [
    "parse_string",
    "parse_file",
    "FasmError",
    "FasmSyntaxError",
    "FasmValidationError",
]


@dataclass(frozen=True, slots=True)
class _ParsedValue:
    """Pairs a value with its declared literal width, for validation only."""

    value: FeatureValue
    declared_width: int | None


def _digits(token: object) -> str:
    return str(token).replace("_", "")


def _unescape_annotation_value(raw: str) -> str:
    r"""Turn ESCAPED_STRING inner text into the logical annotation value.

    The inverse of :func:`fasm_toolkit.emit.escape_annotation_value`: a backslash
    escapes the character that follows it (so ``\"`` becomes ``"`` and ``\\``
    becomes ``\``), which is what lets a value containing a quote round-trip.
    """
    out: list[str] = []
    i = 0
    while i < len(raw):
        if raw[i] == "\\" and i + 1 < len(raw):
            out.append(raw[i + 1])
            i += 2
        else:
            out.append(raw[i])
            i += 1
    return "".join(out)


class _ToIR(Transformer):
    """Lower a Lark parse tree into :mod:`fasm_toolkit.ir` dataclasses."""

    def start(self, lines: list[FasmLine | None]) -> FasmFile:
        return FasmFile(tuple(line for line in lines if line is not None))

    @v_args(inline=True)
    def fasm_line(
        self,
        feature: SetFeature | None,
        annotations: tuple[Annotation, ...] | None,
        comment: object | None,
    ) -> FasmLine | None:
        comment_text = None if comment is None else str(comment)[1:]
        anns = annotations if annotations is not None else ()
        if feature is None and not anns and comment_text is None:
            return None  # blank line: dropped from the IR
        return FasmLine(feature=feature, annotations=anns, comment=comment_text)

    @v_args(inline=True)
    def set_feature(
        self,
        feature: object,
        address: Address | None,
        parsed: _ParsedValue | None,
    ) -> SetFeature:
        value: FeatureValue | None = None
        if parsed is not None:
            value = parsed.value
            width = address.width if address is not None else 1
            if parsed.declared_width is not None and parsed.declared_width > width:
                raise FasmValidationError(
                    f"declared width {parsed.declared_width} exceeds address "
                    f"width {width} for feature {feature!s}"
                )
        result = SetFeature(name=str(feature), address=address, value=value)
        if value is not None and not result.value_fits():
            raise FasmValidationError(
                f"value {value.value} does not fit in width {result.width} "
                f"for feature {feature!s}"
            )
        return result

    @v_args(inline=True)
    def address(self, first: Token, second: Token | None) -> Address:
        # Written [high:low]; for a single index [n] the grammar leaves the
        # second slot empty.
        if second is None:
            return Address(low=int(first), high=None)
        return Address(low=int(second), high=int(first))

    def annotations(self, items: list[Annotation]) -> tuple[Annotation, ...]:
        return tuple(items)

    @v_args(inline=True)
    def annotation(self, name: object, value: object) -> Annotation:
        # ESCAPED_STRING includes the surrounding quotes; strip them, then
        # resolve escapes so the IR holds the logical value (emit re-escapes).
        return Annotation(
            name=str(name), value=_unescape_annotation_value(str(value)[1:-1])
        )

    # -- value alternatives ----------------------------------------------

    def _sized(self, items: list, base: int, fmt: ValueFormat) -> _ParsedValue:
        declared_width = int(str(items[0])) if len(items) == 2 else None
        return _ParsedValue(
            FeatureValue(int(_digits(items[-1]), base), fmt), declared_width
        )

    def hex_value(self, items: list) -> _ParsedValue:
        return self._sized(items, 16, ValueFormat.VERILOG_HEX)

    def bin_value(self, items: list) -> _ParsedValue:
        return self._sized(items, 2, ValueFormat.VERILOG_BINARY)

    def dec_value(self, items: list) -> _ParsedValue:
        return self._sized(items, 10, ValueFormat.VERILOG_DECIMAL)

    def oct_value(self, items: list) -> _ParsedValue:
        return self._sized(items, 8, ValueFormat.VERILOG_OCTAL)

    def plain_value(self, items: list) -> _ParsedValue:
        return _ParsedValue(
            FeatureValue(int(_digits(items[0]), 10), ValueFormat.PLAIN), None
        )


def _build_parser() -> Lark:
    grammar = resources.files("fasm_toolkit.grammar").joinpath("fasm.lark").read_text()
    return Lark(
        grammar,
        parser="lalr",
        lexer="contextual",
        maybe_placeholders=True,
        propagate_positions=True,
    )


_PARSER = _build_parser()
_TRANSFORMER = _ToIR()


def parse_string(text: str) -> FasmFile:
    """Parse a string of FASM source into a :class:`FasmFile`.

    >>> parse_string("a.b.c = 1").lines[0].feature.name
    'a.b.c'
    """
    # The grammar expects every line, including the last, to end in a newline.
    if not text.endswith("\n"):
        text = text + "\n"
    logger.debug("Parsing {} characters of FASM", len(text))
    try:
        tree = _PARSER.parse(text)
    except UnexpectedInput as exc:
        logger.debug("FASM syntax error: {}", exc)
        raise FasmSyntaxError(str(exc)) from exc
    except LarkError as exc:  # pragma: no cover - defensive
        logger.debug("FASM parse error: {}", exc)
        raise FasmSyntaxError(str(exc)) from exc
    try:
        result = _TRANSFORMER.transform(tree)
    except VisitError as exc:
        # Lark wraps exceptions raised inside the transform; surface ours.
        if isinstance(exc.orig_exc, FasmError):
            logger.debug("FASM validation error: {}", exc.orig_exc)
            raise exc.orig_exc from None
        raise
    logger.debug("Parsed {} FASM line(s)", len(result.lines))
    return result


def parse_file(path: str | Path) -> FasmFile:
    """Parse a FASM file into a :class:`FasmFile`."""
    path = Path(path)
    logger.debug("Reading FASM file: {}", path)
    return parse_string(path.read_text())
