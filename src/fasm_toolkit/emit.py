"""Serialise the IR back to FASM text.

Two forms are produced:

* default - reproduces each line, preserving value formats, annotations, and
  comments. Whitespace is normalised to single spaces, so the output is not
  byte-identical to a hand-written file, but re-parsing it yields equal IR.
* canonical - the F4PGA canonical form: every set bit on its own line as a
  width-one, value-one feature, de-duplicated and sorted.
"""

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
    "to_string",
    "line_to_string",
    "set_feature_to_string",
    "feature_value_to_string",
    "escape_annotation_value",
]


def feature_value_to_string(value: FeatureValue, width: int) -> str:
    """Render a value. Sized formats use ``width`` (taken from the address)."""
    v = value.value
    match value.format:
        case ValueFormat.PLAIN:
            return str(v)
        case ValueFormat.VERILOG_HEX:
            return f"{width}'h{v:X}"
        case ValueFormat.VERILOG_DECIMAL:
            return f"{width}'d{v}"
        case ValueFormat.VERILOG_OCTAL:
            return f"{width}'o{v:o}"
        case ValueFormat.VERILOG_BINARY:
            return f"{width}'b{v:b}"
    raise ValueError(f"unknown value format: {value.format!r}")  # pragma: no cover


def _address_to_string(address: Address) -> str:
    if address.high is None:
        return f"[{address.low}]"
    return f"[{address.high}:{address.low}]"


def set_feature_to_string(feature: SetFeature) -> str:
    """Render a feature assignment, e.g. ``a[3:0] = 4'b1010``."""
    out = feature.name
    if feature.address is not None:
        out += _address_to_string(feature.address)
    if feature.value is not None:
        out += " = " + feature_value_to_string(feature.value, feature.width)
    return out


def escape_annotation_value(value: str) -> str:
    """Escape a logical annotation value into ESCAPED_STRING inner text.

    The inverse of the parser's unescaping: a backslash or double quote in the
    value is escaped so the emitted ``"..."`` literal re-parses to the same
    logical value. Backslash is escaped first so a value's quotes are not
    double-counted.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _annotations_to_string(annotations: tuple[Annotation, ...]) -> str:
    body = ", ".join(
        f'{a.name} = "{escape_annotation_value(a.value)}"' for a in annotations
    )
    return f"{{ {body} }}"


def line_to_string(line: FasmLine) -> str:
    """Render a whole line: feature, annotations, and comment, space-joined."""
    parts: list[str] = []
    if line.feature is not None:
        parts.append(set_feature_to_string(line.feature))
    if line.annotations:
        parts.append(_annotations_to_string(line.annotations))
    if line.comment is not None:
        parts.append("#" + line.comment)
    return " ".join(parts)


def to_string(file: FasmFile, *, canonical: bool = False) -> str:
    """Serialise a :class:`FasmFile` to FASM text (always newline-terminated)."""
    if canonical:
        return _to_canonical_string(file)
    lines = [line_to_string(line) for line in file.lines]
    return "\n".join(lines) + "\n"


def _to_canonical_string(file: FasmFile) -> str:
    from fasm_toolkit.transform import canonical_set_features

    strings: set[str] = set()
    for feature in file.features():
        for canonical in canonical_set_features(feature):
            strings.add(set_feature_to_string(canonical))
    return "\n".join(sorted(strings)) + "\n"
