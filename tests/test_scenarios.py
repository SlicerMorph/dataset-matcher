"""
Real-world matching scenarios from TEST_SPEC.md.

Each test builds a scenario's empty-file tree under pytest's tmp_path (outside the
repo) via fixture_generator, then exercises the library and asserts the expected
outcome. The fixtures are generated, never committed.
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import fixture_generator as fg  # noqa: E402

import dataset_matcher as dm  # noqa: E402


def build(tmp_path, scenario_id):
    return fg.build_scenario(os.path.join(str(tmp_path), scenario_id), scenario_id)


def names(paths):
    return [os.path.basename(p) for p in paths]


# --------------------------------------------------------------------------
# Group A -- baseline clean match
# --------------------------------------------------------------------------

def test_A1_clean_match_reorders(tmp_path):
    base = build(tmp_path, "A1")
    vol = dm.list_files(os.path.join(base, "vol"), [".ply"])
    # Deliberately scramble the secondary order; matching must realign it.
    lm = list(reversed(dm.list_files(os.path.join(base, "lm"), [".mrk.json"])))

    result = dm.match_datasets(vol, lm)

    assert len(result) == len(vol)
    for volume, landmark in zip(vol, result):
        assert dm.get_basename(volume) == dm.get_basename(landmark)


def test_A2_report_complete(tmp_path):
    base = build(tmp_path, "A1")
    vol = dm.list_files(os.path.join(base, "vol"), [".ply"])
    lm = dm.list_files(os.path.join(base, "lm"), [".mrk.json"])

    report = dm.match_report(vol, lm)
    assert report.is_complete
    assert len(report.pairs) == 6
    assert report.missing == [] and report.orphans == [] and report.ambiguous == []


# --------------------------------------------------------------------------
# Group B -- the basename rule
# --------------------------------------------------------------------------

def test_B1_trailing_underscore(tmp_path):
    base = build(tmp_path, "B1")
    vol = dm.list_files(os.path.join(base, "vol"), [".nii.gz"])
    lm = dm.list_files(os.path.join(base, "lm"), [".mrk.json"])

    assert dm.get_basename(vol[0]).endswith("_")
    result = dm.match_datasets(vol, lm)
    assert len(result) == 2
    for v, r in zip(vol, result):
        assert dm.get_basename(v) == dm.get_basename(r)


def test_B2_mid_name_dot(tmp_path):
    base = build(tmp_path, "B2")
    vol = dm.list_files(os.path.join(base, "vol"), [".nii.gz"])
    lm = dm.list_files(os.path.join(base, "lm"), [".mrk.json"])

    assert dm.get_basename(os.path.join(base, "vol", "B6129PF1.J_.nii.gz")) == "B6129PF1.J_"
    result = dm.match_datasets(vol, lm)
    for v, r in zip(vol, result):
        assert dm.get_basename(v) == dm.get_basename(r)


def test_B3_collision_guard(tmp_path):
    base = build(tmp_path, "B3")
    vol = dm.list_files(os.path.join(base, "vol"), [".nii.gz"])
    lm = dm.list_files(os.path.join(base, "lm"), [".mrk.json"])

    # The two ids differ only after the mid-name dot; they must stay distinct.
    assert dm.get_basename(os.path.join(base, "vol", "B6129PF1.J_.nii.gz")) == "B6129PF1.J_"
    assert dm.get_basename(os.path.join(base, "vol", "B6129PF1.K_.nii.gz")) == "B6129PF1.K_"
    result = dm.match_datasets(vol, lm)
    assert len(result) == 2
    for v, r in zip(vol, result):
        assert dm.get_basename(v) == dm.get_basename(r)


def test_B4_compound_seg_nrrd(tmp_path):
    base = build(tmp_path, "B4")
    vol = dm.list_files(os.path.join(base, "vol"), [".nii.gz"])
    seg = dm.list_files(os.path.join(base, "seg"), [".seg.nrrd"])

    result = dm.match_datasets(vol, seg)
    assert result == seg
    assert dm.get_basename(seg[0]) == "spec_UCHAR"


def test_B5_new_compound_endings(tmp_path):
    base = build(tmp_path, "B5")
    assert dm.get_basename(os.path.join(base, "misc", "mask.seg.nhdr")) == "mask"
    assert dm.get_basename(os.path.join(base, "misc", "points.mrk.fcsv")) == "points"


# --------------------------------------------------------------------------
# Group C -- two file types in one folder
# --------------------------------------------------------------------------

def test_C1s_two_types_one_folder(tmp_path):
    base = build(tmp_path, "C1s")
    data = os.path.join(base, "data")
    report = dm.match_directories(data, None, [".nii.gz"], [".seg.nrrd"])
    assert report.is_complete
    assert len(report.pairs) == 2


def test_C2s_overlapping_extensions_raise(tmp_path):
    base = build(tmp_path, "C2s")
    data = os.path.join(base, "data")
    with pytest.raises(dm.DatasetError):
        dm.match_directories(data, None, [".nii.gz"], [".nii.gz"])


def test_C3s_label_sibling_not_matched(tmp_path):
    base = build(tmp_path, "C3s")
    data = os.path.join(base, "data")
    report = dm.match_directories(data, None, [".nii.gz"], [".seg.nrrd"])
    assert len(report.pairs) == 1
    assert len(report.missing) == 1
    assert dm.get_basename(report.missing[0]) == "t_UCHAR-label"


# --------------------------------------------------------------------------
# Group D -- suffix siblings and key extraction
# --------------------------------------------------------------------------

def test_D1_plain_match_does_not_pair_derived_outputs(tmp_path):
    base = build(tmp_path, "D1")
    src = dm.list_files(os.path.join(base, "src"), [".nii.gz"])
    out = dm.list_files(os.path.join(base, "out"), [".nii.gz"])

    report = dm.match_report(src, out)
    assert len(report.pairs) == 0
    assert len(report.missing) == len(src)
    assert len(report.orphans) == len(out)


def test_D2_callable_key_recovers_source_id(tmp_path):
    base = build(tmp_path, "D2")
    src = dm.list_files(os.path.join(base, "src"), [".nii.gz"])
    out = dm.list_files(os.path.join(base, "out"), [".nii.gz"])

    key = lambda p: dm.get_basename(p).split("-")[0]
    result = dm.match_datasets(src, out, key=key)
    assert len(result) == 2
    for s, r in zip(src, result):
        assert key(s) == key(r)


def test_D3_one_source_many_outputs_is_ambiguous(tmp_path):
    base = build(tmp_path, "D3")
    src = dm.list_files(os.path.join(base, "src"), [".nii.gz"])
    out = dm.list_files(os.path.join(base, "out"))  # both .nii.gz and .mat

    key = lambda p: dm.get_basename(p).split("-")[0]
    report = dm.match_report(src, out, key=key)
    assert report.ambiguous
    assert report.ambiguous[0].key == "A_J_"


def test_D4_median_suffix_via_key(tmp_path):
    base = build(tmp_path, "D4")
    models = dm.list_files(os.path.join(base, "models"), [".ply"])
    medians = dm.list_files(os.path.join(base, "medians"), [".fcsv"])

    key = lambda p: dm.get_basename(p).removesuffix("_median")
    result = dm.match_datasets(models, medians, key=key)
    assert len(result) == 1


# --------------------------------------------------------------------------
# Group E -- case and separator inconsistency
# --------------------------------------------------------------------------

def test_E1_case_insensitive_match(tmp_path):
    base = build(tmp_path, "E1")
    a = dm.list_files(os.path.join(base, "a"), [".fcsv"])
    b = dm.list_files(os.path.join(base, "b"), [".mrk.json"])

    result = dm.match_datasets(a, b, case_insensitive=True)
    assert result == b


def test_E2_case_sensitive_default_fails(tmp_path):
    base = build(tmp_path, "E1")
    a = dm.list_files(os.path.join(base, "a"), [".fcsv"])
    b = dm.list_files(os.path.join(base, "b"), [".mrk.json"])

    with pytest.raises(dm.UnmatchedFileError):
        dm.match_datasets(a, b)


def test_E3_lowercase_strain_suffix(tmp_path):
    base = build(tmp_path, "E3")
    a = dm.list_files(os.path.join(base, "a"), [".ply"])
    b = dm.list_files(os.path.join(base, "b"), [".mrk.json"])

    assert dm.match_datasets(a, b, case_insensitive=True) == b


def test_E4_case_folding_does_not_fix_separator(tmp_path):
    base = build(tmp_path, "E4")
    a = dm.list_files(os.path.join(base, "a"), [".fcsv"])
    b = dm.list_files(os.path.join(base, "b"), [".mrk.json"])

    report = dm.match_report(a, b, case_insensitive=True)
    assert not report.is_complete
    assert report.missing and report.orphans


def test_E5_normalizing_key_fixes_separator(tmp_path):
    base = build(tmp_path, "E4")
    a = dm.list_files(os.path.join(base, "a"), [".fcsv"])
    b = dm.list_files(os.path.join(base, "b"), [".mrk.json"])

    key = lambda p: dm.get_basename(p).lower().replace("-", "_")
    result = dm.match_datasets(a, b, key=key)
    assert len(result) == 1


# --------------------------------------------------------------------------
# Group F -- directory hygiene
# --------------------------------------------------------------------------

def test_F1_skip_hidden_files(tmp_path):
    base = build(tmp_path, "F1")
    lm = dm.list_files(os.path.join(base, "lm"))
    assert ".DS_Store" not in names(lm)
    assert len(lm) == 3


def test_F2_skip_stray_directories(tmp_path):
    base = build(tmp_path, "F2")
    vol = os.path.join(base, "vol")
    lm = os.path.join(base, "lm")
    # Listing returns files only; the timestamp dirs are ignored.
    assert len(dm.list_files(lm, [".mrk.json"])) == 3
    report = dm.match_directories(vol, lm, [".nii.gz"], [".mrk.json"])
    assert report.is_complete
    assert len(report.pairs) == 3


def test_F3_natural_sort(tmp_path):
    base = build(tmp_path, "F3")
    files = dm.list_files(os.path.join(base, "seq"), natural=True)
    assert names(files) == ["img_1.png", "img_2.png", "img_10.png"]


# --------------------------------------------------------------------------
# Group G -- incompleteness and ambiguity
# --------------------------------------------------------------------------

def test_G1_missing_raises(tmp_path):
    base = build(tmp_path, "G1")
    vol = dm.list_files(os.path.join(base, "vol"), [".ply"])
    lm = dm.list_files(os.path.join(base, "lm"), [".mrk.json"])

    with pytest.raises(dm.UnmatchedFileError) as exc:
        dm.match_datasets(vol, lm)
    assert "c" in exc.value.unmatched


def test_G2_orphan_reported_but_match_succeeds(tmp_path):
    base = build(tmp_path, "G2")
    vol = dm.list_files(os.path.join(base, "vol"), [".ply"])
    lm = dm.list_files(os.path.join(base, "lm"), [".mrk.json"])

    report = dm.match_report(vol, lm)
    assert not report.is_complete
    assert names(report.orphans) == ["d.mrk.json"]
    # match_datasets ignores extras and still returns the 3 pairs.
    assert len(dm.match_datasets(vol, lm)) == 3


def test_G3_missing_and_orphan(tmp_path):
    base = build(tmp_path, "G3")
    vol = dm.list_files(os.path.join(base, "vol"), [".ply"])
    lm = dm.list_files(os.path.join(base, "lm"), [".mrk.json"])

    report = dm.match_report(vol, lm)
    assert names(report.missing) == ["b.ply"]
    assert names(report.orphans) == ["d.mrk.json"]


def test_G4_duplicate_basename_ambiguous(tmp_path):
    base = build(tmp_path, "G4")
    vol = dm.list_files(os.path.join(base, "vol"), [".ply"])
    lm = dm.list_files(os.path.join(base, "lm"), [".mrk.json"], recursive=True)

    with pytest.raises(dm.AmbiguousMatchError) as exc:
        dm.match_datasets(vol, lm)
    assert len(exc.value.matches) == 2


def test_G5_identical_inputs_raise(tmp_path):
    base = build(tmp_path, "G5")
    x = dm.list_files(os.path.join(base, "data"), [".ply"])
    with pytest.raises(dm.IdenticalDatasetError):
        dm.match_datasets(x, x)


def test_G6_empty_inputs_raise(tmp_path):
    base = build(tmp_path, "G6")
    x = dm.list_files(os.path.join(base, "data"), [".ply"])
    with pytest.raises(dm.EmptyDatasetError):
        dm.match_datasets([], x)
    with pytest.raises(dm.EmptyDatasetError):
        dm.match_datasets(x, [])


# --------------------------------------------------------------------------
# Group H -- extension typos and malformed names
# --------------------------------------------------------------------------

def test_H1_uppercase_ending_recognized(tmp_path):
    base = build(tmp_path, "H1")
    vol = dm.list_files(os.path.join(base, "vol"), [".PLY"])
    lm = dm.list_files(os.path.join(base, "lm"), [".mrk.json"])

    assert dm.get_basename(vol[0]) == "129S1_SVIMJ"
    assert len(dm.match_datasets(vol, lm)) == 1


def test_H2_typo_ending_not_silently_matched(tmp_path):
    base = build(tmp_path, "H2")
    vol = dm.list_files(os.path.join(base, "vol"))
    lm = dm.list_files(os.path.join(base, "lm"))

    report = dm.match_report(vol, lm)
    assert len(report.pairs) == 0
    assert dm.get_basename(vol[0]) == "A_J.nii.gzz"


def test_H3_typo_secondary_ending(tmp_path):
    base = build(tmp_path, "H3")
    vol = dm.list_files(os.path.join(base, "vol"), [".nii.gz"])
    lm = dm.list_files(os.path.join(base, "lm"))

    report = dm.match_report(vol, lm)
    assert len(report.pairs) == 0


def test_H4_missing_dot_preserved(tmp_path):
    base = build(tmp_path, "H4")
    assert dm.get_basename(os.path.join(base, "misc", "A_J.mrkjson")) == "A_J.mrkjson"


def test_H5_trailing_space_preserved(tmp_path):
    base = build(tmp_path, "H5")
    # Documents current behavior (whitespace not stripped); see TEST_SPEC H5.
    assert dm.get_basename(os.path.join(base, "misc", "A_J.ply ")) == "A_J.ply "


def test_H6_caller_extension_recovers_id(tmp_path):
    base = build(tmp_path, "H6")
    path = os.path.join(base, "misc", "brain.am")
    assert dm.get_basename(path) == "brain.am"
    assert dm.get_basename(path, extensions=[".am"]) == "brain"


# --------------------------------------------------------------------------
# Group I -- concatenated template+target names
# --------------------------------------------------------------------------

def test_I1_extract_target_id_with_fallback(tmp_path):
    base = build(tmp_path, "I1")
    est = dm.list_files(os.path.join(base, "est"), [".fcsv"])
    tpl = dm.list_files(os.path.join(base, "tpl"), [".fcsv"])

    def target_id(path):
        stem = dm.get_basename(path)
        match = re.match(r"^USNM\d+-Cranium_(USNM\d+.*)$", stem)
        return match.group(1) if match else stem

    result = dm.match_datasets(est, tpl, key=target_id)
    assert len(result) == 2
    assert None not in result
    for estimate, template in zip(est, result):
        assert target_id(estimate) == target_id(template)


def test_I2_template_id_duplicate_is_ambiguous(tmp_path):
    base = build(tmp_path, "I2")
    tpl = dm.list_files(os.path.join(base, "tpl"), [".fcsv"])
    est = dm.list_files(os.path.join(base, "est"), [".fcsv"])

    report = dm.match_report(tpl, est, key=r"^(USNM\d+)")
    assert report.ambiguous
    assert report.ambiguous[0].key == "USNM142188"
