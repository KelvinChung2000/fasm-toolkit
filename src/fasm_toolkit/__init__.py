r"""fasm-toolkit: a modern FPGA Assembly (FASM) parser and manipulation toolkit.

The pipeline is parse -> IR -> manipulate -> emit:

    >>> from fasm_toolkit import parse_string
    >>> file = parse_string("CLB.A[3:0] = 4'b1010")
    >>> file.to_string(canonical=True)
    'CLB.A[1]\\nCLB.A[3]\\n'

The IR (:mod:`fasm_toolkit.ir`) is a set of immutable dataclasses that preserve
value formats, annotations, and comments, so a parsed file round-trips back to
equal IR.
"""

from loguru import logger

from fasm_toolkit.dsl import (
    Editor,
    FasmBuilder,
    Selection,
    bits,
    edit,
)
from fasm_toolkit.emit import (
    feature_value_to_string,
    line_to_string,
    set_feature_to_string,
    to_string,
)
from fasm_toolkit.errors import (
    FasmBuildError,
    FasmError,
    FasmMergeError,
    FasmSyntaxError,
    FasmValidationError,
)
from fasm_toolkit.ir import (
    Address,
    Annotation,
    FasmFile,
    FasmLine,
    FeatureValue,
    SetFeature,
    ValueFormat,
)
from fasm_toolkit.parser import (
    parse_file,
    parse_string,
)
from fasm_toolkit.transform import (
    canonical_set_features,
    canonicalize,
    merge_and_sort,
    merge_features,
)

__all__ = [
    # IR
    "ValueFormat",
    "FeatureValue",
    "Address",
    "Annotation",
    "SetFeature",
    "FasmLine",
    "FasmFile",
    # parsing
    "parse_string",
    "parse_file",
    # errors
    "FasmError",
    "FasmSyntaxError",
    "FasmValidationError",
    "FasmMergeError",
    "FasmBuildError",
    # eDSL (FASM++)
    "FasmBuilder",
    "bits",
    "edit",
    "Editor",
    "Selection",
    # emit
    "to_string",
    "line_to_string",
    "set_feature_to_string",
    "feature_value_to_string",
    # transform
    "canonicalize",
    "canonical_set_features",
    "merge_features",
    "merge_and_sort",
]

# Follow loguru's guidance for libraries: stay silent unless the consuming
# application explicitly opts in with ``logger.enable("fasm_toolkit")``. The CLI
# enables it (see fasm_toolkit.cli).
logger.disable("fasm_toolkit")

try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _version

    __version__ = _version("fasm-toolkit")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"
