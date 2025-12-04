"""
Tests for dataset-matcher.
"""

import os
import tempfile
import pytest

from dataset_matcher import (
    match_datasets,
    match_multiple,
    get_basename,
    list_files,
    DatasetError,
    UnmatchedFileError,
    AmbiguousMatchError,
    EmptyDatasetError,
)


class TestGetBasename:
    """Tests for get_basename function."""
    
    def test_simple_extension(self):
        assert get_basename("/path/to/file.txt") == "file"
        assert get_basename("file.txt") == "file"
    
    def test_nii_gz(self):
        assert get_basename("/data/specimen_001.nii.gz") == "specimen_001"
        assert get_basename("specimen_001.nii.gz") == "specimen_001"
    
    def test_mrk_json(self):
        assert get_basename("/lm/data.mrk.json") == "data"
        assert get_basename("sample.mrk.json") == "sample"
    
    def test_seg_nrrd(self):
        assert get_basename("/seg/mask.seg.nrrd") == "mask"
    
    def test_tar_gz(self):
        assert get_basename("archive.tar.gz") == "archive"
    
    def test_dots_as_separator_nii_gz(self):
        """Test dots used as name separators with .nii.gz extension."""
        assert get_basename("skull.mandible.nii.gz") == "skull.mandible"
        assert get_basename("/path/to/skull.mandible.nii.gz") == "skull.mandible"
    
    def test_dots_as_separator_nrrd(self):
        """Test dots used as name separators with .nrrd extension."""
        assert get_basename("mouse.skull.nrrd") == "mouse.skull"
        assert get_basename("/data/mouse.skull.nrrd") == "mouse.skull"
    
    def test_dots_as_separator_ply(self):
        """Test dots used as name separators with mesh extensions."""
        assert get_basename("specimen.left.femur.ply") == "specimen.left.femur"
        assert get_basename("bone.fragment.001.stl") == "bone.fragment.001"
    
    def test_dots_as_separator_fcsv(self):
        """Test dots used as name separators with .fcsv extension."""
        assert get_basename("landmarks.cranium.fcsv") == "landmarks.cranium"
    
    def test_multiple_dots_with_compound_ext(self):
        """Test multiple dots with compound extensions."""
        assert get_basename("a.b.c.d.nii.gz") == "a.b.c.d"
        assert get_basename("patient.study.series.mrk.json") == "patient.study.series"
    
    def test_no_extension(self):
        assert get_basename("/path/to/file") == "file"
        assert get_basename("file") == "file"
    
    def test_unknown_extension_preserved(self):
        """Test that unknown extensions are preserved as part of the name."""
        # .unknown is not in KNOWN_EXTENSIONS, so it stays
        assert get_basename("file.unknown") == "file.unknown"
        assert get_basename("data.customformat") == "data.customformat"
    
    def test_absolute_path(self):
        assert get_basename("/a/b/c/d/specimen.nii.gz") == "specimen"
    
    def test_relative_path(self):
        assert get_basename("./data/specimen.nii.gz") == "specimen"


