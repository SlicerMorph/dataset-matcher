"""
dataset-matcher: Match datasets (file lists) by basename across directories.

A lightweight library for aligning file lists from different directories
based on their basenames (filenames without extensions).
"""

from .matcher import (
    match_datasets,
    match_multiple,
    get_basename,
    list_files,
)

from .exceptions import (
    DatasetError,
    UnmatchedFileError,
    AmbiguousMatchError,
    EmptyDatasetError,
)

__version__ = "0.1.0"

__all__ = [
    # Core functions
    "match_datasets",
    "match_multiple",
    "get_basename",
    "list_files",
    # Exceptions
    "DatasetError",
    "UnmatchedFileError",
    "AmbiguousMatchError",
    "EmptyDatasetError",
    # Version
    "__version__",
]
