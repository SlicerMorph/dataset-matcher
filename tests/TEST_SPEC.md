# Test Specification: real-world matching scenarios

Status: draft for review. Last updated 2026-06-10.

This document defines a set of test scenarios for `dataset-matcher`, derived from the
**actual file-naming conventions** in two SlicerMorph data repositories:

- `Mouse_Models` -- inbred-strain mouse skull models + landmarks, and the `ape_malpaca`
  automated-landmarking estimates (Zhang et al. 2022 style).
- `mouse_CT_atlas` -- the *Mus musculus* craniofacial atlas: target volumes, landmarks,
  templates, and registration outputs.

The goal is to test the library against the messy reality of these names (trailing
underscores, dots in the middle of names, mixed case and separators, compound and typo'd
endings, stray non-file entries, derived-output suffixes) rather than against tidy
invented names.

The synthetic fixtures are **empty files** -- matching is by name only, so contents do not
matter. See "Fixture and harness plan" at the end for how the files get created.

---

## 1. Observed naming conventions (the ground truth)

| # | Convention | Real example (and source) |
| - | ---------- | ------------------------- |
| C1 | Clean 1:1 prefix across two folders | `Models/129S1_SVIMJ.ply` <-> `LMs/129S1_SVIMJ.mrk.json` (62 perfectly paired) |
| C2 | Underscores inside the id | `A_J.ply`, `BALB_CBYJ.ply`, `B6D2F1_J.ply` (`Mouse_Models/Models`) |
| C3 | Trailing underscore in the id | `data/targets/129S1_SVLMJ_.nii.gz` <-> `data/target_LMs/129S1_SVLMJ_.mrk.json` |
| C4 | A dot in the **middle** of the id | `data/targets/B6129PF1.J_.nii.gz`, `C3HeB.FeJ_.nii.gz`, `KK.HlJ_.nii.gz` |
| C5 | Compound endings | `.nii.gz`, `.mrk.json`, `.seg.nrrd` (`data/templates/..._UCHAR.seg.nrrd`) |
| C6 | Two file types in one folder | `data/templates/` holds `.nii.gz`, `.seg.nrrd`, `.mrk.json`, `.fcsv`, `.csv` together |
| C7 | A volume and its label/seg sibling, distinguished by an added tag | `..._UCHAR.nii.gz` vs `..._UCHAR-label.nii.gz` vs `..._UCHAR.seg.nrrd` |
| C8 | Derived outputs with an appended suffix | `output/129S1_SVLMJ_-transformed.nii.gz`, `output/129S1_SVLMJ_-0forwardAffine.mat` (source `targets/129S1_SVLMJ_.nii.gz`) |
| C9 | Mixed case in the id | `templates_LMs/USNM590953_CRANIUM.fcsv` vs `USNM142185-Cranium.fcsv` |
| C10 | Mixed separator (`-` vs `_`) | `USNM142185-Cranium.fcsv` vs `USNM590953_CRANIUM.fcsv` |
| C11 | Lowercase vs uppercase strain suffix | `BTBR_T_Itpr3tf_j.ply` (lowercase `_j`) among otherwise `_J` names |
| C12 | A descriptive suffix appended to the id | `medianEstimates/USNM142188-Cranium_median.fcsv` (`_median`); `templates_LMs/..._merged_1.fcsv` |
| C13 | Concatenated template+target ids in one name | `individualEstimates/USNM142188-Cranium_USNM084655-Cranium_merged_1.fcsv` |
| C14 | Stray non-file entries in a data folder | `data/target_LMs/2025-11-18_18_37_54/` (timestamp dirs alongside 51 `.mrk.json`) |
| C15 | Hidden OS files present | `.DS_Store` in `Mouse_Models/LMs/`, `mouse_CT_atlas/data/quick_LM/`, etc. |
| C16 | `.csv`/`.fcsv`/`.mat` companions | `low_res_skull_only_LM_LPS.csv`, `Skull_LMs.fcsv`, `output/*-0forwardAffine.mat` |

Typo'd / malformed endings (convention C17) do **not** appear in the real data; they are
introduced synthetically in Group H, built by corrupting real names.

---

## 2. Scenario catalog

Each scenario lists: the fixture files, the call to make, and the expected outcome.
"in scope" notes whether plain basename matching is expected to handle it, or whether it
needs the `key=` extraction feature, or is intentionally out of scope.

Legend for expected outcome: **pairs** = correctly aligned pairs; **missing** = primary
files with no partner; **orphans** = secondary files with no partner; **ambiguous** = a key
matching more than one file; **raises X** = the named exception from `match_datasets`.