class TestMatchDatasets:
    """Tests for match_datasets function."""
    
    def test_exact_match_reorder(self):
        """Test that files are correctly reordered."""
        primary = [
            "/scans/specimen_001.nii.gz",
            "/scans/specimen_002.nii.gz",
            "/scans/specimen_003.nii.gz",
        ]
        secondary = [
            "/lm/specimen_003.mrk.json",
            "/lm/specimen_001.mrk.json",
            "/lm/specimen_002.mrk.json",
        ]
        
        result = match_datasets(primary, secondary)
        
        assert result == [
            "/lm/specimen_001.mrk.json",
            "/lm/specimen_002.mrk.json",
            "/lm/specimen_003.mrk.json",
        ]
    
    def test_already_ordered(self):
        """Test when files are already in correct order."""
        primary = ["/a/file1.nii.gz", "/a/file2.nii.gz"]
        secondary = ["/b/file1.fcsv", "/b/file2.fcsv"]
        
        result = match_datasets(primary, secondary)
        
        assert result == secondary
    
    def test_different_extensions(self):
        """Test matching across different file types."""
        volumes = ["/v/subj_01.nii.gz", "/v/subj_02.nii.gz"]
        meshes = ["/m/subj_02.ply", "/m/subj_01.ply"]
        
        result = match_datasets(volumes, meshes)
        
        assert result == ["/m/subj_01.ply", "/m/subj_02.ply"]
    
    def test_unmatched_raises_error(self):
        """Test that unmatched files raise UnmatchedFileError."""
        primary = ["/a/file1.nii.gz", "/a/file2.nii.gz"]
        secondary = ["/b/file1.fcsv", "/b/file3.fcsv"]  # file2 missing
        
        with pytest.raises(UnmatchedFileError) as exc_info:
            match_datasets(primary, secondary)
        
        assert "file2" in exc_info.value.unmatched
    
    def test_unmatched_with_name(self):
        """Test that dataset name appears in error message."""
        primary = ["/a/file1.nii.gz"]
        secondary = ["/b/other.fcsv"]
        
        with pytest.raises(UnmatchedFileError) as exc_info:
            match_datasets(primary, secondary, name="landmarks")
        
        assert exc_info.value.dataset_name == "landmarks"
        assert "landmarks" in str(exc_info.value)
    
    def test_allow_missing(self):
        """Test allow_missing=True returns None for unmatched."""
        primary = ["/a/file1.nii.gz", "/a/file2.nii.gz"]
        secondary = ["/b/file1.fcsv"]
        
        result = match_datasets(primary, secondary, allow_missing=True)
        
        assert result == ["/b/file1.fcsv", None]
    
    def test_empty_primary_raises(self):
        """Test that empty primary raises EmptyDatasetError."""
        with pytest.raises(EmptyDatasetError) as exc_info:
            match_datasets([], ["/b/file.txt"])
        
        assert exc_info.value.dataset_name == "primary"
    
    def test_empty_secondary_raises(self):
        """Test that empty secondary raises EmptyDatasetError."""
        with pytest.raises(EmptyDatasetError):
            match_datasets(["/a/file.txt"], [])
    
    def test_duplicate_basenames_raises(self):
        """Test that duplicate basenames in secondary raise error."""
        primary = ["/a/file.nii.gz"]
        secondary = ["/b/file.fcsv", "/c/file.fcsv"]  # same basename
        
        with pytest.raises(AmbiguousMatchError) as exc_info:
            match_datasets(primary, secondary)
        
        assert "file" in exc_info.value.basename
        assert len(exc_info.value.matches) == 2


class TestMatchDatasetsSubstring:
    """Tests for substring matching strategy."""
    
    def test_substring_match_secondary_in_primary(self):
        """Test substring matching when secondary basename is in primary."""
        # Common case: shorter secondary names contained in longer primary names
        primary = ["/a/specimen_001_scan.nii.gz", "/a/specimen_002_scan.nii.gz"]
        secondary = ["/b/specimen_002.fcsv", "/b/specimen_001.fcsv"]
        
        result = match_datasets(primary, secondary, strategy="substring")
        
        # Secondary "specimen_001" is substring of primary "specimen_001_scan"
        assert result == ["/b/specimen_001.fcsv", "/b/specimen_002.fcsv"]
    
    def test_substring_match_primary_in_secondary(self):
        """Test substring matching when primary basename is in secondary."""
        # Reverse case: primary names contained in secondary
        primary = ["/a/subj_01.nii.gz", "/a/subj_02.nii.gz"]
        secondary = ["/b/subj_02_landmarks.fcsv", "/b/subj_01_landmarks.fcsv"]
        
        result = match_datasets(primary, secondary, strategy="substring")
        
        # Primary "subj_01" is substring of secondary "subj_01_landmarks"
        assert result == ["/b/subj_01_landmarks.fcsv", "/b/subj_02_landmarks.fcsv"]
    
    def test_substring_ambiguous_raises(self):
        """Test that ambiguous substring matches raise error."""
        primary = ["/a/specimen.nii.gz"]
        secondary = ["/b/specimen_a.fcsv", "/b/specimen_b.fcsv"]  # both contain "specimen"
        
        with pytest.raises(AmbiguousMatchError):
            match_datasets(primary, secondary, strategy="substring")


