"""The FASM++ embedded DSL: generate and edit FASM with full Python power.

Two facades sit on top of the immutable IR:

* :class:`~fasm_toolkit.dsl.builder.FasmBuilder` generates FASM from scratch,
  with scoped dotted names, value formatting, and width validation.
* :func:`~fasm_toolkit.dsl.query.edit` edits an existing :class:`FasmFile` in
  place, selecting and transforming lines while preserving everything untouched.
"""

from fasm_toolkit.dsl.builder import FasmBuilder, bits
from fasm_toolkit.dsl.query import Editor, Selection, edit

__all__ = [
    "FasmBuilder",
    "bits",
    "edit",
    "Editor",
    "Selection",
]
