"""Command line interface for fasm-toolkit."""

import sys
from collections.abc import Callable
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

FileArg = Annotated[
    Path, typer.Argument(exists=True, dir_okay=False, help="FASM file to read.")
]
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


def _guard(operation: Callable[[], str]) -> str:
    """Run a pipeline, reporting any FasmError cleanly and exiting non-zero."""
    try:
        return operation()
    except FasmError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command(name="format")
def format_command(file: FileArg) -> None:
    """Reformat a FASM file (normalised whitespace, preserved intent)."""

    def run() -> str:
        fasm_file = parse_file(file)
        logger.info("Formatting {} ({} line(s))", file, len(fasm_file.lines))
        return fasm_file.to_string()

    typer.echo(_guard(run), nl=False)


@app.command()
def canonicalize(file: FileArg) -> None:
    """Emit the canonical form: one set bit per line, sorted and de-duplicated."""

    def run() -> str:
        fasm_file = parse_file(file)
        logger.info("Canonicalizing {}", file)
        return fasm_file.to_string(canonical=True)

    typer.echo(_guard(run), nl=False)


@app.command()
def merge(file: FileArg) -> None:
    """Group, merge bit ranges, and sort for tidy non-canonical output."""

    def run() -> str:
        fasm_file = parse_file(file)
        logger.info("Merging {}", file)
        return fasm_file.merged().to_string()

    typer.echo(_guard(run), nl=False)


@app.command()
def parse(file: FileArg) -> None:
    """Parse and print the IR (one line per FASM line) for inspection."""

    def run() -> str:
        fasm_file = parse_file(file)
        return "\n".join(repr(line) for line in fasm_file.lines)

    typer.echo(_guard(run))


if __name__ == "__main__":  # pragma: no cover
    app()
