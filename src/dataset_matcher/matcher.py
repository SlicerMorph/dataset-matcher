"""
Core matching functions for dataset-matcher.
"""

import os
from typing import Sequence, Literal

from .exceptions import (
    DatasetError,
    UnmatchedFileError,
    AmbiguousMatchError,
    EmptyDatasetError,
)


# Known compound extensions (multi-part extensions, checked first)
# Order matters - longer/more specific extensions should come first
COMPOUND_EXTENSIONS = (
    '.nii.gz',      # NIfTI compressed
    '.mrk.json',    # Slicer markups
    '.seg.nrrd',    # Slicer segmentation
    '.tar.gz',      # Compressed archive
    '.tar.bz2',     # Compressed archive
    '.tar.xz',      # Compressed archive
)

# Known single file format extensions
# Only these are stripped - dots used as name separators are preserved
KNOWN_EXTENSIONS = {
    # Medical imaging
    '.nii', '.nrrd', '.mha', '.mhd', '.dcm', '.dicom',
    '.mgz', '.mnc', '.img', '.hdr',
    # Slicer markups and data
    '.fcsv', '.json', '.mrml', '.ctbl',
    # Meshes and models
    '.ply', '.stl', '.obj', '.vtk', '.vtp', '.vtu',
    '.off', '.gltf', '.glb',
    # Common formats
    '.txt', '.csv', '.tsv', '.xml',
    '.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp',
    # Archives (single extension)
    '.gz', '.zip', '.bz2', '.xz',
}


def get_basename(path: str) -> str:
    """
    Extract the basename from a file path, removing only known file extensions.
    
    Handles compound extensions like .nii.gz, .mrk.json correctly.
    Preserves dots used as name separators (e.g., skull.mandible.nii.gz -> skull.mandible).
    
    Args:
        path: File path (absolute or relative)
        
    Returns:
        Filename without known file format extensions
        
    Examples:
        >>> get_basename("/path/to/specimen_001.nii.gz")
        'specimen_001'
        >>> get_basename("/path/to/data.mrk.json")
        'data'
        >>> get_basename("file.txt")
        'file'
        >>> get_basename("/path/to/skull.mandible.nii.gz")
        'skull.mandible'
        >>> get_basename("mouse.skull.nrrd")
        'mouse.skull'
    """
    filename = os.path.basename(path)
    lower_filename = filename.lower()
    
    # Check for known compound extensions first (order matters)
    for compound_ext in COMPOUND_EXTENSIONS:
        if lower_filename.endswith(compound_ext):
            return filename[:-len(compound_ext)]
    
    # Check for known single extensions
    # We only strip if it's a known file format extension
    if '.' in filename:
        base, ext = os.path.splitext(filename)
        if ext.lower() in KNOWN_EXTENSIONS:
            return base
    
    # No known extension found - return filename as-is
    return filename


def _build_basename_index(
    paths: Sequence[str],
    dataset_name: str | None = None
) -> dict[str, str]:
    """
    Build an index mapping basenames to full paths.
    
    Args:
        paths: List of file paths
        dataset_name: Optional name for error messages
        
    Returns:
        Dictionary mapping basename -> full path
        
    Raises:
        AmbiguousMatchError: If multiple paths have the same basename
    """
    index: dict[str, str] = {}
    
    for path in paths:
        basename = get_basename(path)
        
        if basename in index:
            raise AmbiguousMatchError(
                f"Ambiguous match: basename '{basename}' matches multiple files: "
                f"'{index[basename]}' and '{path}'",
                basename=basename,
                matches=[index[basename], path]
            )
        
        index[basename] = path
    
    return index


