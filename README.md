# dataset-matcher

A lightweight Python library for matching datasets (file lists) by basename across directories.

## Installation

```bash
pip install dataset-matcher
```

For fuzzy/substring matching support:
```bash
pip install dataset-matcher[fuzzy]
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

## Features

- **Zero dependencies** for core functionality (pure Python, stdlib only)
- **Compound extension support**: `.nii.gz`, `.mrk.json`, `.seg.nrrd`, `.tar.gz`
- **Dots as name separators**: `skull.mandible.nii.gz` → basename `skull.mandible`
- **Optional fuzzy matching**: Install with `[fuzzy]` for substring/approximate matching
- **Clear error messages**: Reports exactly which files are missing/unmatched
- **Multi-dataset matching**: Match 3+ datasets at once

## API Reference

### `match_datasets(primary, secondary, *, strategy="exact", name=None)`

Match files in `secondary` to files in `primary` by basename.

**Parameters:**
- `primary`: List of file paths (the reference order)
- `secondary`: List of file paths to reorder
- `strategy`: Matching strategy - `"exact"` (default) or `"substring"`
- `name`: Optional name for the secondary dataset (used in error messages)

**Returns:** List of paths from `secondary`, reordered to align with `primary`

**Raises:** `DatasetError` if matching fails

### `match_multiple(*datasets, names=None, strategy="exact")`

Match multiple datasets against the first one.

**Parameters:**
- `*datasets`: Two or more lists of file paths
- `names`: Optional list of names for each dataset
- `strategy`: Matching strategy

**Returns:** Tuple of matched lists (first list unchanged, others reordered)

### `get_basename(path)`

Extract the basename, removing only known file format extensions.
Preserves dots used as name separators.

```python
>>> get_basename("/path/to/specimen_001.nii.gz")
'specimen_001'
>>> get_basename("/path/to/data.mrk.json")
'data'
>>> get_basename("skull.mandible.nii.gz")
'skull.mandible'
>>> get_basename("mouse.skull.nrrd")
'mouse.skull'
```

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
