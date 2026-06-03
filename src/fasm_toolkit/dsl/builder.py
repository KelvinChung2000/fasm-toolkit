"""Generation facade: build FASM with a fluent, scoped Python builder.

The eDSL philosophy is that Python already supplies macros (functions),
repetition (``for``), and modularity (``import``). The one thing it lacks for
FASM authoring is ergonomic nesting of dotted feature names, which is what
:class:`FasmBuilder` adds through :meth:`FasmBuilder.scope`.

Every builder call appends to an ordered list of :class:`~fasm_toolkit.ir.FasmLine`
objects; :meth:`FasmBuilder.build` freezes that list into an immutable
:class:`~fasm_toolkit.ir.FasmFile`, which the existing emit and transform layers
then serialise. The builder validates names, addresses, and value widths against
the same rules the parser enforces, so anything it builds re-parses to equal IR.
"""

import re
from collections.abc import Iterable, Iterator
from contextlib import contextmanager

from loguru import logger

from fasm_toolkit.errors import FasmBuildError
from fasm_toolkit.ir import (
    Address,
    FasmFile,
    FasmLine,
    FeatureValue,
    SetFeature,
    ValueFormat,
)

__all__ = [
    "FasmBuilder",
    "bits",
    "validate_feature_name",
    "validate_annotation_name",
    "build_feature_value",
    "coerce_lines",
]

# The FEATURE terminal from the FASM grammar (grammar/fasm.lark). A resolved,
# scope-joined feature name must match this exactly. The grammar is the single
# source of truth; tests/test_dsl_ergonomics.py asserts these stay in step.
_FEATURE_RE = re.compile(r"[a-zA-Z][0-9a-zA-Z_.]*")
# The ANNOTATION_NAME terminal from the same grammar.
_ANNOTATION_NAME_RE = re.compile(r"[.a-zA-Z][0-9a-zA-Z_]*")


def validate_feature_name(name: str) -> str:
    """Return ``name`` if it is a valid FASM feature name, else raise.

    Shared by the builder and the editor so generated and edited names obey the
    same grammar rule.
    """
    if not name:
        raise FasmBuildError("feature name must be a non-empty string")
    if _FEATURE_RE.fullmatch(name) is None:
        raise FasmBuildError(
            f"invalid feature name {name!r}: must match the FASM feature "
            f"pattern [a-zA-Z][0-9a-zA-Z_.]*"
        )
    return name


def validate_annotation_name(name: str) -> str:
    """Return ``name`` if it is a valid FASM annotation name, else raise."""
    if not name:
        raise FasmBuildError("annotation name must be a non-empty string")
    if _ANNOTATION_NAME_RE.fullmatch(name) is None:
        raise FasmBuildError(
            f"invalid annotation name {name!r}: must match the FASM annotation "
            f"pattern [.a-zA-Z][0-9a-zA-Z_]*"
        )
    return name


def bits(high: int, low: int) -> Address:
    """Return an :class:`Address` spanning ``[high:low]``.

    The argument order matches FASM text (high first), keeping call sites
    unambiguous where a bare ``(high, low)`` tuple would not be.

    >>> bits(15, 0)
    Address(low=0, high=15)
    """
    if isinstance(high, bool) or isinstance(low, bool):
        raise FasmBuildError("bits() expects two ints (high, low), not bools")
    return _address(low=low, high=high)


def _address(*, low: int, high: int | None) -> Address:
    """Build an :class:`Address`, surfacing its range check as FasmBuildError."""
    try:
        return Address(low=low, high=high)
    except ValueError as exc:  # negative index, or high < low
        raise FasmBuildError(str(exc)) from exc


def build_feature_value(value: int, fmt: ValueFormat) -> FeatureValue:
    """Build a :class:`FeatureValue`, surfacing a bad value as FasmBuildError.

    Shared by the builder and the editor so a negative value fails as a
    ``FasmBuildError`` (inside the FasmError hierarchy) rather than leaking the
    IR's raw ``ValueError``.
    """
    try:
        return FeatureValue(value, fmt)
    except ValueError as exc:  # negative value
        raise FasmBuildError(str(exc)) from exc


