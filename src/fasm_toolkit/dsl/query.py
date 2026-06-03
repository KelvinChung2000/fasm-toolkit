"""Editing facade: select lines of an existing file and transform only those.

Editing is format preserving and functional. :func:`edit` wraps an immutable
:class:`~fasm_toolkit.ir.FasmFile` in an :class:`Editor`. :meth:`Editor.select`
returns a :class:`Selection`, a view of the matching line indices. Each
selection transform produces a brand new :class:`Editor` over a new file, with
only the selected lines changed and everything else, comments, annotations, and
ordering included, left exactly as it was.

::

    out = (
        edit(parse_file("design.fasm"))
        .select(prefix="TILE_X0Y0.LUT")
        .set_value(0)
        .commit()
    )
"""

from collections.abc import Callable, Iterable, Iterator
from dataclasses import replace

from loguru import logger

from fasm_toolkit.dsl.builder import (
    build_feature_value,
    check_value_fits,
    coerce_lines,
    default_value_format,
    validate_annotation_name,
    validate_feature_name,
)
from fasm_toolkit.emit import line_to_string
from fasm_toolkit.errors import FasmBuildError
from fasm_toolkit.ir import (
    Address,
    Annotation,
    FasmFile,
    FasmLine,
    SetFeature,
    ValueFormat,
)

__all__ = ["edit", "Editor", "Selection"]


def edit(file: FasmFile) -> "Editor":
    """Wrap an immutable :class:`FasmFile` in an :class:`Editor`."""
    return Editor(file)


def _matches(
    line: FasmLine,
    prefix: str | None,
    name: str | None,
    predicate: Callable[[FasmLine], bool] | None,
    has_annotation: str | None,
) -> bool:
    """Return whether ``line`` satisfies every supplied criterion (logical AND)."""
    if prefix is not None and (
        line.feature is None or not line.feature.name.startswith(prefix)
    ):
        return False
    if name is not None and (line.feature is None or line.feature.name != name):
        return False
    if has_annotation is not None and not any(
        a.name == has_annotation for a in line.annotations
    ):
        return False
    return predicate is None or predicate(line)


def _require_feature(line: FasmLine, op: str) -> SetFeature:
    if line.feature is None:
        raise FasmBuildError(
            f"{op} requires a feature line, but selected line "
            f"{line_to_string(line)!r} has none; narrow the selection "
            f"(e.g. with prefix= or name=)"
        )
    return line.feature


class Editor:
    """An immutable cursor over a :class:`FasmFile`.

    Every transform returns a new ``Editor``; the original is never mutated.
    Selections are tied to the editor they were created from, so re-select after
    a transform rather than reusing an old selection's indices.
    """

    def __init__(self, file: FasmFile) -> None:
        self._file = file

    @property
    def file(self) -> FasmFile:
        """The current immutable file."""
        return self._file

    def select(
        self,
        *,
        prefix: str | None = None,
        name: str | None = None,
        predicate: Callable[[FasmLine], bool] | None = None,
        has_annotation: str | None = None,
    ) -> "Selection":
        """Return a :class:`Selection` of lines matching all given criteria.

        ``prefix`` and ``name`` match against a line's feature name; ``predicate``
        is an arbitrary ``FasmLine -> bool``; ``has_annotation`` matches lines
        carrying an annotation of that name. With no criteria, every line
        matches.
        """
        indices = tuple(
            i
            for i, line in enumerate(self._file.lines)
            if _matches(line, prefix, name, predicate, has_annotation)
        )
        logger.debug("select: {} of {} line(s) matched", len(indices), len(self._file))
        return Selection(self, indices)

    # -- structural insertion --------------------------------------------

    def insert_before(
        self, selection: "Selection", lines: "FasmLine | Iterable[FasmLine]"
    ) -> "Editor":
        """Insert ``lines`` immediately before the first line of ``selection``.

        Prefer :meth:`Selection.insert_before`, which keeps the fluent chain.
        """
        self._require_own_selection(selection, "insert_before")
        new = coerce_lines(lines)
        if len(selection) == 0:
            raise FasmBuildError("insert_before: selection is empty, no anchor line")
        anchor = min(selection.indices)
        old = self._file.lines
        return Editor(FasmFile(old[:anchor] + new + old[anchor:]))

    def insert_after(
        self, selection: "Selection", lines: "FasmLine | Iterable[FasmLine]"
    ) -> "Editor":
        """Insert ``lines`` immediately after the last line of ``selection``.

        Prefer :meth:`Selection.insert_after`, which keeps the fluent chain.
        """
        self._require_own_selection(selection, "insert_after")
        new = coerce_lines(lines)
        if len(selection) == 0:
            raise FasmBuildError("insert_after: selection is empty, no anchor line")
        anchor = max(selection.indices) + 1
        old = self._file.lines
        return Editor(FasmFile(old[:anchor] + new + old[anchor:]))

    def append(self, lines: "FasmLine | Iterable[FasmLine]") -> "Editor":
        """Append a single line or an iterable of lines to the end of the file."""
        return Editor(FasmFile(self._file.lines + coerce_lines(lines)))

    def _require_own_selection(self, selection: "Selection", op: str) -> None:
        """Reject a selection whose indices index a different (or stale) file.

        Every transform returns a fresh ``Editor``, so a selection is only valid
        against the editor it was taken from; anchoring a foreign or stale
        selection's indices into this file would insert at the wrong place.
        """
        if selection.editor is not self:
            raise FasmBuildError(
                f"{op}: this selection was created from a different editor; "
                f"re-select on the editor you are inserting into (each transform "
                f"returns a new editor), or use Selection.{op}"
            )

    def commit(self) -> FasmFile:
        """Return the current immutable :class:`FasmFile`."""
        logger.debug("commit: {} line(s)", len(self._file))
        return self._file