### Group A -- Baseline clean match

| ID | Derived from | Fixture | Call | Expected |
| -- | ------------ | ------- | ---- | -------- |
| A1 | C1 | `vol/` = 6 `*.ply` (129S1_SVIMJ, A_J, B6C3F1, BALB_CJ, AKR_J, B6D2F1_J); `lm/` = same 6 as `*.mrk.json`, shuffled order | `match_datasets(vol, lm)` | 6 pairs, reordered to vol order; `is_complete` |
| A2 | C1 | same as A1 | `match_report(vol, lm)` | `is_complete` True; 0 missing, 0 orphans, 0 ambiguous |

### Group B -- The basename rule (dots, trailing underscore, compound endings)

| ID | Derived from | Fixture | Call | Expected |
| -- | ------------ | ------- | ---- | -------- |
| B1 | C3 | `vol/129S1_SVLMJ_.nii.gz`, `vol/A_J_.nii.gz`; `lm/` matching `.mrk.json` | `match_datasets` | 2 pairs; basenames keep the trailing `_` (`129S1_SVLMJ_`) |
| B2 | C4 | `vol/B6129PF1.J_.nii.gz`, `vol/C3HeB.FeJ_.nii.gz`; `lm/` matching `.mrk.json` | `match_datasets` | 2 pairs; basenames keep the mid-name dot (`B6129PF1.J_`) |
| B3 | C4 (collision guard) | `vol/B6129PF1.J_.nii.gz`, `vol/B6129PF1.K_.nii.gz`; `lm/` matching `.mrk.json` | `match_datasets` | 2 distinct pairs (`.J_` not conflated with `.K_`). **Note:** the old `split(".")[0]` rule would reduce both to `B6129PF1` and mis-pair; this scenario locks in the correct behavior. |
| B4 | C5 | `vol/spec_UCHAR.nii.gz`; `seg/spec_UCHAR.seg.nrrd` | `match_datasets(vol, seg)` | 1 pair; both reduce to `spec_UCHAR` (`.seg.nrrd` recognized, not just `.nrrd`) |
| B5 | C5 (new endings) | files ending `.seg.nhdr` and `.mrk.fcsv` | `get_basename` checks | endings stripped to the bare id |

### Group C -- Two file types in one folder (C6)

| ID | Derived from | Fixture | Call | Expected |
| -- | ------------ | ------- | ---- | -------- |
| C1s | C6 | one folder with `s1.nii.gz`, `s2.nii.gz`, `s1.seg.nrrd`, `s2.seg.nrrd` | `match_directories(dir, None, [".nii.gz"], [".seg.nrrd"])` | 2 pairs; `is_complete` |
| C2s | C6 guard | one folder, both extension lists `[".nii.gz"]` | `match_directories(dir, None, [".nii.gz"], [".nii.gz"])` | raises `DatasetError` (overlapping endings in one folder) |
| C3s | C6 + C7 | folder with `t_UCHAR.nii.gz`, `t_UCHAR-label.nii.gz`, `t_UCHAR.seg.nrrd` | `match_directories(dir, None, [".nii.gz"], [".seg.nrrd"])` | primary listing includes both `t_UCHAR` and `t_UCHAR-label`; `t_UCHAR` pairs with the seg, `t_UCHAR-label` is reported **missing** (its basename differs). Confirms label files are not silently matched. |

### Group D -- Suffix siblings and key extraction (C7, C8, C12)

