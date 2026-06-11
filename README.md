# dataset-matcher

A lightweight Python library for matching datasets (file lists) by basename across directories.

See [DESIGN.md](DESIGN.md) for the design rationale, the filename rule, and the project roadmap.

## Installation

```bash
pip install dataset-matcher
```

Until a release is published to PyPI, install from source:

```bash
pip install "dataset-matcher @ git+https://github.com/SlicerMorph/dataset-matcher.git"
```

## Quick Start

```python
from dataset_matcher import match_datasets, DatasetError

# Match files from different directories by basename
volumes = [
    "/data/scans/specimen_001.nii.gz",
    "/data/scans/specimen_002.nii.gz",
    "/data/scans/specimen_003.nii.gz"
]
landmarks = [
    "/data/landmarks/specimen_002.mrk.json",
    "/data/landmarks/specimen_003.mrk.json",
    "/data/landmarks/specimen_001.mrk.json"
]

try:
    matched_landmarks = match_datasets(volumes, landmarks)
    # Returns landmarks reordered to match volumes:
    # ["/data/landmarks/specimen_001.mrk.json",
    #  "/data/landmarks/specimen_002.mrk.json",
    #  "/data/landmarks/specimen_003.mrk.json"]
except DatasetError as e:
    print(f"Matching failed: {e}")
```

### Inspect before acting (no exceptions)

When you want to show the user what matched before doing anything, use `match_report`,
which never raises and reports problems in both directions:

```python
from dataset_matcher import match_report

report = match_report(volumes, landmarks, name="landmarks")
print(report.summary())
if report.is_complete:
    for volume, landmark in report.pairs:
        process(volume, landmark)
else:
    print("Missing:", report.missing)   # primary files with no partner
    print("Extra:",   report.orphans)   # secondary files with no partner
```

### Match straight from directories

`match_directories` lists the files for you and returns a `MatchReport`:

```python
from dataset_matcher import match_directories

# Two folders, one dataset each:
report = match_directories(
    "/data/scans", "/data/landmarks", [".nii.gz"], [".mrk.json"]
)

# Or two file types in one folder (pass None for the second directory):
report = match_directories(
    "/data/both", None, [".ply"], [".mrk.json"]
)
```

## Features

- **Zero dependencies** for core functionality (pure Python, stdlib only; no Qt).
- **Compound extension support**: `.nii.gz`, `.mrk.json`, `.seg.nrrd`, `.seg.nhdr`,
  `.mrk.fcsv`, `.tar.gz`, and more. Callers can add their own.
- **Dots as name separators**: `skull.mandible.nii.gz` keeps basename `skull.mandible`.
- **Report mode**: inspect matched / missing / extra / ambiguous without raising.
- **Flexible identifiers**: match by basename, a regular expression, or your own function.
- **Case-insensitive option** for cross-platform (macOS / Windows / Linux) file lists.
- **Natural sorting** so frame/slice numbers order as humans expect (2 before 10).
- **Multi-dataset matching**: match 3+ datasets at once.

## API Reference

### `match_datasets(primary, secondary, *, strategy="exact", key=None, extensions=None, case_insensitive=False, name=None, allow_missing=False)`

Match files in `secondary` to files in `primary` by basename. Reorders `secondary` to
align with `primary`. Raises on problems (see Error Handling); use `match_report` for a
non-raising version.

- `strategy`: `"exact"` (default) or `"substring"`.
- `key`: how to derive the match identifier from a filename - `None` uses the basename
  rule, or pass a regular expression (string / compiled pattern; first capture group is
  the identifier) or a callable `path -> identifier`.
- `extensions`: extra file-type endings to recognize, beyond the built-in list.
- `case_insensitive`: match identifiers ignoring letter case.
- `name`: label for the secondary dataset (used in error messages).
- `allow_missing`: return `None` for unmatched positions instead of raising.

### `match_report(primary, secondary, *, key=None, extensions=None, case_insensitive=False, strategy="exact", name=None)`

Same matching, but returns a `MatchReport` and never raises. Useful for showing the user
what will happen. `MatchReport` provides `.pairs`, `.ordered_secondary`, `.missing`,
`.orphans`, `.ambiguous`, `.is_complete`, and `.summary()`.

### `match_directories(primary_dir, secondary_dir, primary_extensions, secondary_extensions, *, ...)`

List two directories (or two file types in one directory, by passing `None` for
`secondary_dir`) and match them, returning a `MatchReport`. Lists with natural sorting and
skips hidden files by default.

### `match_multiple(*datasets, names=None, strategy="exact", key=None, extensions=None, case_insensitive=False, allow_missing=False)`

Match multiple datasets against the first one. Returns a tuple of lists (first unchanged,
others reordered).

### `get_basename(path, extensions=None)`

Extract the basename, removing only one recognized file-type ending. Preserves dots used
as name separators.

```python
>>> get_basename("/path/to/specimen_001.nii.gz")
'specimen_001'
>>> get_basename("/path/to/data.mrk.json")
'data'
>>> get_basename("AJ.mouse.nii.gz")
'AJ.mouse'
>>> get_basename("mouse.skull.nrrd")
'mouse.skull'
>>> get_basename("brain.am", extensions=[".am"])
'brain'
```

### `list_files(directory, extensions=None, recursive=False, *, natural=False, skip_hidden=True, case_insensitive_sort=False)`

List files in a directory, optionally filtered by ending. Skips hidden files (such as
`.DS_Store`) by default, and can sort numerically with `natural=True`.

## Error Handling

```python
from dataset_matcher import DatasetError, UnmatchedFileError, AmbiguousMatchError

try:
    matched = match_datasets(volumes, landmarks)
except UnmatchedFileError as e:
    print(f"Missing files: {e.unmatched}")
except AmbiguousMatchError as e:
    print(f"Multiple matches found: {e.matches}")
except DatasetError as e:
    print(f"General matching error: {e}")
```

## Use Cases

This library was designed for scientific imaging workflows where multiple data types
(volumes, landmarks, models, segmentations) need to be matched by specimen ID:

- **3D Slicer / SlicerMorph**: Batch processing of morphometric data
- **Medical imaging pipelines**: Matching scans with annotations
- **Any workflow** where files in different directories share a common identifier

## License

MIT License