def _resolve_address(at: int | Address | None, width: int | None) -> Address | None:
    """Turn the ``at`` / ``width`` arguments into a single address (or ``None``)."""
    if at is not None and width is not None:
        raise FasmBuildError(
            "pass either 'at' (an explicit address) or 'width' (shorthand for "
            "[width-1:0]), not both"
        )
    if width is not None:
        if isinstance(width, bool) or not isinstance(width, int):
            raise FasmBuildError(f"width must be an int, got {type(width).__name__}")
        if width < 1:
            raise FasmBuildError(f"width must be >= 1, got {width}")
        return _address(low=0, high=width - 1)
    if at is None:
        return None
    if isinstance(at, Address):
        return at
    if isinstance(at, bool) or not isinstance(at, int):
        raise FasmBuildError(f"'at' must be an int or Address, got {type(at).__name__}")
    return _address(low=at, high=None)


def coerce_lines(lines: "FasmLine | Iterable[FasmLine]") -> tuple[FasmLine, ...]:
    """Normalise a single line or an iterable of lines into a validated tuple.

    Accepting a lone :class:`FasmLine` keeps the common single-line insert from
    needing a one-element tuple, and gives a clear FasmBuildError (not a raw
    ``TypeError``) when the argument is neither.
    """
    if isinstance(lines, FasmLine):
        return (lines,)
    if not isinstance(lines, Iterable):
        raise FasmBuildError(
            f"expected a FasmLine or an iterable of FasmLine, got "
            f"{type(lines).__name__}"
        )
    result = tuple(lines)
    for line in result:
        if not isinstance(line, FasmLine):
            raise FasmBuildError(
                f"expected FasmLine objects, got {type(line).__name__}"
            )
    return result


def default_value_format(address: Address | None) -> ValueFormat:
    """Hex for an addressed value, plain decimal for a bare value (per the spec)."""
    return ValueFormat.PLAIN if address is None else ValueFormat.VERILOG_HEX


def check_value_fits(feature: SetFeature) -> None:
    """Reject a feature whose value does not fit its emit width.

    Defers to :meth:`SetFeature.value_fits`, the same check the parser runs, so
    anything the eDSL produces re-parses to equal IR. An implicit-one feature
    (``value is None``) always fits.
    """
    if feature.value_fits():
        return
    assert feature.value is not None  # value_fits is True for None
    if feature.address is None:
        raise FasmBuildError(
            f"value {feature.value.value} does not fit: feature {feature.name} "
            f"is unaddressed, so it is one bit wide (value must be 0 or 1); "
            f"pass at= or width= to address a wider field"
        )
    raise FasmBuildError(
        f"value {feature.value.value} does not fit in width {feature.width} "
        f"for feature {feature.name}"
    )