class Selection:
    """A view of the line indices an :meth:`Editor.select` matched.

    Transforms build a new file with only those lines changed and return a new
    :class:`Editor`, so calls chain top to bottom. The selection itself is
    inspectable through ``len`` and iteration over the matched lines.
    """

    def __init__(self, editor: Editor, indices: tuple[int, ...]) -> None:
        self._editor = editor
        self._indices = indices
        self._index_set = frozenset(indices)

    def __len__(self) -> int:
        """Return the number of matched lines."""
        return len(self._indices)

    def __iter__(self) -> Iterator[FasmLine]:
        """Iterate over the matched lines."""
        lines = self._editor.file.lines
        return (lines[i] for i in self._indices)

    @property
    def indices(self) -> tuple[int, ...]:
        """The matched line indices, in file order."""
        return self._indices

    @property
    def editor(self) -> Editor:
        """The editor this selection was taken from (its indices index its file)."""
        return self._editor

    # -- transforms (each returns a new Editor) --------------------------

    def set_value(self, value: int, *, fmt: ValueFormat | None = None) -> Editor:
        """Replace the value on every selected feature line.

        The format is preserved from the existing value when the line already
        has one, otherwise the default (hex when addressed, plain decimal
        otherwise) applies. Pass ``fmt`` to force a format.
        """

        def transform(line: FasmLine) -> FasmLine:
            feature = _require_feature(line, "set_value")
            if fmt is not None:
                chosen = fmt
            elif feature.value is not None:
                chosen = feature.value.format
            else:
                chosen = default_value_format(feature.address)
            new_feature = replace(feature, value=build_feature_value(value, chosen))
            check_value_fits(new_feature)
            return replace(line, feature=new_feature)

        return self._apply(transform)

    def set_address(self, address: Address) -> Editor:
        """Replace the address on every selected feature line."""
        if not isinstance(address, Address):
            raise FasmBuildError(
                f"set_address expects an Address, got {type(address).__name__}"
            )

        def transform(line: FasmLine) -> FasmLine:
            feature = _require_feature(line, "set_address")
            new_feature = replace(feature, address=address)
            check_value_fits(new_feature)
            return replace(line, feature=new_feature)

        return self._apply(transform)

    def rename(self, fn: Callable[[str], str]) -> Editor:
        """Map every selected feature name through ``fn`` (validated on output)."""

        def transform(line: FasmLine) -> FasmLine:
            feature = _require_feature(line, "rename")
            new_name = validate_feature_name(fn(feature.name))
            return replace(line, feature=replace(feature, name=new_name))

        return self._apply(transform)

    def add_annotation(self, name: str, value: str) -> Editor:
        """Attach a ``name = "value"`` annotation to every selected line.

        ``name`` is validated against the grammar; ``value`` is the logical
        string (any quotes or backslashes are escaped on emit), but a newline is
        rejected since an annotation cannot span lines.
        """
        validate_annotation_name(name)
        if "\n" in value or "\r" in value:
            raise FasmBuildError("annotation value must not contain a newline")
        annotation = Annotation(name, value)

        def transform(line: FasmLine) -> FasmLine:
            return replace(line, annotations=line.annotations + (annotation,))

        return self._apply(transform)

    # -- structural insertion (anchored on this selection) ---------------

    def insert_before(self, lines: "FasmLine | Iterable[FasmLine]") -> Editor:
        """Insert ``lines`` immediately before this selection's first line."""
        return self._editor.insert_before(self, lines)

    def insert_after(self, lines: "FasmLine | Iterable[FasmLine]") -> Editor:
        """Insert ``lines`` immediately after this selection's last line."""
        return self._editor.insert_after(self, lines)

    def remove(self) -> Editor:
        """Drop every selected line, returning a new :class:`Editor`."""
        kept = tuple(
            line
            for i, line in enumerate(self._editor.file.lines)
            if i not in self._index_set
        )
        logger.debug("remove: dropped {} line(s)", len(self._index_set))
        return Editor(FasmFile(kept))

    def map(self, fn: Callable[[FasmLine], FasmLine]) -> Editor:
        """Apply an arbitrary ``FasmLine -> FasmLine`` to every selected line."""

        def transform(line: FasmLine) -> FasmLine:
            result = fn(line)
            if not isinstance(result, FasmLine):
                raise FasmBuildError(
                    f"map function must return a FasmLine, got {type(result).__name__}"
                )
            return result

        return self._apply(transform)

    # -- internals --------------------------------------------------------

    def _apply(self, transform: Callable[[FasmLine], FasmLine]) -> Editor:
        new_lines = tuple(
            transform(line) if i in self._index_set else line
            for i, line in enumerate(self._editor.file.lines)
        )
        return Editor(FasmFile(new_lines))
