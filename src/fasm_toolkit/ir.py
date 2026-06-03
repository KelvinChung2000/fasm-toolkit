"""The FASM intermediate representation (IR).

The IR is a small set of immutable, typed dataclasses. Parsing produces a
:class:`FasmFile`; manipulation and emission operate on it. The IR deliberately
preserves intent that the original ``fasm`` library kept (value formats,
comments, annotations) so that a parsed file round-trips back to equal IR.

Design notes:

* A feature with no value (``feature`` on its own) is an *implicit* set-to-one;
  it is modelled as ``SetFeature.value is None``. An *explicit* one
  (``feature = 1``) carries a :class:`FeatureValue`. Keeping the two distinct is
  what lets emission reproduce the original line.
* The declared width of a sized Verilog literal (the ``8`` in ``8'hFF``) is
  validated at parse time and then discarded: the emitted width is always
  derived from the feature address, matching the reference library.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

__all__ = [
    "ValueFormat",
    "FeatureValue",
    "Address",
    "Annotation",
    "SetFeature",
    "FasmLine",
    "FasmFile",
]


class ValueFormat(Enum):
    """How a FASM value was written, so it can be reproduced on output."""

    PLAIN = "plain"
    """A bare decimal with no size or radix, e.g. ``42``."""
    VERILOG_DECIMAL = "decimal"
    """A sized decimal, e.g. ``8'd42``."""
    VERILOG_HEX = "hex"
    """A sized hexadecimal, e.g. ``8'h2a``."""
    VERILOG_BINARY = "binary"
    """A sized binary, e.g. ``8'b00101010``."""
    VERILOG_OCTAL = "octal"
    """A sized octal, e.g. ``8'o52``."""


@dataclass(frozen=True, slots=True)
class FeatureValue:
    """The value assigned to a feature, with the format it was written in."""

    value: int
    format: ValueFormat

    def __post_init__(self) -> None:
        """Reject negative values."""
        if self.value < 0:
            raise ValueError(f"feature value must be non-negative, got {self.value}")


@dataclass(frozen=True, slots=True)
class Address:
    """A feature bit address.

    Written ``[high:low]`` for a range, or ``[index]`` for a single bit. The
    single-bit form is represented with ``high is None`` so that ``[17]`` and
    ``[17:17]`` remain distinguishable for round-tripping.
    """

    low: int
    high: int | None = None

    def __post_init__(self) -> None:
        """Reject negative indices and ranges with high below low."""
        if self.low < 0:
            raise ValueError(f"address index must be non-negative, got {self.low}")
        if self.high is not None and self.high < self.low:
            raise ValueError(f"address high ({self.high}) must be >= low ({self.low})")

    @property
    def width(self) -> int:
        """Number of bits the address spans."""
        return 1 if self.high is None else self.high - self.low + 1


@dataclass(frozen=True, slots=True)
class Annotation:
    """A ``name = "value"`` annotation."""

    name: str
    value: str


@dataclass(frozen=True, slots=True)
class SetFeature:
    """A feature assignment such as ``feature[31:0] = 42``."""

    name: str
    address: Address | None = None
    value: FeatureValue | None = None

    @property
    def width(self) -> int:
        """The width used when emitting the value (derived from the address)."""
        return self.address.width if self.address is not None else 1

    def value_fits(self) -> bool:
        """Whether the value fits the emit width. An implicit one always fits.

        The single source of truth for the magnitude check, shared by the parser
        (which validates input) and the eDSL builder/editor (which validate
        generated and edited features), so the two cannot drift.
        """
        if self.value is None:
            return True
        return self.value.value < (1 << self.width)


@dataclass(frozen=True, slots=True)
class FasmLine:
    """A single FASM line: an optional feature, annotations, and a comment.

    The comment text excludes the leading ``#`` but keeps any following
    whitespace, so ``# hello`` is stored as ``" hello"``.
    """

    feature: SetFeature | None = None
    annotations: tuple[Annotation, ...] = ()
    comment: str | None = None

    @property
    def is_blank(self) -> bool:
        """True when the line has no feature, annotations, or comment."""
        return self.feature is None and not self.annotations and self.comment is None


@dataclass(frozen=True, slots=True)
class FasmFile:
    """An ordered collection of FASM lines, with IR manipulation helpers."""

    lines: tuple[FasmLine, ...] = ()

    def __iter__(self) -> Iterator[FasmLine]:
        """Iterate over the lines."""
        return iter(self.lines)

    def __len__(self) -> int:
        """Return the number of lines."""
        return len(self.lines)

    def __getitem__(self, index: int) -> FasmLine:
        """Return the line at ``index``."""
        return self.lines[index]

    # -- queries ----------------------------------------------------------

    def features(self) -> Iterator[SetFeature]:
        """Yield every :class:`SetFeature` in order (comment-only lines skipped)."""
        for line in self.lines:
            if line.feature is not None:
                yield line.feature

    def feature_lines(self) -> Iterator[FasmLine]:
        """Yield only lines that assign a feature."""
        for line in self.lines:
            if line.feature is not None:
                yield line

    # -- structural manipulation -----------------------------------------

    def filter(self, predicate: Callable[[FasmLine], bool]) -> "FasmFile":
        """Return a new file keeping only lines for which ``predicate`` holds."""
        return FasmFile(tuple(line for line in self.lines if predicate(line)))

    def with_feature_prefix(self, prefix: str) -> "FasmFile":
        """Keep only feature lines whose feature name starts with ``prefix``."""
        return self.filter(
            lambda line: (
                line.feature is not None and line.feature.name.startswith(prefix)
            )
        )

    def without_comments(self) -> "FasmFile":
        """Drop comments, then drop lines left blank by that removal."""
        stripped = (replace(line, comment=None) for line in self.lines)
        return FasmFile(tuple(line for line in stripped if not line.is_blank))

    def without_annotations(self) -> "FasmFile":
        """Drop annotations, then drop lines left blank by that removal."""
        stripped = (replace(line, annotations=()) for line in self.lines)
        return FasmFile(tuple(line for line in stripped if not line.is_blank))

    def append(self, line: FasmLine) -> "FasmFile":
        """Return a new file with ``line`` appended."""
        return FasmFile(self.lines + (line,))

    def extend(self, lines: tuple[FasmLine, ...]) -> "FasmFile":
        """Return a new file with ``lines`` appended."""
        return FasmFile(self.lines + tuple(lines))

    # -- convenience bridges to the transform / emit layers --------------

    def to_string(self, *, canonical: bool = False) -> str:
        """Serialise back to FASM text. See :mod:`fasm_toolkit.emit`."""
        from fasm_toolkit.emit import to_string

        return to_string(self, canonical=canonical)

    def canonical(self) -> "FasmFile":
        """Return the canonical (one set bit per line) form of this file."""
        from fasm_toolkit.transform import canonicalize

        return canonicalize(self)

    def merged(
        self,
        *,
        zero_function: Callable[[str], bool] | None = None,
        sort_key: Callable[[str], Any] | None = None,
    ) -> "FasmFile":
        """Group, merge bit ranges, and sort. See :mod:`fasm_toolkit.transform`."""
        from fasm_toolkit.transform import merge_and_sort

        return merge_and_sort(self, zero_function=zero_function, sort_key=sort_key)
