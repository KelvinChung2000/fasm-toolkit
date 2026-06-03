"""Round-trip idempotency: parse(emit(parse(x))) == parse(x)."""

import pytest
from conftest import EXAMPLES, example

from fasm_toolkit import parse_file, parse_string

ROUND_TRIP_CASES = [
    "feat",
    "feat = 1",
    "feat = 0",
    "a.b.c.INIT[17]",
    "a.b.c.INIT[17:17] = 1'b1",
    "a[0:0] = 1'b0",
    "a[31:0] = 32'hDEADBEEF",
    "a[7:0] = 8'b10101010",
    "a[7:0] = 8'o52",
    "a[7:0] = 8'd42",
    "a[7:0] = 42",
    'feat { module = "top", file = "/a/b.txt", line_number = "123" }',
    '{ .top_module = "/a/b/c/d.txt" }',
    'feat { .attr = "" } # comment',
    "# just a comment",
]


@pytest.mark.parametrize("text", ROUND_TRIP_CASES)
def test_string_round_trip(text: str) -> None:
    once = parse_string(text)
    twice = parse_string(once.to_string())
    assert once.lines == twice.lines


@pytest.mark.parametrize("name", EXAMPLES)
def test_example_round_trip(name: str) -> None:
    once = parse_file(example(name))
    twice = parse_string(once.to_string())
    assert once.lines == twice.lines


@pytest.mark.parametrize("name", EXAMPLES)
def test_example_canonical_round_trip(name: str) -> None:
    """Canonical output is itself valid FASM and is canonical-stable."""
    file = parse_file(example(name))
    canonical_text = file.to_string(canonical=True)
    reparsed = parse_string(canonical_text)
    assert reparsed.to_string(canonical=True) == canonical_text