| ID | Derived from | Fixture | Call | Expected |
| -- | ------------ | ------- | ---- | -------- |
| D1 | C8 | `src/129S1_SVLMJ_.nii.gz`, `src/A_J_.nii.gz`; `out/129S1_SVLMJ_-transformed.nii.gz`, `out/A_J_-transformed.nii.gz` | `match_datasets(src, out)` plain | both **missing**/**orphan** -- basenames differ (`..._` vs `..._-transformed`). Documents that plain matching does **not** pair derived outputs. |
| D2 | C8 + key | same as D1 | `match_datasets(src, out, key=lambda p: get_basename(p).split("-")[0])` | 2 pairs (`-transformed` stripped). Shows a callable key recovers the source id. |
| D3 | C8 ambiguity | `src/A_J_.nii.gz`; `out/A_J_-transformed.nii.gz`, `out/A_J_-0forwardAffine.mat` | `match_report(src, out, key=lambda p: get_basename(p).split("-")[0])` | `ambiguous` lists key `A_J_` (one source, two derived outputs) |
| D4 | C12 + key | `models/USNM142188-Cranium.ply`; `medians/USNM142188-Cranium_median.fcsv` | `match_datasets(models, medians, key=lambda p: get_basename(p).removesuffix("_median"))` | 1 pair (`_median` stripped) |
| D5 | C7 (scope note) | mask sibling `photo01_mask.jpg` vs `photo01.jpg` | n/a | **Out of scope** per DESIGN.md section 4; documented here as a non-goal, no test asserting a pair. |

### Group E -- Case and separator inconsistency (C9, C10, C11)

| ID | Derived from | Fixture | Call | Expected |
| -- | ------------ | ------- | ---- | -------- |
| E1 | C9/C11 | primary `USNM142185-Cranium.fcsv`; secondary `usnm142185-cranium.mrk.json` | `match_datasets(..., case_insensitive=True)` | 1 pair |
| E2 | C9/C11 | same as E1 | `match_datasets(...)` default | raises `UnmatchedFileError` (case-sensitive default) |
| E3 | C11 | primary `BTBR_T_Itpr3tf_j.ply`; secondary `BTBR_T_Itpr3tf_J.mrk.json` | `match_datasets(..., case_insensitive=True)` | 1 pair |
| E4 | C10 | primary `USNM590953_CRANIUM.fcsv`; secondary `USNM590953-Cranium.mrk.json` | `match_datasets(..., case_insensitive=True)` | still **missing**/**orphan** -- case folding does not fix `_` vs `-`. Documents the limitation; the fix is a normalizing `key=` (E5). |
| E5 | C10 + key | same as E4 | `key=lambda p: get_basename(p).lower().replace("-", "_")` | 1 pair |

### Group F -- Directory hygiene (C14, C15, natural sort)

| ID | Derived from | Fixture | Call | Expected |
| -- | ------------ | ------- | ---- | -------- |
| F1 | C15 | `lm/` with 3 `.mrk.json` plus a real `.DS_Store` file | `list_files(lm)` then match | `.DS_Store` excluded (default `skip_hidden`); match complete |
| F2 | C14 | `lm/` with 3 `.mrk.json` plus subdirs `2025-11-18_18_37_54/`, `2025-11-18_18_41_09/`; `vol/` with 3 `.nii.gz` | `match_directories(vol, lm, [".nii.gz"], [".mrk.json"])` | 3 pairs; subdirs ignored (listing returns files only). A naive count (3 vs 5 entries) or sort-and-zip would misalign. |
| F3 | natural sort (synthetic) | `seq/img_1.png`, `img_2.png`, `img_10.png` | `list_files(seq, natural=True)` | order `img_1, img_2, img_10` (not `img_1, img_10, img_2`) |

### Group G -- Incompleteness and ambiguity

| ID | Derived from | Fixture | Call | Expected |
| -- | ------------ | ------- | ---- | -------- |
| G1 | missing | `vol/` 3 specimens; `lm/` missing one of them | `match_datasets` | raises `UnmatchedFileError`, `.unmatched` names the missing id |
| G2 | orphan | `vol/` 3; `lm/` 3 matching + 1 extra | `match_report` | `is_complete` False; `orphans` = the extra; `match_datasets` still returns 3 pairs (extras ignored) |
| G3 | both | `vol/` {a,b,c}; `lm/` {a,c,d} | `match_report` | `missing` = [b], `orphans` = [d] |
| G4 | C12 ambiguity | recursive: `lm/dirA/A_J.mrk.json`, `lm/dirB/A_J.mrk.json`; `vol/A_J.ply` | `match_datasets(vol, list_files(lm, recursive=True))` | raises `AmbiguousMatchError`, `.matches` len 2 |
| G5 | identical | same list passed as both inputs | `match_datasets(x, x)` | raises `IdenticalDatasetError` |
| G6 | empty | empty primary, or empty secondary | `match_datasets` | raises `EmptyDatasetError` (correct `dataset_name`) |

### Group H -- Extension typos and malformed names (C17, synthetic)

