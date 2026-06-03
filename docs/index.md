# fasm-toolkit

A modern parser and manipulation toolkit for the FPGA Assembly (FASM) format.

The core parser is built on [Lark](https://github.com/lark-parser/lark), and all
manipulation happens on a small, typed intermediate representation (IR). Output is
byte-for-byte compatible with the reference
[`fasm`](https://github.com/chipsalliance/fasm) library.

## Pipeline

The library follows a `parse -> IR -> manipulate -> emit` flow.

```python
from fasm_toolkit import parse_string

fasm = parse_string("CLB.A[3:0] = 4'b1010")
print(fasm.to_string(canonical=True))  # CLB.A[1] / CLB.A[3], one bit per line
```

## Command line

```
fasm-toolkit format FILE         # reformat, preserving intent
fasm-toolkit canonicalize FILE   # canonical form, sorted and de-duplicated
fasm-toolkit merge FILE          # merge bit ranges and sort
fasm-toolkit parse FILE          # dump the IR for inspection
```

Add `-v` (info) or `-vv` (debug) to route logs to stderr; data always goes to
stdout so commands stay pipeable.

## FASM++ embedded DSL

Beyond parsing, the toolkit ships an embedded Python DSL for *writing* and
*editing* FASM. Macros are functions, repetition is a `for` loop, and an
optional layer maps features to a real bitstream. See the [cookbook](cookbook.md).

```python
from fasm_toolkit import FasmBuilder

b = FasmBuilder()
with b.scope("TILE_X0Y0"):
    b.set("LUT.INIT", 0xABCD, width=16)
print(b.build().to_string())  # TILE_X0Y0.LUT.INIT[15:0] = 16'hABCD
```

```{toctree}
:maxdepth: 2
:caption: Contents

cookbook
api
```
