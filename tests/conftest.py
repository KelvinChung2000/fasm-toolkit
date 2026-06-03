"""Shared test fixtures."""

from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent / "data"
EXAMPLES = ["blank.fasm", "comment.fasm", "feature_only.fasm", "many.fasm"]


@pytest.fixture
def data_dir() -> Path:
    return DATA_DIR


def example(name: str) -> Path:
    return DATA_DIR / name