| ID | Built by corrupting | Fixture | Call | Expected |
| -- | ------------------- | ------- | ---- | -------- |
| H1 | uppercase ending | `vol/129S1_SVIMJ.PLY`; `lm/129S1_SVIMJ.mrk.json` | `match_datasets` | 1 pair -- ending recognition is case-insensitive, so `.PLY` reduces to `129S1_SVIMJ` |
| H2 | typo `.nii.gz`->`.nii.gzz` | `vol/A_J.nii.gzz`; `lm/A_J.mrk.json` | `match_report` | NOT paired -- `.nii.gzz` unrecognized, basename stays `A_J.nii.gzz`. Reported as missing/orphan so the typo is visible, not silently mis-handled. |
| H3 | typo `.mrk.json`->`.mrk.jsn` | `lm/A_J.mrk.jsn` against `vol/A_J.nii.gz` | `match_report` | NOT paired; surfaced as missing/orphan |
| H4 | missing dot | `lm/A_J.mrkjson` | `get_basename` | returns `A_J.mrkjson` unchanged (unknown ending preserved) |
| H5 | trailing space | `vol/A_J.ply ` (note trailing space) | `get_basename` | returns `A_J.ply ` unchanged (`.ply` not at end). **Open question:** should the library strip surrounding whitespace? Flagged for decision. |
| H6 | unusual but valid ending | `vol/brain.am` (Amira) | `get_basename("brain.am")` and `get_basename("brain.am", extensions=[".am"])` | `brain.am` by default; `brain` with the extra ending. Tests caller extensibility. |

### Group I -- Concatenated template+target names (C13, complex regex)

| ID | Derived from | Fixture | Call | Expected |
| -- | ------------ | ------- | ---- | -------- |
| I1 | C13 | `est/USNM142188-Cranium_USNM084655-Cranium_merged_1.fcsv`, `est/USNM142188-Cranium_USNM142185-Cranium.fcsv`; templates `tpl/USNM084655-Cranium_merged_1.fcsv`, `tpl/USNM142185-Cranium.fcsv` | `match_datasets(est, tpl, key=callable)` where the callable captures the **target** id from an estimate name and falls back to the bare basename for a template name | 2 pairs, each estimate matched to its template by the extracted target id. (A bare regex cannot be used here because the same rule is applied to both sides; templates need the fallback.) |
| I2 | C13 (first id) | primary `tpl/USNM142188-Cranium.fcsv`; secondary = the two estimates above | `match_report(tpl, est, key=r"^(USNM\d+)")` (captures the **template** id) | both estimates reduce to template id `USNM142188`, so the secondary has a duplicate key -> reported as `ambiguous`. Tests regex group extraction and duplicate detection. |

---

## 3. Coverage map (scenario -> feature)

| Feature | Scenarios |
| ------- | --------- |
| basename rule: trailing `_`, mid-name dots | B1, B2, B3 |
| compound endings incl. new `.seg.nhdr`/`.mrk.fcsv` | B4, B5, C1s |
| two-types-in-one-folder + overlap guard | C1s, C2s, C3s |
| `key=` callable extraction | D2, D3, D4, E5 |
| `key=` regex extraction (groups) | I1, I2 |
| derived-output / suffix siblings (and their scope) | D1, D5, C3s |
| `case_insensitive` matching (and its limits) | E1, E2, E3, E4 |
| report API: missing / orphans / ambiguous / complete | A2, G2, G3, G4, D3 |
| listing: skip hidden, skip dirs, natural sort | F1, F2, F3 |
| existing exceptions preserved | G1, G4, G5, G6, E2 |
| ending recognition case-insensitivity vs typos | H1, H2, H3, H4, H5 |
| caller-extendable endings | H6 |

---

## 4. Fixture and harness plan (for the next step, after this spec is approved)

Recommended approach -- **declarative scenarios materialized at test time**:

1. Encode each scenario above as data: a list of relative file paths to create (empty), the
   call to make, and the expected outcome. Keep this in `tests/scenarios.py` (or a JSON
   file) so the spec and the code stay in step.
2. A parametrized pytest fixture creates the files under pytest's `tmp_path`, runs the call,
   and asserts the outcome. Nothing is committed except the scenario data and the test.
3. This keeps the repo free of hundreds of committed empty files while still exercising real
   on-disk listing (hidden files, stray dirs, sorting) -- which Groups F and the
   `match_directories` scenarios require.

Optional: a small `tests/dump_fixtures.py` that writes any scenario's tree to a real folder
on disk, for manual inspection in the IDE.

Open decisions to confirm before building:
- **H5 (whitespace):** should `get_basename` strip surrounding whitespace from names? (Lean
  yes, but it is a behavior change.)
- **Fixtures on disk vs materialized at test time:** the recommendation above is
  materialize-at-test-time; confirm you are happy with that rather than a committed
  `tests/fixtures/` tree of empty files.