class FasmBuilder:
    r"""Accumulate FASM feature lines, then :meth:`build` an immutable file.

    >>> b = FasmBuilder()
    >>> with b.scope("TILE_X0Y0"):
    ...     _ = b.set("LUT.INIT", 0xABCD, width=16)
    ...     _ = b.enable("MUX.SEL0")
    >>> b.build().to_string()
    "TILE_X0Y0.LUT.INIT[15:0] = 16'hABCD\nTILE_X0Y0.MUX.SEL0\n"
    """

    def __init__(self) -> None:
        self._lines: list[FasmLine] = []
        self._scopes: list[str] = []

    # -- scoping ----------------------------------------------------------

    @contextmanager
    def scope(self, prefix: str) -> Iterator["FasmBuilder"]:
        """Prepend ``prefix.`` to every feature name emitted inside the block.

        Scopes nest: an inner ``scope`` composes onto the outer prefix, so the
        dotted name grows left to right exactly as written.
        """
        if not prefix:
            raise FasmBuildError("scope prefix must be a non-empty string")
        self._scopes.append(prefix)
        logger.debug("enter scope {!r} (depth {})", prefix, len(self._scopes))
        try:
            yield self
        finally:
            self._scopes.pop()
            logger.debug("exit scope {!r}", prefix)

    def _resolve_name(self, name: str) -> str:
        if not name:
            raise FasmBuildError("feature name must be a non-empty string")
        return validate_feature_name(".".join((*self._scopes, name)))

    # -- feature emission -------------------------------------------------

    def set(
        self,
        name: str,
        value: int,
        *,
        at: int | Address | None = None,
        width: int | None = None,
        fmt: ValueFormat | None = None,
    ) -> "FasmBuilder":
        """Emit a feature assignment ``name[...] = value``.

        ``at`` addresses a single bit (``int``) or a range (:class:`Address`,
        e.g. via :func:`bits`). ``width=N`` is shorthand for the range
        ``[N-1:0]``. ``fmt`` overrides the default value format (hex when an
        address is present, plain decimal otherwise).
        """
        address = _resolve_address(at, width)
        chosen_fmt = fmt if fmt is not None else default_value_format(address)
        feature_value = build_feature_value(value, chosen_fmt)
        feature = SetFeature(
            name=self._resolve_name(name), address=address, value=feature_value
        )
        check_value_fits(feature)
        return self._emit(FasmLine(feature=feature))

    def enable(
        self,
        name: str,
        *,
        at: int | Address | None = None,
        width: int | None = None,
    ) -> "FasmBuilder":
        """Emit an implicit-one feature (``value=None``), e.g. ``MUX.SEL0``.

        ``at`` / ``width`` address the feature exactly as in :meth:`set`.
        """
        address = _resolve_address(at, width)
        feature = SetFeature(name=self._resolve_name(name), address=address)
        return self._emit(FasmLine(feature=feature))

    def clear(
        self,
        name: str,
        *,
        at: int | Address | None = None,
        width: int | None = None,
    ) -> "FasmBuilder":
        """Emit an explicit zero, e.g. ``F[3] = 1'h0``.

        Useful where a cleared bit must be stated rather than implied, such as
        merge conflict checks. ``at`` / ``width`` address it as in :meth:`set`;
        a cleared value is just :meth:`set` with value ``0``.
        """
        return self.set(name, 0, at=at, width=width)

    # -- non-feature lines ------------------------------------------------

    def comment(self, text: str) -> "FasmBuilder":
        """Emit a comment-only line rendered as ``#<text>``.

        ``text`` is the comment body verbatim, matching the IR: pass a leading
        space (``" note"``) if you want ``# note`` rather than ``#note``. A
        newline is rejected, since a comment runs to the end of its line and an
        embedded newline would emit a second line that re-parses differently.
        """
        if "\n" in text or "\r" in text:
            raise FasmBuildError("comment text must not contain a newline")
        return self._emit(FasmLine(comment=text))

    def line(self, line: FasmLine) -> "FasmBuilder":
        """Append a raw :class:`FasmLine`, an escape hatch for the uncovered."""
        if not isinstance(line, FasmLine):
            raise FasmBuildError(
                f"line() expects a FasmLine, got {type(line).__name__}"
            )
        return self._emit(line)

    def extend(self, lines: "FasmLine | Iterable[FasmLine]") -> "FasmBuilder":
        """Append a single line or an iterable of raw :class:`FasmLine` objects."""
        for line in coerce_lines(lines):
            self._emit(line)
        return self

    # -- materialise ------------------------------------------------------

    def build(self) -> FasmFile:
        """Freeze the accumulated lines into an immutable :class:`FasmFile`."""
        logger.debug("build: {} line(s)", len(self._lines))
        return FasmFile(tuple(self._lines))

    # -- internals --------------------------------------------------------

    def _emit(self, line: FasmLine) -> "FasmBuilder":
        self._lines.append(line)
        return self
