"""
Custom exceptions for dataset-matcher.
"""

from __future__ import annotations


class DatasetError(Exception):
    """Base exception for dataset matching errors."""
    pass


class UnmatchedFileError(DatasetError):
    """Raised when files in one dataset cannot be matched to the other."""
    
    def __init__(self, message: str, unmatched: list[str], dataset_name: str | None = None):
        """
        Initialize UnmatchedFileError.
        
        Args:
            message: Error description
            unmatched: List of basenames that could not be matched
            dataset_name: Optional name of the dataset with unmatched files
        """
        super().__init__(message)
        self.unmatched = unmatched
        self.dataset_name = dataset_name


class AmbiguousMatchError(DatasetError):
    """Raised when a basename matches multiple files."""
    
    def __init__(self, message: str, basename: str, matches: list[str]):
        """
        Initialize AmbiguousMatchError.
        
        Args:
            message: Error description
            basename: The basename that had multiple matches
            matches: List of file paths that matched
        """
        super().__init__(message)
        self.basename = basename
        self.matches = matches


class EmptyDatasetError(DatasetError):
    """Raised when an empty dataset is provided."""
    
    def __init__(self, message: str, dataset_name: str | None = None):
        """
        Initialize EmptyDatasetError.
        
        Args:
            message: Error description
            dataset_name: Optional name of the empty dataset
        """
        super().__init__(message)
        self.dataset_name = dataset_name


class IdenticalDatasetError(DatasetError):
    """Raised when primary and secondary datasets are identical."""
    
    def __init__(self, message: str, dataset_name: str | None = None):
        """
        Initialize IdenticalDatasetError.
        
        Args:
            message: Error description
            dataset_name: Optional name of the secondary dataset
        """
        super().__init__(message)
        self.dataset_name = dataset_name
