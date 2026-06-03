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

Data goes to stdout, so commands stay pipeable. Add `-v` (info) or `-vv`
(debug) to send logs to stderr.

## Logging

Logging uses [loguru](https://github.com/Delgan/loguru). Following loguru's
guidance for libraries, fasm-toolkit stays silent by default. A consuming
application turns it on with one call.

```python
from loguru import logger

logger.enable("fasm_toolkit")   # opt in
```

The `fasm-toolkit` command enables it automatically and exposes the level
through `-v` / `-vv`.

## Development

Dependencies are managed with [uv](https://github.com/astral-sh/uv). The `dev`
dependency group is installed by default.

```
uv sync                 # set up the environment (includes dev tools)
uv run pytest           # run the test suite
uv run ruff check       # lint
uv run ruff format      # format
uv run ty check         # type-check the library
uv sync --extra docs && uv run sphinx-build -b html docs docs/_build/html  # docs
```

Install the git hooks with `uv run pre-commit install`.

The parity tests in `tests/test_parity.py` compare output against a reference
`fasm` checkout in a sibling `../fasm` directory and are skipped when it is not
present.

## Releasing

Releases are automated with
[release-please](https://github.com/googleapis/release-please) and published to
PyPI by GitHub Actions:

- Commits to `master` use [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, ...). release-please opens and maintains a release PR with the
  next version and changelog.
- Merging that PR tags the release, which triggers a build (`uv build`) and
  publish (`uv publish`) to PyPI.
- The version is derived from the git tag by `hatch-vcs`, so it never needs to be
  edited by hand.

Publishing requires a `PYPI_TOKEN` repository secret. The release workflow can
also be run manually via *workflow_dispatch* to publish the latest tag.

## Status and roadmap

This first release is a faithful, modern core. The IR is designed so a future
FASM++ superset (macros, grouping, low-level bitstream hooks that compile down
to plain FASM) can be added without disturbing the existing data model.
