"""Logging behaviour (loguru integration)."""

import io
import sys
from pathlib import Path

import pytest
from loguru import logger
from typer.testing import CliRunner

import fasm_toolkit.cli as cli_module
from fasm_toolkit import parse_string
from fasm_toolkit.cli import app

runner = CliRunner()


def test_library_is_silent_when_disabled() -> None:
    """Per loguru's library convention, fasm_toolkit logs nothing until enabled."""
    logger.disable("fasm_toolkit")
    records: list[str] = []
    sink_id = logger.add(records.append, level="DEBUG")
    try:
        parse_string("a.b.c = 1")
    finally:
        logger.remove(sink_id)
    assert records == []


def test_library_logs_when_enabled() -> None:
    records: list[str] = []
    sink_id = logger.add(records.append, level="DEBUG")
    logger.enable("fasm_toolkit")
    try:
        parse_string("a.b.c = 1")
    finally:
        logger.remove(sink_id)
        logger.disable("fasm_toolkit")
    assert any("Parsed" in record for record in records)


def test_configure_logging_debug_writes_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buffer)
    cli_module._configure_logging(2)  # -vv => DEBUG  # noqa: SLF001
    try:
        parse_string("a = 1")
    finally:
        logger.remove()
        logger.disable("fasm_toolkit")
    assert "Parsed" in buffer.getvalue()


def test_configure_logging_default_suppresses_debug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buffer)
    cli_module._configure_logging(0)  # default => WARNING  # noqa: SLF001
    try:
        parse_string("a = 1")  # only emits debug-level logs
    finally:
        logger.remove()
        logger.disable("fasm_toolkit")
    assert buffer.getvalue() == ""


def test_verbose_flag_keeps_stdout_clean(tmp_path: Path) -> None:
    file = tmp_path / "in.fasm"
    file.write_text("a[3:0] = 4'b1010\n")
    result = runner.invoke(app, ["-vv", "canonicalize", str(file)])
    assert result.exit_code == 0
    assert result.stdout == "a[1]\na[3]\n"