class TestMatchMultiple:
    """Tests for match_multiple function."""
    
    def test_three_datasets(self):
        """Test matching three datasets."""
        volumes = ["/v/s1.nii.gz", "/v/s2.nii.gz"]
        landmarks = ["/l/s2.mrk.json", "/l/s1.mrk.json"]
        masks = ["/m/s2.seg.nrrd", "/m/s1.seg.nrrd"]
        
        v, l, m = match_multiple(volumes, landmarks, masks)
        
        # Volumes unchanged (reference)
        assert v == ["/v/s1.nii.gz", "/v/s2.nii.gz"]
        # Others reordered to match
        assert l == ["/l/s1.mrk.json", "/l/s2.mrk.json"]
        assert m == ["/m/s1.seg.nrrd", "/m/s2.seg.nrrd"]
    
    def test_with_names(self):
        """Test that names are passed through for error messages."""
        volumes = ["/v/s1.nii.gz"]
        landmarks = ["/l/other.mrk.json"]  # won't match
        
        with pytest.raises(UnmatchedFileError) as exc_info:
            match_multiple(volumes, landmarks, names=["volumes", "landmarks"])
        
        assert exc_info.value.dataset_name == "landmarks"
    
    def test_fewer_than_two_raises(self):
        """Test that fewer than 2 datasets raises ValueError."""
        with pytest.raises(ValueError):
            match_multiple(["/a/file.txt"])
    
    def test_mismatched_names_count_raises(self):
        """Test that wrong number of names raises ValueError."""
        with pytest.raises(ValueError):
            match_multiple(
                ["/a/f1.txt"], ["/b/f1.txt"], ["/c/f1.txt"],
                names=["a", "b"]  # only 2 names for 3 datasets
            )


class TestListFiles:
    """Tests for list_files function."""
    
    def test_list_all_files(self, tmp_path):
        """Test listing all files without filter."""
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.nii.gz").touch()
        (tmp_path / "file3.mrk.json").touch()
        
        files = list_files(str(tmp_path))
        
        assert len(files) == 3
        assert all(str(tmp_path) in f for f in files)
    
    def test_filter_by_extension(self, tmp_path):
        """Test filtering by extension."""
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.nii.gz").touch()
        (tmp_path / "file3.nii.gz").touch()
        
        files = list_files(str(tmp_path), extensions=[".nii.gz"])
        
        assert len(files) == 2
        assert all("nii.gz" in f for f in files)
    
    def test_multiple_extensions(self, tmp_path):
        """Test filtering by multiple extensions."""
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.nii.gz").touch()
        (tmp_path / "file3.mrk.json").touch()
        
        files = list_files(str(tmp_path), extensions=[".nii.gz", ".mrk.json"])
        
        assert len(files) == 2
    
    def test_sorted_output(self, tmp_path):
        """Test that output is sorted."""
        (tmp_path / "c_file.txt").touch()
        (tmp_path / "a_file.txt").touch()
        (tmp_path / "b_file.txt").touch()
        
        files = list_files(str(tmp_path))
        filenames = [os.path.basename(f) for f in files]
        
        assert filenames == ["a_file.txt", "b_file.txt", "c_file.txt"]
    
    def test_recursive(self, tmp_path):
        """Test recursive file listing."""
        (tmp_path / "file1.txt").touch()
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file2.txt").touch()
        
        # Non-recursive
        files = list_files(str(tmp_path), recursive=False)
        assert len(files) == 1
        
        # Recursive
        files = list_files(str(tmp_path), recursive=True)
        assert len(files) == 2
    
    def test_nonexistent_directory_raises(self):
        """Test that nonexistent directory raises DatasetError."""
        with pytest.raises(DatasetError):
            list_files("/nonexistent/path")
    
    def test_case_insensitive_extension(self, tmp_path):
        """Test that extension matching is case-insensitive."""
        (tmp_path / "file1.TXT").touch()
        (tmp_path / "file2.txt").touch()
        
        files = list_files(str(tmp_path), extensions=[".txt"])
        
        assert len(files) == 2