def match_datasets(
    primary: Sequence[str],
    secondary: Sequence[str],
    *,
    strategy: Literal["exact", "substring"] = "exact",
    name: str | None = None,
    allow_missing: bool = False,
) -> list[str]:
    """
    Match files in secondary to files in primary by basename.
    
    Reorders the secondary list so that each file corresponds to the file
    at the same index in primary (based on matching basenames).
    
    Args:
        primary: List of file paths (the reference order)
        secondary: List of file paths to match and reorder
        strategy: Matching strategy:
            - "exact": Basenames must match exactly (default)
            - "substring": Secondary basename can be substring of primary
        name: Optional name for the secondary dataset (used in error messages)
        allow_missing: If True, return None for unmatched files instead of raising
        
    Returns:
        List of paths from secondary, reordered to align with primary.
        If allow_missing=True, unmatched positions contain None.
        
    Raises:
        EmptyDatasetError: If either dataset is empty
        UnmatchedFileError: If files cannot be matched (and allow_missing=False)
        AmbiguousMatchError: If multiple files match the same basename
        
    Examples:
        >>> volumes = ["/scans/spec_001.nii.gz", "/scans/spec_002.nii.gz"]
        >>> landmarks = ["/lm/spec_002.mrk.json", "/lm/spec_001.mrk.json"]
        >>> match_datasets(volumes, landmarks)
        ['/lm/spec_001.mrk.json', '/lm/spec_002.mrk.json']
    """
    # Validate inputs
    if not primary:
        raise EmptyDatasetError(
            "Primary dataset is empty",
            dataset_name="primary"
        )
    
    if not secondary:
        raise EmptyDatasetError(
            f"Secondary dataset{f' ({name})' if name else ''} is empty",
            dataset_name=name or "secondary"
        )
    
    # Build index of secondary files
    secondary_index = _build_basename_index(secondary, name)
    
    # Match each primary file to secondary
    result: list[str | None] = []
    unmatched: list[str] = []
    
    for primary_path in primary:
        primary_basename = get_basename(primary_path)
        matched_path = None
        
        if strategy == "exact":
            matched_path = secondary_index.get(primary_basename)
        
        elif strategy == "substring":
            # Find secondary basenames that contain the primary basename
            # or vice versa
            matches = []
            for sec_basename, sec_path in secondary_index.items():
                if primary_basename in sec_basename or sec_basename in primary_basename:
                    matches.append((sec_basename, sec_path))
            
            if len(matches) == 1:
                matched_path = matches[0][1]
            elif len(matches) > 1:
                raise AmbiguousMatchError(
                    f"Ambiguous substring match for '{primary_basename}': "
                    f"matches {[m[0] for m in matches]}",
                    basename=primary_basename,
                    matches=[m[1] for m in matches]
                )
        
        if matched_path is None:
            unmatched.append(primary_basename)
            if allow_missing:
                result.append(None)
        else:
            result.append(matched_path)
    
    # Report unmatched files
    if unmatched and not allow_missing:
        dataset_desc = f"'{name}'" if name else "secondary dataset"
        raise UnmatchedFileError(
            f"No matching files in {dataset_desc} for: {', '.join(unmatched)}",
            unmatched=unmatched,
            dataset_name=name
        )
    
    return result


def match_multiple(
    *datasets: Sequence[str],
    names: Sequence[str] | None = None,
    strategy: Literal["exact", "substring"] = "exact",
    allow_missing: bool = False,
) -> tuple[list[str], ...]:
    """
    Match multiple datasets against the first one.
    
    The first dataset is used as the reference. All other datasets
    are reordered to match its order.
    
    Args:
        *datasets: Two or more lists of file paths
        names: Optional list of names for each dataset (for error messages)
        strategy: Matching strategy ("exact" or "substring")
        allow_missing: If True, return None for unmatched files
        
    Returns:
        Tuple of lists: (primary unchanged, secondary matched, ...)
        
    Raises:
        ValueError: If fewer than 2 datasets provided
        DatasetError: If matching fails
        
    Examples:
        >>> volumes = ["/v/s1.nii.gz", "/v/s2.nii.gz"]
        >>> landmarks = ["/l/s2.mrk.json", "/l/s1.mrk.json"]  
        >>> masks = ["/m/s1.seg.nrrd", "/m/s2.seg.nrrd"]
        >>> v, l, m = match_multiple(volumes, landmarks, masks)
    """
    if len(datasets) < 2:
        raise ValueError("At least 2 datasets are required for matching")
    
    if names is not None and len(names) != len(datasets):
        raise ValueError(
            f"Number of names ({len(names)}) must match number of datasets ({len(datasets)})"
        )
    
    primary = list(datasets[0])
    results = [primary]
    
    for i, secondary in enumerate(datasets[1:], start=1):
        name = names[i] if names else None
        matched = match_datasets(
            primary,
            secondary,
            strategy=strategy,
            name=name,
            allow_missing=allow_missing,
        )
        results.append(matched)
    
    return tuple(results)


def list_files(
    directory: str,
    extensions: Sequence[str] | None = None,
    recursive: bool = False,
) -> list[str]:
    """
    List files in a directory, optionally filtering by extension.
    
    Args:
        directory: Path to directory
        extensions: List of extensions to include (e.g., ['.nii.gz', '.nrrd']).
                   Include the leading dot. If None, include all files.
        recursive: If True, search subdirectories recursively
        
    Returns:
        List of absolute file paths, sorted alphabetically
        
    Examples:
        >>> list_files("/data/scans", extensions=[".nii.gz", ".nrrd"])
        ['/data/scans/specimen_001.nii.gz', '/data/scans/specimen_002.nii.gz']
    """
    if not os.path.isdir(directory):
        raise DatasetError(f"Directory does not exist: {directory}")
    
    # Normalize extensions to lowercase
    if extensions:
        extensions = [ext.lower() for ext in extensions]
    
    def matches_extension(filename: str) -> bool:
        if extensions is None:
            return True
        lower_name = filename.lower()
        return any(lower_name.endswith(ext) for ext in extensions)
    
    files = []
    
    if recursive:
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                if matches_extension(filename):
                    files.append(os.path.join(root, filename))
    else:
        for entry in os.listdir(directory):
            path = os.path.join(directory, entry)
            if os.path.isfile(path) and matches_extension(entry):
                files.append(path)
    
    return sorted(files)
