"""Edit existing FASM in place, preserving everything left untouched.

Run it:

    uv run python examples/02_edit.py

``edit(file)`` selects lines by prefix, name, predicate, or annotation, then
transforms only those. Comments, annotations, ordering, and unselected lines are
preserved byte for byte because the IR is format preserving.
"""

from fasm_toolkit import FasmBuilder, FasmLine, edit, parse_string

DESIGN = (
    "# power-on configuration\n"
    "TILE_X0Y0.LUT.INIT[15:0] = 16'hABCD\n"
    "TILE_X0Y0.MUX.OUT_SEL\n"
    "TILE_X1Y0.LUT.INIT[15:0] = 16'h1234\n"
    'TILE_X1Y0.MUX.OUT_SEL { net = "clk" }\n'
)


def main() -> str:
    """Run the edit demo and return the resulting FASM text."""
    file = parse_string(DESIGN)

    out = (
        edit(file)
        # Zero every LUT init in tile X0Y0 (format 16'h... is preserved).
        .select(prefix="TILE_X0Y0.LUT")
        .set_value(0)
        # Tag the clock mux so downstream tools can find it.
        .select(has_annotation="net")
        .add_annotation("reviewed", "yes")
        # Rename tile X1Y0 into a named block.
        .select(prefix="TILE_X1Y0")
        .rename(lambda name: name.replace("TILE_X1Y0", "BLOCK_A"))
        .commit()
    )

    # Structural insertion: drop a section header before the block. insert_before
    # is a chainable Selection method and takes a single line or an iterable.
    out = (
        edit(out)
        .select(name="BLOCK_A.LUT.INIT")
        .insert_before(FasmLine(comment=" --- block A ---"))
        .commit()
    )

    # Append a trailer built with the generation facade.
    trailer = FasmBuilder().comment(" end of configuration").build()
    out = edit(out).append(trailer).commit()

    return out.to_string()


if __name__ == "__main__":
    print(main(), end="")
