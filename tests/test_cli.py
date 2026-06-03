"""CLI behaviour via Typer's test runner."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

import fasm_toolkit.cli as cli_module
from fasm_toolkit.cli import app
from fasm_toolkit.parser import FasmValidationError

runner = CliRunner()


def _write(tmp_path: Path, text: str) -> Path:
    file = tmp_path / "in.fasm"
    file.write_text(text)
    return file


def test_format_command(tmp_path):
    file = _write(tmp_path, "a[3:0]   =   4'b1010\n")
    result = runner.invoke(app, ["format", str(file)])
    assert result.exit_code == 0
    assert result.stdout == "a[3:0] = 4'b1010\n"


def test_canonicalize_command(tmp_path):
    file = _write(tmp_path, "a[3:0] = 4'b1010\n")
    result = runner.invoke(app, ["canonicalize", str(file)])
    assert result.exit_code == 0
    assert result.stdout == "a[1]\na[3]\n"


def test_merge_command(tmp_path):
    file = _write(tmp_path, "a[0] = 1\na[1] = 1\n")
    result = runner.invoke(app, ["merge", str(file)])
    assert result.exit_code == 0
    assert result.stdout == "a[1:0] = 2'b11\n"


def test_parse_command_dumps_ir(tmp_path):
    file = _write(tmp_path, "feat\n")
    result = runner.invoke(app, ["parse", str(file)])
    assert result.exit_code == 0
    assert "SetFeature" in result.stdout


def test_missing_file_is_an_error():
    result = runner.invoke(app, ["format", "/no/such/file.fasm"])
    assert result.exit_code != 0


def test_parse_error_reports_and_exits_nonzero(tmp_path, mocker):
    file = _write(tmp_path, "feat\n")
    mocker.patch.object(
        cli_module,
        "parse_file",
        side_effect=FasmValidationError("boom"),
    )
    result = runner.invoke(app, ["format", str(file)])
    assert result.exit_code == 1
    assert "boom" in result.output
