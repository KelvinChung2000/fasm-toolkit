"""Exception hierarchy for fasm_toolkit.

Everything the library raises for bad input derives from :class:`FasmError`, so a
consumer (or the CLI) can catch one type and report it cleanly.
"""

__all__ = [
    "FasmError",
    "FasmSyntaxError",
    "FasmValidationError",
    "FasmMergeError",
    "FasmBuildError",
]


class FasmError(Exception):
    """Base class for all errors raised while parsing or transforming FASM."""


class FasmSyntaxError(FasmError):
    """Raised when the input does not conform to the FASM grammar."""


class FasmValidationError(FasmError):
    """Raised when input parses but breaks a semantic rule (e.g. a too-wide value)."""


class FasmMergeError(FasmError):
    """Raised when features cannot merge (e.g. a bit is both set and cleared)."""


class FasmBuildError(FasmError):
    """Raised when the eDSL builder or editor is misused.

    Covers invalid feature names, out-of-range addresses, and values that do not
    fit their declared width. There is no silent fallback: a bad authoring call
    fails loudly so the mistake is caught at build or commit time.
    """
