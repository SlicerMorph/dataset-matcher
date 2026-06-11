"""
Fixture generator for the real-world matching scenarios in TEST_SPEC.md.

This module is committed to the repo, but the empty files it produces are NOT:
the test suite materializes them under pytest's temporary directory (outside the
repo) and they are cleaned up automatically.

Each scenario is a layout: a mapping of subdirectory -> list of entries. An entry
ending in "/" is created as a subdirectory; an entry may contain nested path
components; a name starting with "." (e.g. ".DS_Store") becomes a hidden file.
All files are created empty -- matching is by name only.

Run as a script to dump a scenario's tree to a real folder for inspection:

    python tests/fixture_generator.py --list
    python tests/fixture_generator.py A1 /tmp/dm-fixtures/A1
    python tests/fixture_generator.py --all /tmp/dm-fixtures
"""

import os


# Real specimen names are taken verbatim from Mouse_Models and mouse_CT_atlas;
# see TEST_SPEC.md section 1 for the source of each convention.
SCENARIO_LAYOUTS = {
    # Group A -- baseline clean 1:1 (Mouse_Models Models/ <-> LMs/)
    "A1": {
        "vol": ["129S1_SVIMJ.ply", "A_J.ply", "B6C3F1.ply",
                "BALB_CJ.ply", "AKR_J.ply", "B6D2F1_J.ply"],
        "lm": ["129S1_SVIMJ.mrk.json", "A_J.mrk.json", "B6C3F1.mrk.json",
               "BALB_CJ.mrk.json", "AKR_J.mrk.json", "B6D2F1_J.mrk.json"],
    },

    # Group B -- the basename rule (mouse_CT_atlas targets/ <-> target_LMs/)
    "B1": {  # trailing underscore in the id
        "vol": ["129S1_SVLMJ_.nii.gz", "A_J_.nii.gz"],
        "lm": ["129S1_SVLMJ_.mrk.json", "A_J_.mrk.json"],
    },
    "B2": {  # a dot in the middle of the id
        "vol": ["B6129PF1.J_.nii.gz", "C3HeB.FeJ_.nii.gz"],
        "lm": ["B6129PF1.J_.mrk.json", "C3HeB.FeJ_.mrk.json"],
    },
    "B3": {  # collision guard: .J_ must not be conflated with .K_
        "vol": ["B6129PF1.J_.nii.gz", "B6129PF1.K_.nii.gz"],
        "lm": ["B6129PF1.J_.mrk.json", "B6129PF1.K_.mrk.json"],
    },
    "B4": {  # compound .seg.nrrd recognized (not just .nrrd)
        "vol": ["spec_UCHAR.nii.gz"],
        "seg": ["spec_UCHAR.seg.nrrd"],
    },
    "B5": {  # new compound endings used by get_basename checks
        "misc": ["mask.seg.nhdr", "points.mrk.fcsv"],
    },

    # Group C -- two file types in one folder (mouse_CT_atlas templates/)
    "C1s": {
        "data": ["s1.nii.gz", "s2.nii.gz", "s1.seg.nrrd", "s2.seg.nrrd"],
    },
    "C2s": {
        "data": ["s1.nii.gz", "s2.nii.gz"],
    },
    "C3s": {  # volume, its -label sibling, and its segmentation together
        "data": ["t_UCHAR.nii.gz", "t_UCHAR-label.nii.gz", "t_UCHAR.seg.nrrd"],
    },

    # Group D -- suffix siblings and key extraction (mouse_CT_atlas output/)
    "D1": {
        "src": ["129S1_SVLMJ_.nii.gz", "A_J_.nii.gz"],
        "out": ["129S1_SVLMJ_-transformed.nii.gz", "A_J_-transformed.nii.gz"],
    },
    "D2": {  # same layout as D1, matched via a callable key
        "src": ["129S1_SVLMJ_.nii.gz", "A_J_.nii.gz"],
        "out": ["129S1_SVLMJ_-transformed.nii.gz", "A_J_-transformed.nii.gz"],
    },
    "D3": {  # one source, two derived outputs -> ambiguous
        "src": ["A_J_.nii.gz"],
        "out": ["A_J_-transformed.nii.gz", "A_J_-0forwardAffine.mat"],
    },
    "D4": {  # _median suffix (ape_malpaca medianEstimates)
        "models": ["USNM142188-Cranium.ply"],
        "medians": ["USNM142188-Cranium_median.fcsv"],
    },

    # Group E -- case and separator inconsistency (ape_malpaca templates_LMs)
    "E1": {  # case only (also serves E2)
        "a": ["USNM142185-Cranium.fcsv"],
        "b": ["usnm142185-cranium.mrk.json"],
    },
    "E3": {  # lowercase vs uppercase strain suffix
        "a": ["BTBR_T_Itpr3tf_j.ply"],
        "b": ["BTBR_T_Itpr3tf_J.mrk.json"],
    },
    "E4": {  # separator mismatch (- vs _); also serves E5
        "a": ["USNM590953_CRANIUM.fcsv"],
        "b": ["USNM590953-Cranium.mrk.json"],
    },

    # Group F -- directory hygiene
    "F1": {  # hidden .DS_Store among landmark files (real in Mouse_Models/LMs)
        "vol": ["s1.nii.gz", "s2.nii.gz", "s3.nii.gz"],
        "lm": ["s1.mrk.json", "s2.mrk.json", "s3.mrk.json", ".DS_Store"],
    },
    "F2": {  # stray timestamp dirs among landmark files (real in target_LMs)
        "vol": ["s1.nii.gz", "s2.nii.gz", "s3.nii.gz"],
        "lm": ["s1.mrk.json", "s2.mrk.json", "s3.mrk.json",
               "2025-11-18_18_37_54/", "2025-11-18_18_41_09/"],
    },
    "F3": {  # natural-number sorting
        "seq": ["img_1.png", "img_2.png", "img_10.png"],
    },

    # Group G -- incompleteness and ambiguity
    "G1": {  # missing partner
        "vol": ["a.ply", "b.ply", "c.ply"],
        "lm": ["a.mrk.json", "b.mrk.json"],
    },
    "G2": {  # an extra (orphan) partner
        "vol": ["a.ply", "b.ply", "c.ply"],
        "lm": ["a.mrk.json", "b.mrk.json", "c.mrk.json", "d.mrk.json"],
    },
    "G3": {  # missing and orphan together
        "vol": ["a.ply", "b.ply", "c.ply"],
        "lm": ["a.mrk.json", "c.mrk.json", "d.mrk.json"],
    },
    "G4": {  # same basename in two subdirs -> ambiguous (recursive)
        "vol": ["A_J.ply"],
        "lm": ["dirA/A_J.mrk.json", "dirB/A_J.mrk.json"],
    },
    "G5": {  # identical inputs
        "data": ["a.ply", "b.ply"],
    },
    "G6": {  # empty-list handling
        "data": ["a.ply"],
    },

    # Group H -- extension typos and malformed names (synthetic)
    "H1": {  # uppercase ending recognized
        "vol": ["129S1_SVIMJ.PLY"],
        "lm": ["129S1_SVIMJ.mrk.json"],
    },
    "H2": {  # typo .nii.gz -> .nii.gzz
        "vol": ["A_J.nii.gzz"],
        "lm": ["A_J.mrk.json"],
    },
    "H3": {  # typo .mrk.json -> .mrk.jsn
        "vol": ["A_J.nii.gz"],
        "lm": ["A_J.mrk.jsn"],
    },
    "H4": {  # missing dot in ending
        "misc": ["A_J.mrkjson"],
    },
    "H5": {  # trailing space in name
        "misc": ["A_J.ply "],
    },
    "H6": {  # unusual but valid ending, recovered via extensions=
        "misc": ["brain.am"],
    },

    # Group I -- concatenated template+target names (ape_malpaca)
    "I1": {
        "est": ["USNM142188-Cranium_USNM084655-Cranium_merged_1.fcsv",
                "USNM142188-Cranium_USNM142185-Cranium.fcsv"],
        "tpl": ["USNM084655-Cranium_merged_1.fcsv",
                "USNM142185-Cranium.fcsv"],
    },
    "I2": {
        "tpl": ["USNM142188-Cranium.fcsv"],
        "est": ["USNM142188-Cranium_USNM084655-Cranium_merged_1.fcsv",
                "USNM142188-Cranium_USNM142185-Cranium.fcsv"],
    },
}


