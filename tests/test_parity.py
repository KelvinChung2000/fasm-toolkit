"""Cross-validate output against the reference ``fasm`` library.

These tests run the original library (found in a sibling ``../fasm`` checkout)
in its own virtualenv via a subprocess and compare its output to ours. They are
skipped automatically when that checkout or its environment is unavailable, so
the suite stays self-contained.
"""

import subprocess
from pathlib import Path

import pytest

from conftest import EXAMPLES, example
from fasm_toolkit import parse_file

_ORIGINAL_PYTHON = Path(__file__).resolve().parents[2] / "fasm" / ".venv" / "bin" / "python"

_SNIPPET = """
import sys
import fasm
import fasm.parser
canonical = sys.argv[2] == "1"
lines = list(fasm.parser.parse_fasm_filename(sys.argv[1]))
sys.stdout.write(fasm.fasm_tuple_to_string(lines, canonical=canonical))
"""


def _reference_output(path: Path, *, canonical: bool) -> str:
    if not _ORIGINAL_PYTHON.exists():
        pytest.skip(f"reference fasm interpreter not found at {_ORIGINAL_PYTHON}")
    proc = subprocess.run(
        [str(_ORIGINAL_PYTHON), "-c", _SNIPPET, str(path), "1" if canonical else "0"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        pytest.skip(f"reference fasm library failed to run: {proc.stderr.strip()}")
    return proc.stdout


@pytest.mark.parametrize("name", EXAMPLES)
def test_canonical_output_matches_reference(name):
    path = example(name)
    reference = _reference_output(path, canonical=True)
    ours = parse_file(path).to_string(canonical=True)
    assert ours == reference


@pytest.mark.parametrize("name", EXAMPLES)
def test_default_output_matches_reference(name):
    path = example(name)
    reference = _reference_output(path, canonical=False)
    ours = parse_file(path).to_string()
    assert ours == reference
