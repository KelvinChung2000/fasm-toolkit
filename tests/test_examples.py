"""Run the example scripts and check their demonstrated behaviour holds.

Keeps the examples honest: if the eDSL surface changes in a way that breaks a
documented example, this fails.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from fasm_toolkit import parse_string

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


def _load(name: str) -> ModuleType:
    path = EXAMPLES_DIR / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generate_example_emits_parseable_fasm() -> None:
    text = _load("01_generate.py").main()
    # The generated text must re-parse (the round-trip invariant in practice).
    parsed = parse_string(text)
    assert parse_string(parsed.to_string()) == parsed
    assert "TILE_X1Y1.ROUTING.JUMP[3:0] = 4'b11" in text
    assert "TILE_X0Y0.MUX.OUT_SEL" in text


def test_edit_example_changes_only_intended_lines() -> None:
    text = _load("02_edit.py").main()
    assert "TILE_X0Y0.LUT.INIT[15:0] = 16'h0" in text  # zeroed, format preserved
    assert "BLOCK_A.LUT.INIT[15:0] = 16'h1234" in text  # renamed
    assert "TILE_X1Y0" not in text  # old name gone
    assert 'reviewed = "yes"' in text  # annotation added
    assert "# --- block A ---" in text  # inserted header
    assert "# end of configuration" in text  # appended trailer
    assert "# power-on configuration" in text  # original comment untouched


@pytest.mark.parametrize("name", ["01_generate.py", "02_edit.py"])
def test_example_main_returns_text(name: str) -> None:
    assert isinstance(_load(name).main(), str)
