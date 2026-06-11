"""
Core matching functions for dataset-matcher.

See DESIGN.md in the repository root for the rationale behind the filename rule,
the supported layouts, and the reporting model.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence, Union

from .exceptions import (
    DatasetError,
    IdenticalDatasetError,
    UnmatchedFileError,
    AmbiguousMatchError,
    EmptyDatasetError,
)


# ---------------------------------------------------------------------------
# Known file-type endings (the allowlist described in DESIGN.md section 3)
# ---------------------------------------------------------------------------

# Multi-part endings (more than one dot). These are checked before single
# endings, longest first, so that e.g. ".seg.nrrd" wins over ".nrrd".
DEFAULT_COMPOUND_EXTENSIONS = (
    ".nii.gz",       # NIfTI, compressed
    ".mrk.json",     # Slicer markups (current)
    ".mrk.fcsv",     # Slicer markups (legacy variant)
    ".seg.nrrd",     # Slicer segmentation
    ".seg.nhdr",     # Slicer segmentation (detached header)
    ".tar.gz",       # archives
    ".tar.bz2",
    ".tar.xz",
)

# Single-part endings.
DEFAULT_KNOWN_EXTENSIONS = frozenset({
    # Medical imaging
    ".nii", ".nrrd", ".nhdr", ".mha", ".mhd", ".dcm", ".dicom",
    ".mgz", ".mnc", ".img", ".hdr", ".gipl",
    # Slicer markups, transforms, scenes, color tables
    ".fcsv", ".mrk", ".json", ".mrml", ".ctbl", ".h5", ".tfm", ".mat",
    # Meshes and models
    ".ply", ".stl", ".obj", ".vtk", ".vtp", ".vtu", ".vtm",
    ".off", ".gltf", ".glb", ".gii",
    # Common data / text
    ".txt", ".csv", ".tsv", ".xml",
    # Images
    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".tga",
    # Single-part archives
    ".gz", ".zip", ".bz2", ".xz",
})


# A key source: None (use the basename), a regex (str or compiled pattern), or a
# callable mapping a path to an identifier string (or None if it has none).
KeySource = Union[None, str, "re.Pattern", Callable[[str], Optional[str]]]


def _split_extra_extensions(extra):
    """Split caller-supplied extra endings into (compound tuple, single set)."""
    compounds = []
    singles = set()
    for ext in extra or ():
        e = ext.lower()
        if not e.startswith("."):
            e = "." + e
        if e.count(".") > 1:
            compounds.append(e)
        else:
            singles.add(e)
    return tuple(compounds), singles


def get_basename(path, extensions=None):
    """
    Reduce a path to its matchable basename.

    Strips exactly one recognized file-type ending (a multi-part ending such as
    ``.nii.gz`` if present, otherwise a single ending such as ``.ply``). Any dot
    that is not part of a recognized ending is treated as an ordinary character
    of the name, not an extension separator.

    Args:
        path: File path (absolute or relative).
        extensions: Optional extra endings to recognize, in addition to the
            built-in allowlist (e.g. ``[".am", ".foo.bar"]``). Endings with more
            than one dot are treated as multi-part.

    Returns:
        The filename with one recognized ending removed, or the filename
        unchanged if it has no recognized ending.

    Examples:
        >>> get_basename("/path/to/specimen_001.nii.gz")
        'specimen_001'
        >>> get_basename("AJ.mouse.nii.gz")
        'AJ.mouse'
        >>> get_basename("mouse.skull.nrrd")
        'mouse.skull'
        >>> get_basename("notes.unknownext")
        'notes.unknownext'
    """
    filename = os.path.basename(path)
    lower_filename = filename.lower()

    extra_compound, extra_single = _split_extra_extensions(extensions)

    # Longest compound ending first, so the most specific one wins.
    compounds = sorted(
        set(DEFAULT_COMPOUND_EXTENSIONS) | set(extra_compound),
        key=len,
        reverse=True,
    )
    for compound_ext in compounds:
        if lower_filename.endswith(compound_ext) and len(filename) > len(compound_ext):
            return filename[:-len(compound_ext)]

    if "." in filename:
        base, ext = os.path.splitext(filename)
        if ext.lower() in DEFAULT_KNOWN_EXTENSIONS or ext.lower() in extra_single:
            return base

    return filename


# ---------------------------------------------------------------------------
# Key resolution (DESIGN.md section 7, item 3)
# ---------------------------------------------------------------------------

def _make_key_func(key, extensions):
    """
    Build a function mapping a path to its raw match key (or None).

    ``key`` may be None (use the basename), a regex string / compiled pattern
    (the first capture group, or the whole match, becomes the key), or a
    callable taking the path and returning the key.
    """
    if key is None:
        return lambda path: get_basename(path, extensions=extensions)

    if isinstance(key, (str, re.Pattern)):
        pattern = re.compile(key) if isinstance(key, str) else key

        def regex_key(path):
            match = pattern.search(os.path.basename(path))
            if match is None:
                return None
            if match.groups():
                return match.group(1)
            return match.group(0)

        return regex_key

    if callable(key):
        return key

    raise TypeError(
        "key must be None, a regular expression (str or compiled pattern), "
        "or a callable taking a path"
    )


def _normalize(value, case_insensitive):
    if value is None:
        return None
    return value.lower() if case_insensitive else value


# ---------------------------------------------------------------------------
# Report data structures (DESIGN.md section 6)
# ---------------------------------------------------------------------------

@dataclass
class AmbiguousMatch:
    """A key that could not be resolved to a single pair."""
    key: str
    primary: Optional[str]
    candidates: list


@dataclass
class MatchReport:
    """
    The result of matching two file lists, without raising on problems.

    Attributes:
        pairs: List of (primary_path, secondary_path) tuples, in primary order.
        ordered_secondary: The secondary list reordered to align with primary;
            positions with no match hold None.
        missing: Primary paths with no secondary partner.
        orphans: Secondary paths with no primary partner.
        ambiguous: AmbiguousMatch entries (a key matching more than one file).
        primary_files / secondary_files: The input lists, for reference.
        name: Optional label for the secondary dataset.
    """
    pairs: list = field(default_factory=list)
    ordered_secondary: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    orphans: list = field(default_factory=list)
    ambiguous: list = field(default_factory=list)
    primary_files: list = field(default_factory=list)
    secondary_files: list = field(default_factory=list)
    name: Optional[str] = None

    @property
    def is_complete(self):
        """True when every file matched exactly one partner, both directions."""
        return not self.missing and not self.orphans and not self.ambiguous

    @property
    def matched_primary(self):
        return [primary for primary, _ in self.pairs]

    @property
    def matched_secondary(self):
        return [secondary for _, secondary in self.pairs]

    def summary(self):
        """A short human-readable description, suitable for display to a user."""
        label = " '{0}'".format(self.name) if self.name else ""
        lines = [
            "Matched {0} pair(s){1}.".format(len(self.pairs), label),
        ]
        if self.missing:
            lines.append(
                "{0} file(s) with no match: {1}".format(
                    len(self.missing),
                    ", ".join(os.path.basename(p) for p in self.missing),
                )
            )
        if self.orphans:
            lines.append(
                "{0} unmatched extra file(s): {1}".format(
                    len(self.orphans),
                    ", ".join(os.path.basename(p) for p in self.orphans),
                )
            )
        if self.ambiguous:
            lines.append(
                "{0} ambiguous name(s): {1}".format(
                    len(self.ambiguous),
                    ", ".join(a.key for a in self.ambiguous),
                )
            )
        if self.is_complete:
            lines.append("All files matched cleanly.")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Matching engine
# ---------------------------------------------------------------------------

@dataclass
class _EngineResult:
    pairs: list
    ordered_secondary: list
    missing: list
    orphans: list
    ambiguous: list
    duplicate_secondary: dict


def _index_secondary(secondary, key_func, case_insensitive):
    """Map normalized key -> path; collect duplicate keys and unmatchable paths."""
    index = {}
    raw_by_norm = {}
    duplicates = {}
    unmatchable = []
    for path in secondary:
        raw = key_func(path)
        if raw is None:
            unmatchable.append(path)
            continue
        norm = _normalize(raw, case_insensitive)
        if norm in index:
            duplicates.setdefault(norm, [index[norm]])
            duplicates[norm].append(path)
        else:
            index[norm] = path
            raw_by_norm[norm] = raw
    return index, raw_by_norm, duplicates, unmatchable


def _run_match(primary, secondary, key_func, case_insensitive, substring):
    index, raw_by_norm, duplicates, unmatchable = _index_secondary(
        secondary, key_func, case_insensitive
    )
    # Keys that appear more than once cannot be used for a confident pairing.
    usable = {k: v for k, v in index.items() if k not in duplicates}

    pairs = []
    ordered = []
    missing = []
    ambiguous = []
    used = set()

    for primary_path in primary:
        raw = key_func(primary_path)
        norm = _normalize(raw, case_insensitive)

        if norm is None:
            ordered.append(None)
            missing.append(primary_path)
            continue

        matched_path = None

        if not substring:
            if norm in duplicates:
                ambiguous.append(AmbiguousMatch(raw, primary_path, list(duplicates[norm])))
                ordered.append(None)
                continue
            matched_path = usable.get(norm)
        else:
            candidates = [
                path
                for skey, path in usable.items()
                if norm in skey or skey in norm
            ]
            if len(candidates) == 1:
                matched_path = candidates[0]
            elif len(candidates) > 1:
                ambiguous.append(AmbiguousMatch(raw, primary_path, candidates))
                ordered.append(None)
                continue

        if matched_path is None:
            ordered.append(None)
            missing.append(primary_path)
        else:
            ordered.append(matched_path)
            pairs.append((primary_path, matched_path))
            used.add(matched_path)

    ambiguous_paths = set()
    for group in duplicates.values():
        ambiguous_paths.update(group)

    orphans = [
        path
        for path in secondary
        if path not in used and path not in ambiguous_paths
    ]

    # Record duplicate-secondary keys that no primary referenced, so the report
    # still surfaces them.
    reported_keys = {a.key for a in ambiguous}
    for norm, group in duplicates.items():
        raw = raw_by_norm.get(norm, norm)
        if raw not in reported_keys:
            ambiguous.append(AmbiguousMatch(raw, None, list(group)))

    return _EngineResult(pairs, ordered, missing, orphans, ambiguous, duplicates)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def match_report(
    primary,
    secondary,
    *,
    key=None,
    extensions=None,
    case_insensitive=False,
    strategy="exact",
    name=None,
):
    """
    Match two file lists and return a MatchReport without raising on problems.

    Use this when you want to inspect or display the outcome (matched, missing,
    extra, ambiguous) before acting -- for example, to show a user a table and
    let them choose to proceed.

    Args:
        primary: Reference list of file paths.
        secondary: List of file paths to align with ``primary``.
        key: How to derive the match identifier from a filename. None uses the
            basename rule (see :func:`get_basename`); a regex or callable
            overrides it (DESIGN.md section 7).
        extensions: Extra file-type endings to recognize, beyond the built-ins.
        case_insensitive: If True, match identifiers ignoring letter case.
        strategy: "exact" (default) or "substring" (legacy partial matching).
        name: Optional label for the secondary dataset, used in the summary.

    Returns:
        A :class:`MatchReport`.
    """
    key_func = _make_key_func(key, extensions)
    result = _run_match(
        list(primary), list(secondary), key_func, case_insensitive,
        substring=(strategy == "substring"),
    )
    return MatchReport(
        pairs=result.pairs,
        ordered_secondary=result.ordered_secondary,
        missing=result.missing,
        orphans=result.orphans,
        ambiguous=result.ambiguous,
        primary_files=list(primary),
        secondary_files=list(secondary),
        name=name,
    )


def match_datasets(
    primary,
    secondary,
    *,
    strategy="exact",
    key=None,
    extensions=None,
    case_insensitive=False,
    name=None,
    allow_missing=False,
):
    """
    Match files in ``secondary`` to files in ``primary`` by their basename.

    Reorders ``secondary`` so that each entry corresponds to the entry at the
    same index in ``primary``. Raises on problems; for a non-raising version
    that reports problems instead, use :func:`match_report`.

    Args:
        primary: Reference list of file paths.
        secondary: List of file paths to align with ``primary``.
        strategy: "exact" (default) or "substring".
        key: Optional identifier rule (regex or callable); overrides the
            basename rule.
        extensions: Extra file-type endings to recognize.
        case_insensitive: If True, match ignoring letter case.
        name: Optional label for the secondary dataset (used in error messages).
        allow_missing: If True, unmatched positions are returned as None instead
            of raising.

    Returns:
        ``secondary`` reordered to align with ``primary`` (with None in
        unmatched positions when ``allow_missing`` is True).

    Raises:
        EmptyDatasetError, UnmatchedFileError, AmbiguousMatchError,
        IdenticalDatasetError.
    """
    primary = list(primary)
    secondary = list(secondary)

    if not primary:
        raise EmptyDatasetError("Primary dataset is empty", dataset_name="primary")

    if not secondary:
        raise EmptyDatasetError(
            "Secondary dataset{0} is empty".format(" ({0})".format(name) if name else ""),
            dataset_name=name or "secondary",
        )

    if set(primary) == set(secondary):
        dataset_desc = " ({0})".format(name) if name else ""
        raise IdenticalDatasetError(
            "Primary and secondary{0} datasets are identical. "
            "This may indicate the same files were selected for both inputs.".format(dataset_desc),
            dataset_name=name,
        )

    key_func = _make_key_func(key, extensions)
    result = _run_match(
        primary, secondary, key_func, case_insensitive,
        substring=(strategy == "substring"),
    )

    # Preserve historical behavior: any duplicate key in secondary is an error.
    if result.duplicate_secondary:
        norm, group = next(iter(result.duplicate_secondary.items()))
        raise AmbiguousMatchError(
            "Ambiguous match: identifier '{0}' matches multiple files: {1}".format(
                norm, " and ".join("'{0}'".format(p) for p in group)
            ),
            basename=norm,
            matches=list(group),
        )

    if result.ambiguous:
        amb = result.ambiguous[0]
        raise AmbiguousMatchError(
            "Ambiguous match for '{0}': {1}".format(
                amb.key, [os.path.basename(c) for c in amb.candidates]
            ),
            basename=amb.key,
            matches=list(amb.candidates),
        )

    if result.missing and not allow_missing:
        unmatched = [
            (key_func(p) or os.path.basename(p)) for p in result.missing
        ]
        dataset_desc = "'{0}'".format(name) if name else "secondary dataset"
        raise UnmatchedFileError(
            "No matching files in {0} for: {1}".format(dataset_desc, ", ".join(unmatched)),
            unmatched=unmatched,
            dataset_name=name,
        )

    return result.ordered_secondary


def match_multiple(
    *datasets,
    names=None,
    strategy="exact",
    key=None,
    extensions=None,
    case_insensitive=False,
    allow_missing=False,
):
    """
    Match multiple datasets against the first one.

    The first dataset is the reference; all others are reordered to align with
    it. See :func:`match_datasets` for the keyword arguments.

    Returns:
        A tuple of lists: the first unchanged, the rest reordered to match.
    """
    if len(datasets) < 2:
        raise ValueError("At least 2 datasets are required for matching")

    if names is not None and len(names) != len(datasets):
        raise ValueError(
            "Number of names ({0}) must match number of datasets ({1})".format(
                len(names), len(datasets)
            )
        )

    primary = list(datasets[0])
    results = [primary]

    for i, secondary in enumerate(datasets[1:], start=1):
        name = names[i] if names else None
        matched = match_datasets(
            primary,
            secondary,
            strategy=strategy,
            key=key,
            extensions=extensions,
            case_insensitive=case_insensitive,
            name=name,
            allow_missing=allow_missing,
        )
        results.append(matched)

    return tuple(results)


# ---------------------------------------------------------------------------
# Directory helpers
# ---------------------------------------------------------------------------

def _natural_sort_key(name):
    """Sort key so that embedded numbers order as humans expect (2 before 10)."""
    parts = re.split(r"(\d+)", name)
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def list_files(
    directory,
    extensions=None,
    recursive=False,
    *,
    natural=False,
    skip_hidden=True,
    case_insensitive_sort=False,
):
    """
    List files in a directory, optionally filtering by ending.

    Args:
        directory: Path to the directory.
        extensions: Endings to include (e.g. ``[".nii.gz", ".nrrd"]``), with the
            leading dot. None includes all files.
        recursive: If True, descend into subdirectories.
        natural: If True, sort so embedded numbers order naturally (2 before 10).
        skip_hidden: If True (default), skip dotfiles such as ``.DS_Store``.
        case_insensitive_sort: If True, sort ignoring letter case (ignored when
            ``natural`` is True, which already folds case).

    Returns:
        A sorted list of file paths.

    Raises:
        DatasetError: If the directory does not exist.
    """
    if not os.path.isdir(directory):
        raise DatasetError("Directory does not exist: {0}".format(directory))

    norm_exts = [ext.lower() for ext in extensions] if extensions else None

    def keep(filename):
        if skip_hidden and filename.startswith("."):
            return False
        if norm_exts is None:
            return True
        lower_name = filename.lower()
        return any(lower_name.endswith(ext) for ext in norm_exts)

    files = []
    if recursive:
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                if keep(filename):
                    files.append(os.path.join(root, filename))
    else:
        for entry in os.listdir(directory):
            path = os.path.join(directory, entry)
            if os.path.isfile(path) and keep(entry):
                files.append(path)

    if natural:
        files.sort(key=lambda p: _natural_sort_key(os.path.basename(p)))
    elif case_insensitive_sort:
        files.sort(key=lambda p: p.lower())
    else:
        files.sort()

    return files


def match_directories(
    primary_dir,
    secondary_dir,
    primary_extensions,
    secondary_extensions,
    *,
    key=None,
    extensions=None,
    case_insensitive=False,
    strategy="exact",
    recursive=False,
    natural=True,
    skip_hidden=True,
    names=None,
):
    """
    List two directories (or two file types in one directory) and match them.

    This is the convenience entry point most callers want: it lists the files,
    then matches them by basename, returning a :class:`MatchReport`.

    To match two file types that live in the *same* folder, pass the same path
    for both directories (or None for ``secondary_dir``); the two extension
    lists must then be disjoint.

    Args:
        primary_dir: Directory holding the reference dataset.
        secondary_dir: Directory holding the dataset to align (None means use
            ``primary_dir`` -- the two-types-in-one-folder layout).
        primary_extensions: Endings that select the primary files.
        secondary_extensions: Endings that select the secondary files.
        key, extensions, case_insensitive, strategy: As in :func:`match_report`.
        recursive: Passed to :func:`list_files`.
        natural: Use natural-number sorting when listing (default True).
        skip_hidden: Skip dotfiles when listing (default True).
        names: Optional (primary_name, secondary_name) pair for the report.

    Returns:
        A :class:`MatchReport`.

    Raises:
        DatasetError: If a directory is missing, or if the two extension lists
            overlap while matching within a single directory.
    """
    if secondary_dir is None:
        secondary_dir = primary_dir

    same_dir = os.path.normpath(primary_dir) == os.path.normpath(secondary_dir)
    if same_dir:
        overlap = {e.lower() for e in primary_extensions} & {
            e.lower() for e in secondary_extensions
        }
        if overlap:
            raise DatasetError(
                "When matching within one directory, the two extension lists "
                "must not overlap; shared endings: {0}".format(sorted(overlap))
            )

    primary_files = list_files(
        primary_dir, primary_extensions, recursive=recursive,
        natural=natural, skip_hidden=skip_hidden,
    )
    secondary_files = list_files(
        secondary_dir, secondary_extensions, recursive=recursive,
        natural=natural, skip_hidden=skip_hidden,
    )

    secondary_name = names[1] if names and len(names) > 1 else None
    return match_report(
        primary_files,
        secondary_files,
        key=key,
        extensions=extensions,
        case_insensitive=case_insensitive,
        strategy=strategy,
        name=secondary_name,
    )
