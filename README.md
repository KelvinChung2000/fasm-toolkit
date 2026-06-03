# fasm-toolkit

A modern parser and manipulation toolkit for the [FPGA Assembly (FASM)](https://fasm.readthedocs.io/) format.

It is a clean-room successor to the reference [`fasm`](https://github.com/chipsalliance/fasm) library. The core parser is built on [Lark](https://github.com/lark-parser/lark), and all manipulation happens on a small, typed intermediate representation (IR). Output is byte-for-byte compatible with the reference library (verified by the parity tests).

## Pipeline

The library follows a `parse -> IR -> manipulate -> emit` flow.

```python
from fasm_toolkit import parse_string

fasm = parse_string("CLB.A[3:0] = 4'b1010")

# Manipulate on the IR.
just_clb = fasm.with_feature_prefix("CLB")

# Emit. Default form preserves value formats, annotations, and comments.
print(fasm.to_string())            # CLB.A[3:0] = 4'b1010
print(fasm.to_string(canonical=True))  # CLB.A[1] / CLB.A[3], one bit per line
```

## The IR

The IR is a set of immutable, typed dataclasses in `fasm_toolkit.ir`.

- `FasmFile` is an ordered collection of `FasmLine` with manipulation helpers.
- `FasmLine` carries an optional `SetFeature`, a tuple of `Annotation`, and an optional comment.
- `SetFeature` is a feature name with an optional `Address` and optional `FeatureValue`.
- `FeatureValue` keeps the value together with the `ValueFormat` it was written in, so a parsed file round-trips back to equal IR.

A feature with no value (`feature`) is an implicit set-to-one and is modelled as `SetFeature.value is None`, which is what keeps it distinct from the explicit `feature = 1`.

## Manipulating a file

`FasmFile` is immutable; every helper returns a new file.

```python
fasm.features()                 # iterate over SetFeature objects
fasm.with_feature_prefix("CLB") # keep features under a prefix
fasm.filter(predicate)          # keep lines matching a predicate
fasm.without_comments()         # drop comments
fasm.canonical()                # canonical (one set bit per line) form
fasm.merged()                   # group, merge bit ranges, and sort
```

## Command line

```
fasm-toolkit format FILE         # reformat, preserving intent
fasm-toolkit canonicalize FILE   # canonical form, sorted and de-duplicated
fasm-toolkit merge FILE          # merge bit ranges and sort
fasm-toolkit parse FILE          # dump the IR for inspection
```

## Development

Dependencies are managed with [uv](https://github.com/astral-sh/uv).

```
uv sync --extra dev   # set up the environment
uv run pytest         # run the test suite
```

The parity tests in `tests/test_parity.py` compare output against a reference
`fasm` checkout in a sibling `../fasm` directory and are skipped when it is not
present.

## Status and roadmap

This first release is a faithful, modern core. The IR is designed so a future
FASM++ superset (macros, grouping, low-level bitstream hooks that compile down
to plain FASM) can be added without disturbing the existing data model.
