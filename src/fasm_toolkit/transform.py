"""Transformations over the IR.

* :func:`canonical_set_features` / :func:`canonicalize` expand features into the
  F4PGA canonical form (one set bit per line).
* :func:`merge_features` coalesces several addressed writes of one feature into a
  single bit vector.
* :func:`merge_and_sort` groups, merges, and sorts a whole file for tidy,
  non-canonical output.

The logic mirrors the reference ``fasm`` library so output matches bit for bit.
"""

import enum
from collections.abc import Callable, Iterator

from loguru import logger

from fasm_toolkit.emit import set_feature_to_string
from fasm_toolkit.ir import (
    Address,
    FasmFile,
    FasmLine,
    FeatureValue,
    SetFeature,
    ValueFormat,
)

__all__ = [
    "canonical_set_features",
    "canonicalize",
    "merge_features",
    "merge_and_sort",
]


def canonical_set_features(feature: SetFeature) -> Iterator[SetFeature]:
    """Yield canonical (width-one, value-one) features for a set feature.

    Cleared bits yield nothing; a feature whose whole value is zero yields
    nothing at all.
    """
    value = 1 if feature.value is None else feature.value.value
    if value == 0:
        return

    address = feature.address
    if address is None:
        yield SetFeature(feature.name)
        return

    if address.high is None:
        if address.low == 0:
            yield SetFeature(feature.name)
        else:
            yield SetFeature(feature.name, Address(address.low))
        return

    for bit in range(address.low, address.high + 1):
        if (value >> (bit - address.low)) & 1:
            if bit == 0:
                yield SetFeature(feature.name)
            else:
                yield SetFeature(feature.name, Address(bit))


def canonicalize(file: FasmFile) -> FasmFile:
    """Return the canonical form of ``file`` as a sorted, de-duplicated
    :class:`FasmFile` (comments and annotations are dropped)."""
    by_string: dict[str, SetFeature] = {}
    for feature in file.features():
        for canonical in canonical_set_features(feature):
            by_string[set_feature_to_string(canonical)] = canonical
    lines = tuple(FasmLine(feature=by_string[key]) for key in sorted(by_string))
    logger.debug("canonicalize: {} line(s) -> {} canonical feature(s)", len(file.lines), len(lines))
    return FasmFile(lines)


def merge_features(features: list[SetFeature]) -> SetFeature:
    """Combine writes to one feature with differing addresses into one feature.

    ``A[0] = 1`` and ``A[1] = 1`` become ``A[1:0] = 2'b11``.
    """
    names = {feature.name for feature in features}
    if len(names) != 1:
        raise ValueError(f"merge_features requires one feature name, got {names}")

    set_bits: set[int] = set()
    cleared_bits: set[int] = set()

    for feature in features:
        if feature.address is None:
            low = high = 0
        else:
            low = feature.address.low
            high = feature.address.high if feature.address.high is not None else low
        value = 1 if feature.value is None else feature.value.value

        for bit in range(low, high + 1):
            if (value >> (bit - low)) & 1:
                if bit in cleared_bits:
                    raise ValueError(f"bit {bit} of {feature.name} both set and cleared")
                set_bits.add(bit)
            else:
                if bit in set_bits:
                    raise ValueError(f"bit {bit} of {feature.name} both set and cleared")
                cleared_bits.add(bit)

    max_bit = max(set_bits | cleared_bits)
    final_value = 0
    for bit in set_bits:
        final_value |= 1 << bit

    return SetFeature(
        name=features[0].name,
        address=Address(low=0, high=max_bit),
        value=FeatureValue(final_value, ValueFormat.VERILOG_BINARY),
    )


def _is_only_comment(line: FasmLine) -> bool:
    return line.feature is None and not line.annotations and line.comment is not None


def _is_only_annotation(line: FasmLine) -> bool:
    return line.feature is None and bool(line.annotations) and line.comment is None


class _GroupState(enum.Enum):
    NO_GROUP = enum.auto()
    IN_COMMENT_GROUP = enum.auto()
    IN_ANNOTATION_GROUP = enum.auto()


