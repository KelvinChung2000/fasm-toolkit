"""Command line interface for fasm-toolkit."""

import sys
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger

from fasm_toolkit.parser import FasmError, parse_file

app = typer.Typer(
    add_completion=False,
    help="Parse and manipulate FPGA Assembly (FASM) files.",
    no_args_is_help=True,
)

FileArg = Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="FASM file to read.")]
VerboseOpt = Annotated[
    int,
    typer.Option(
        "--verbose",
        "-v",
        count=True,
        help="Increase log verbosity to stderr (-v for info, -vv for debug).",
    ),
]

_LOG_LEVELS = {0: "WARNING", 1: "INFO"}


def _configure_logging(verbose: int) -> None:
    """Route library logging to stderr at a level chosen by ``--verbose``."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=_LOG_LEVELS.get(verbose, "DEBUG"),
        format="<level>{level: <8}</level> | {message}",
    )
    logger.enable("fasm_toolkit")


@app.callback()
def main(verbose: VerboseOpt = 0) -> None:
    """Parse and manipulate FPGA Assembly (FASM) files."""
    _configure_logging(verbose)


def _parse_or_exit(file: Path):
    try:
        return parse_file(file)
    except FasmError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def format(file: FileArg) -> None:
    """Reformat a FASM file (normalised whitespace, preserved intent)."""
    fasm_file = _parse_or_exit(file)
    logger.info("Formatting {} ({} line(s))", file, len(fasm_file.lines))
    typer.echo(fasm_file.to_string(), nl=False)


@app.command()
def canonicalize(file: FileArg) -> None:
    """Emit the canonical form: one set bit per line, sorted and de-duplicated."""
    fasm_file = _parse_or_exit(file)
    logger.info("Canonicalizing {}", file)
    typer.echo(fasm_file.to_string(canonical=True), nl=False)


@app.command()
def merge(file: FileArg) -> None:
    """Group, merge bit ranges, and sort for tidy non-canonical output."""
    fasm_file = _parse_or_exit(file)
    logger.info("Merging {}", file)
    typer.echo(fasm_file.merged().to_string(), nl=False)


@app.command()
def parse(file: FileArg) -> None:
    """Parse and print the IR (one line per FASM line) for inspection."""
    fasm_file = _parse_or_exit(file)
    for line in fasm_file.lines:
        typer.echo(repr(line))


if __name__ == "__main__":  # pragma: no cover
    app()