class TestExceptions:
    """Tests for exception classes."""
    
    def test_unmatched_file_error_attributes(self):
        """Test UnmatchedFileError stores unmatched files."""
        err = UnmatchedFileError(
            "Files not found",
            unmatched=["file1", "file2"],
            dataset_name="landmarks"
        )
        
        assert err.unmatched == ["file1", "file2"]
        assert err.dataset_name == "landmarks"
    
    def test_ambiguous_match_error_attributes(self):
        """Test AmbiguousMatchError stores matches."""
        err = AmbiguousMatchError(
            "Multiple matches",
            basename="specimen",
            matches=["/a/specimen.txt", "/b/specimen.txt"]
        )
        
        assert err.basename == "specimen"
        assert len(err.matches) == 2
    
    def test_empty_dataset_error_attributes(self):
        """Test EmptyDatasetError stores dataset name."""
        err = EmptyDatasetError("Empty", dataset_name="volumes")
        
        assert err.dataset_name == "volumes"
    
    def test_exception_inheritance(self):
        """Test all exceptions inherit from DatasetError."""
        assert issubclass(UnmatchedFileError, DatasetError)
        assert issubclass(AmbiguousMatchError, DatasetError)
        assert issubclass(EmptyDatasetError, DatasetError)
        
        # And DatasetError inherits from Exception
        assert issubclass(DatasetError, Exception)


class TestIntegration:
    """Integration tests with real file operations."""
    
    def test_full_workflow(self, tmp_path):
        """Test complete workflow: list files, match datasets."""
        # Create volume directory
        vol_dir = tmp_path / "volumes"
        vol_dir.mkdir()
        (vol_dir / "subj_001.nii.gz").touch()
        (vol_dir / "subj_002.nii.gz").touch()
        (vol_dir / "subj_003.nii.gz").touch()
        
        # Create landmarks directory (different order)
        lm_dir = tmp_path / "landmarks"
        lm_dir.mkdir()
        (lm_dir / "subj_002.mrk.json").touch()
        (lm_dir / "subj_003.mrk.json").touch()
        (lm_dir / "subj_001.mrk.json").touch()
        
        # List files
        volumes = list_files(str(vol_dir), extensions=[".nii.gz"])
        landmarks = list_files(str(lm_dir), extensions=[".mrk.json"])
        
        assert len(volumes) == 3
        assert len(landmarks) == 3
        
        # Match datasets
        matched_landmarks = match_datasets(volumes, landmarks)
        
        # Verify basenames align
        for vol, lm in zip(volumes, matched_landmarks):
            assert get_basename(vol) == get_basename(lm)
    
    def test_partial_match_workflow(self, tmp_path):
        """Test workflow with partial matches using allow_missing."""
        vol_dir = tmp_path / "volumes"
        vol_dir.mkdir()
        (vol_dir / "subj_001.nii.gz").touch()
        (vol_dir / "subj_002.nii.gz").touch()
        
        lm_dir = tmp_path / "landmarks"
        lm_dir.mkdir()
        (lm_dir / "subj_001.mrk.json").touch()
        # subj_002 landmarks missing
        
        volumes = list_files(str(vol_dir))
        landmarks = list_files(str(lm_dir))
        
        matched = match_datasets(volumes, landmarks, allow_missing=True)
        
        assert matched[0] is not None
        assert matched[1] is None