def materialize(base, layout):
    """
    Create a scenario's file tree under ``base`` (all files empty).

    Args:
        base: Destination directory (created if needed).
        layout: A mapping of subdirectory -> list of entries.

    Returns:
        The base directory path as a string.
    """
    base = str(base)
    os.makedirs(base, exist_ok=True)
    for subdir, entries in layout.items():
        directory = os.path.join(base, subdir) if subdir else base
        os.makedirs(directory, exist_ok=True)
        for entry in entries:
            if entry.endswith("/"):
                os.makedirs(os.path.join(directory, entry.rstrip("/")), exist_ok=True)
                continue
            path = os.path.join(directory, entry)
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            open(path, "a").close()
    return base


def build_scenario(base, scenario_id):
    """Materialize one scenario by id under ``base`` and return the base path."""
    if scenario_id not in SCENARIO_LAYOUTS:
        raise KeyError("Unknown scenario id: {0}".format(scenario_id))
    return materialize(base, SCENARIO_LAYOUTS[scenario_id])


def _main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Generate matching test fixtures.")
    parser.add_argument("scenario", nargs="?", help="scenario id (e.g. A1)")
    parser.add_argument("out", nargs="?", help="output directory")
    parser.add_argument("--list", action="store_true", help="list scenario ids")
    parser.add_argument("--all", metavar="OUTDIR", help="dump every scenario under OUTDIR")
    args = parser.parse_args(argv)

    if args.list:
        for sid in sorted(SCENARIO_LAYOUTS):
            print(sid)
        return

    if args.all:
        for sid in sorted(SCENARIO_LAYOUTS):
            dest = os.path.join(args.all, sid)
            build_scenario(dest, sid)
            print("wrote", dest)
        return

    if not args.scenario or not args.out:
        parser.error("provide a scenario id and an output directory (or use --list/--all)")

    build_scenario(args.out, args.scenario)
    print("wrote", args.out)


if __name__ == "__main__":
    _main()