class _MergeModel:
    """Groups and merges lines following the reference library's rules."""

    def __init__(self) -> None:
        self.state = _GroupState.NO_GROUP
        self.groups: list[list[FasmLine]] = []
        self.current_group: list[FasmLine] | None = None

    def _start_comment_group(self, line: FasmLine) -> None:
        if self.current_group is not None:
            self.groups.append(self.current_group)
        self.state = _GroupState.IN_COMMENT_GROUP
        self.current_group = [line]

    def _start_annotation_group(self, line: FasmLine) -> None:
        if self.current_group is not None:
            self.groups.append(self.current_group)
        self.state = _GroupState.IN_ANNOTATION_GROUP
        self.current_group = [line]

    def add(self, line: FasmLine) -> None:
        if self.state is _GroupState.NO_GROUP:
            if _is_only_comment(line):
                self._start_comment_group(line)
            elif _is_only_annotation(line):
                self._start_annotation_group(line)
            elif not line.is_blank:
                self.groups.append([line])
        elif self.state is _GroupState.IN_COMMENT_GROUP:
            assert self.current_group is not None
            if _is_only_comment(line):
                self.current_group.append(line)
            elif _is_only_annotation(line):
                self.current_group.append(line)
                self.state = _GroupState.IN_ANNOTATION_GROUP
            else:
                if not line.is_blank:
                    self.current_group.append(line)
                self.groups.append(self.current_group)
                self.current_group = None
                self.state = _GroupState.NO_GROUP
        else:  # IN_ANNOTATION_GROUP
            assert self.current_group is not None
            if _is_only_comment(line):
                self._start_comment_group(line)
            elif _is_only_annotation(line):
                self.current_group.append(line)
            else:
                self.groups.append(self.current_group)
                self.current_group = None
                self.state = _GroupState.NO_GROUP
                self.add(line)

    def finish(self) -> None:
        if self.state is not _GroupState.NO_GROUP and self.current_group is not None:
            self.groups.append(self.current_group)
            self.current_group = None

    def merge_addresses(self) -> None:
        def eligible_feature(group: list[FasmLine]) -> SetFeature | None:
            if len(group) > 1:
                return None
            only = group[0]
            if only.annotations or only.comment is not None:
                return None
            return only.feature

        eligible: dict[str, list[SetFeature]] = {}
        non_eligible_groups: list[list[FasmLine]] = []
        non_eligible_names: set[str] = set()

        for group in self.groups:
            feature = eligible_feature(group)
            if feature is None:
                non_eligible_groups.append(group)
                for line in group:
                    if line.feature is not None:
                        non_eligible_names.add(line.feature.name)
            else:
                eligible.setdefault(feature.name, []).append(feature)

        self.groups = non_eligible_groups

        for feature_group in eligible.values():
            name = feature_group[0].name
            if name in non_eligible_names:
                for feature in feature_group:
                    self.groups.append([FasmLine(feature=feature)])
            elif len(feature_group) > 1:
                self.groups.append([FasmLine(feature=merge_features(feature_group))])
            else:
                for feature in feature_group:
                    self.groups.append([FasmLine(feature=feature)])

    def sorted_lines(
        self,
        zero_function: Callable[[str], bool] | None,
        sort_key: Callable[[str], object] | None,
    ) -> list[FasmLine]:
        feature_groups: dict[str, list[list[FasmLine]]] = {}
        non_feature_groups: list[list[FasmLine]] = []

        for group in self.groups:
            for line in group:
                if line.feature is not None:
                    group_id = line.feature.name.split(".")[0]
                    feature_groups.setdefault(group_id, []).append(group)
                    break
            else:
                non_feature_groups.append(group)

        def feature_group_key(group: list[FasmLine]) -> str:
            for line in group:
                if line.feature is not None:
                    return line.feature.name
            raise AssertionError("feature group without a feature")

        if sort_key is None:
            group_ids = sorted(feature_groups)
        else:
            group_ids = sorted(feature_groups, key=sort_key)

        output_groups: list[list[FasmLine]] = []
        for group_id in group_ids:
            flattened: list[FasmLine] = []
            for group in sorted(feature_groups[group_id], key=feature_group_key):
                flattened.extend(group)
            if zero_function is not None and all(
                zero_function(line.feature.name)
                for line in flattened
                if line.feature is not None
            ):
                continue
            output_groups.append(flattened)

        output_groups.extend(non_feature_groups)

        result: list[FasmLine] = []
        for index, group in enumerate(output_groups):
            result.extend(group)
            if index != len(output_groups) - 1:
                result.append(FasmLine())  # blank separator line
        return result


def merge_and_sort(
    file: FasmFile,
    *,
    zero_function: Callable[[str], bool] | None = None,
    sort_key: Callable[[str], object] | None = None,
) -> FasmFile:
    """Group, merge bit ranges, and sort a file for tidy non-canonical output.

    Grouping rules (from the reference library):

    * Consecutive comments group together and attach to the next entry.
    * Consecutive annotations group together.
    * Blank lines are discarded.
    * Features group by their first dotted part; same-feature writes with
      different addresses are merged unless a comment makes them ineligible.
    """
    model = _MergeModel()
    for line in file.lines:
        model.add(line)
    model.finish()
    model.merge_addresses()
    result = FasmFile(tuple(model.sorted_lines(zero_function, sort_key)))
    logger.debug("merge_and_sort: {} line(s) -> {} line(s)", len(file.lines), len(result.lines))
    return result
