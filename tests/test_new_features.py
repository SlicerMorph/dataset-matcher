"""
Tests for features added in 0.2.0: completed extension list, case-insensitive
matching, key extraction, the report API, better listing, and match_directories.
"""

import re

import pytest

from dataset_matcher import (
    get_basename,
    match_datasets,
    match_report,
    match_directories,
    list_files,
    MatchReport,
    DatasetError,
)


class TestExtensionList:
    def test_new_compound_endings(self):
        assert get_basename("mask.seg.nhdr") == "mask"
        assert get_basename("points.mrk.fcsv") == "points"

    def test_dots_in_name_with_compound(self):
        # Only the recognized ending is stripped; other dots stay in the name.
        assert get_basename("AJ.mouse.nii.gz") == "AJ.mouse"
        assert get_basename("patient.study.mrk.json") == "patient.study"

    def test_unknown_ending_preserved(self):
        assert get_basename("data.weirdformat") == "data.weirdformat"

    def test_caller_supplied_extension(self):
        # .am is not built in; caller can add it.
        assert get_basename("brain.am") == "brain.am"
        assert get_basename("brain.am", extensions=[".am"]) == "brain"

    def test_caller_supplied_compound_extension(self):
        assert get_basename("scan.foo.bar", extensions=[".foo.bar"]) == "scan"


class TestCaseInsensitive:
    def test_case_insensitive_match(self):
        primary = ["/v/Specimen_01.nii.gz", "/v/Specimen_02.nii.gz"]
        secondary = ["/l/specimen_02.mrk.json", "/l/specimen_01.mrk.json"]

        result = match_datasets(primary, secondary, case_insensitive=True)
        assert result == ["/l/specimen_01.mrk.json", "/l/specimen_02.mrk.json"]

    def test_case_sensitive_by_default_does_not_match(self):
        primary = ["/v/Specimen_01.nii.gz"]
        secondary = ["/l/specimen_01.mrk.json"]
        with pytest.raises(DatasetError):
            match_datasets(primary, secondary)


class TestKeyExtraction:
    def test_regex_key_with_group(self):
        # Pull the specimen id out of a longer, inconsistent filename.
        primary = ["/v/scan_id-001_raw.nrrd", "/v/scan_id-002_raw.nrrd"]
        secondary = ["/l/lm_id-002.fcsv", "/l/lm_id-001.fcsv"]

        result = match_datasets(primary, secondary, key=r"id-(\d+)")
        assert result == ["/l/lm_id-001.fcsv", "/l/lm_id-002.fcsv"]

    def test_callable_key(self):
        primary = ["/v/001_anything.nrrd"]
        secondary = ["/l/001_other.fcsv"]

        result = match_datasets(primary, secondary, key=lambda p: p.split("/")[-1][:3])
        assert result == ["/l/001_other.fcsv"]

    def test_regex_avoids_substring_false_match(self):
        # specimen_1 must NOT match specimen_10 when using an anchored id rule.
        primary = ["/v/specimen_1.nrrd", "/v/specimen_10.nrrd"]
        secondary = ["/l/specimen_10.fcsv", "/l/specimen_1.fcsv"]

        result = match_datasets(primary, secondary)
        assert result == ["/l/specimen_1.fcsv", "/l/specimen_10.fcsv"]


class TestMatchReport:
    def test_complete_report(self):
        primary = ["/v/a.nrrd", "/v/b.nrrd"]
        secondary = ["/l/b.fcsv", "/l/a.fcsv"]

        report = match_report(primary, secondary)
        assert isinstance(report, MatchReport)
        assert report.is_complete
        assert len(report.pairs) == 2
        assert report.ordered_secondary == ["/l/a.fcsv", "/l/b.fcsv"]
        assert report.missing == []
        assert report.orphans == []

    def test_missing_and_orphans_both_reported(self):
        primary = ["/v/a.nrrd", "/v/b.nrrd"]      # b has no landmark
        secondary = ["/l/a.fcsv", "/l/c.fcsv"]    # c is an extra

        report = match_report(primary, secondary)
        assert not report.is_complete
        assert report.missing == ["/v/b.nrrd"]
        assert report.orphans == ["/l/c.fcsv"]
        assert report.ordered_secondary == ["/l/a.fcsv", None]

    def test_ambiguous_reported_not_raised(self):
        primary = ["/v/a.nrrd"]
        secondary = ["/l1/a.fcsv", "/l2/a.fcsv"]  # duplicate basename

        report = match_report(primary, secondary)
        assert report.ambiguous
        assert report.ambiguous[0].key == "a"
        assert len(report.ambiguous[0].candidates) == 2

    def test_summary_is_string(self):
        report = match_report(["/v/a.nrrd"], ["/l/a.fcsv"], name="landmarks")
        assert isinstance(report.summary(), str)
        assert "landmarks" in report.summary()


class TestListFilesImprovements:
    def test_natural_sort(self, tmp_path):
        for n in ["img_2.png", "img_10.png", "img_1.png"]:
            (tmp_path / n).touch()

        files = list_files(str(tmp_path), natural=True)
        names = [f.split("/")[-1] for f in files]
        assert names == ["img_1.png", "img_2.png", "img_10.png"]

    def test_skip_hidden_by_default(self, tmp_path):
        (tmp_path / "real.nrrd").touch()
        (tmp_path / ".DS_Store").touch()

        files = list_files(str(tmp_path))
        names = [f.split("/")[-1] for f in files]
        assert names == ["real.nrrd"]

    def test_include_hidden_when_requested(self, tmp_path):
        (tmp_path / "real.nrrd").touch()
        (tmp_path / ".hidden").touch()

        files = list_files(str(tmp_path), skip_hidden=False)
        assert len(files) == 2


class TestMatchDirectories:
    def test_two_folders(self, tmp_path):
        vol = tmp_path / "vol"
        vol.mkdir()
        (vol / "s1.nii.gz").touch()
        (vol / "s2.nii.gz").touch()

        lm = tmp_path / "lm"
        lm.mkdir()
        (lm / "s2.mrk.json").touch()
        (lm / "s1.mrk.json").touch()
        (lm / ".DS_Store").touch()  # must be ignored

        report = match_directories(
            str(vol), str(lm), [".nii.gz"], [".mrk.json"]
        )
        assert report.is_complete
        assert len(report.pairs) == 2

    def test_two_types_in_one_folder(self, tmp_path):
        d = tmp_path / "both"
        d.mkdir()
        (d / "s1.ply").touch()
        (d / "s2.ply").touch()
        (d / "s1.mrk.json").touch()
        (d / "s2.mrk.json").touch()

        report = match_directories(
            str(d), None, [".ply"], [".mrk.json"]
        )
        assert report.is_complete
        assert len(report.pairs) == 2

    def test_overlapping_extensions_in_one_folder_raises(self, tmp_path):
        d = tmp_path / "both"
        d.mkdir()
        (d / "s1.nrrd").touch()
        with pytest.raises(DatasetError):
            match_directories(str(d), None, [".nrrd"], [".nrrd"])
