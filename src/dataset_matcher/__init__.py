"""
dataset-matcher: Match datasets (file lists) by basename across directories.

A lightweight library for aligning file lists from different directories
based on their basenames (filenames without extensions).
"""

from .matcher import (
    match_datasets,
    match_multiple,
    match_report,
    match_directories,
    get_basename,
    list_files,
    MatchReport,
    AmbiguousMatch,
)

from .exceptions import (
    DatasetError,
    IdenticalDatasetError,
    UnmatchedFileError,
    AmbiguousMatchError,
    EmptyDatasetError,
)

__version__ = "0.2.0"

__all__ = [
    # Core functions
    "match_datasets",
    "match_multiple",
    "match_report",
    "match_directories",
    "get_basename",
    "list_files",
    # Result types
    "MatchReport",
    "AmbiguousMatch",
    # Exceptions
    "DatasetError",
    "UnmatchedFileError",
    "AmbiguousMatchError",
    "EmptyDatasetError",
    "IdenticalDatasetError",
    # Version
    "__version__",
]
