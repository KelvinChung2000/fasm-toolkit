# FASM++ eDSL cookbook

FASM++ is an embedded Python DSL for writing and editing FASM. There is no new
text grammar to learn. A macro is a Python function, repetition is a `for` loop,
and modularity is a plain `import`. Everything produces or consumes the same
immutable IR the parser produces, so the emit and transform layers work
unchanged.

The runnable versions of every snippet below live in the `examples/` directory:

```
uv run python examples/01_generate.py
uv run python examples/02_edit.py
```

## Generate

`FasmBuilder` accumulates feature lines, then `build()` freezes them into an
immutable `FasmFile`. `scope()` supplies the one thing Python lacks, ergonomic
nesting of dotted feature names.

```python
from fasm_toolkit import FasmBuilder, bits

def configure_lut(b: FasmBuilder, init: int) -> None:   # a macro is just a function
    b.set("LUT.INIT", init, width=16)
    with b.scope("MUX"):
        b.enable("OUT_SEL")

b = FasmBuilder()
for x in range(2):
    for y in range(2):                                  # repetition is a plain loop
        with b.scope(f"TILE_X{x}Y{y}"):
            configure_lut(b, 0xABCD)

print(b.build().to_string())
```

Addressing and value formats:

- `width=N` is shorthand for the range `[N-1:0]`.
- `at=` takes a single bit (`int`) or a range (`Address`, via `bits(high, low)`).
- A value with an address defaults to hex; a bare value defaults to plain
  decimal. Pass `fmt=` to override.

```python
b.set("LUT.INIT", 0xABCD, width=16)            # LUT.INIT[15:0] = 16'hABCD
b.set("CFG", 5, at=bits(3, 0))                 # CFG[3:0] = 4'h5
b.enable("MUX.SEL0")                           # MUX.SEL0  (implicit one)
b.clear("CFG", at=2)                           # CFG[2] = 1'h0  (explicit zero)
```

Anything the builder produces re-parses to equal IR, so the round trip holds:

```python
from fasm_toolkit import parse_string

file = b.build()
assert parse_string(file.to_string()) == file
```

## Edit

`edit(file)` selects lines and transforms only those. Everything not selected,
comments, annotations, and ordering included, is preserved, because the IR is
format preserving. Each transform returns a new `Editor`, so calls chain top to
bottom.

```python
from fasm_toolkit import edit, parse_file

out = (
    edit(parse_file("design.fasm"))
      .select(prefix="TILE_X0Y0.LUT")   # match by feature-name prefix
      .set_value(0)                       # 16'hABCD becomes 16'h0, format kept
      .select(has_annotation="net")      # match by annotation name
      .add_annotation("reviewed", "yes")
      .commit()                           # new FasmFile, untouched lines intact
)
```

Selections match by `prefix`, exact `name`, an arbitrary `predicate`, or
`has_annotation`. The available transforms are `set_value`, `set_address`,
`rename`, `add_annotation`, `remove`, and `map`. Structural insertion is on the
`Editor`: `insert_before`, `insert_after`, and `append`.

```python
editor = edit(file)
header = editor.select(name="BLOCK_A.LUT.INIT")
out = editor.insert_before(header, (FasmLine(comment=" --- block A ---"),)).commit()
```
