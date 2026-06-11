# dataset-matcher -- Design Document

Status: draft / working design. Last updated 2026-06-10.

This document records what `dataset-matcher` is for, the design decisions behind it,
the current state of the code, and the planned work. It exists so the project can be
picked up later (or by someone else) without having to re-derive the intent from the
source. Issues and pull requests should refer back to the relevant section here.

---

## 1. Purpose

Many batch workflows need to take two (or more) sets of files and figure out which file
in one set corresponds to which file in another -- for example, a folder of 3D models and
a folder of landmark files, where `specimen_001.ply` belongs with `specimen_001.mrk.json`.
The shared assumption is that **corresponding files have the same name, differing only in
their file-type ending**.

In the SlicerMorph ecosystem this pairing is currently re-implemented separately inside
almost every batch module (GPA, ALPACA, DeCA, ANTsPyRegistration, the semi-landmark tools,
and others). Those copies have drifted apart and disagree with one another -- most visibly
about how filenames are split into a "name" part and an "ending" part, and about the order
in which files come back from disk (which differs across macOS, Windows, and Linux).

`dataset-matcher` is intended to be the **single, well-specified, pip-installable library**
that every module imports instead of rolling its own. It is deliberately generic (it talks
about "datasets" and "files", not "specimens" or "landmarks") so that it can be useful to
the wider 3D Slicer community, not only SlicerMorph.

### Design principles

- **Pure standard library, no Qt, no Slicer dependency.** The library must be usable from
  any Python environment, including the Slicer application's Python and plain command-line
  scripts. This is also what would allow it to be adopted by Slicer core, not just an
  extension. Optional features may pull optional dependencies, but the core must not.
- **One correct behavior, specified here.** Where the old per-module code disagreed, the
  library picks one rule, documents it in this file, and every consumer inherits it.
- **Fail loudly, or report clearly -- never pair silently wrong.** The most damaging bug in
  the old code is silent mis-pairing (everything shifts by one and no error is raised). The
  library must either raise a clear error or hand back a structured report the caller can
  show to the user.

---

## 2. The problem in the wild

A survey of the ecosystem (2026-06-10) found the same job done in several different ways.
These are the behaviors the library must replace or support. (Full file-by-file inventory
is in the appendix.)

1. **Compare names directly across two folders.** The safe approach, and what this library
   does. (ALPACA, GPA, parts of DeCA and ANTsPy.)
2. **Sort both folders and pair by position** (first-with-first, second-with-second),
   trusting the order to line up. Dangerous: a missing file or a stray hidden file such as
   `.DS_Store` shifts every pair with no warning. (DeCA's import path; one R function.)
3. **Guess an identifier** by pulling the first number out of a filename, or by testing
   whether one name appears inside another. Misfires -- e.g. `specimen_1` matches
   `specimen_10`. (legacy ALPACA, ANTsPy, PlaceSemiLMPatches, ProjectSemiLM,
   MeshDistanceMeasurement.)
4. **Hand-written "natural" sorting** so that frame/slice numbers sort as humans expect
   (2 before 10). Written independently in at least two places. (ImageStacks, the
   photogrammetry video tools.)
5. **Pair a file with a sibling in the same folder** distinguished by an added tag, e.g.
   `photo01.jpg` with `photo01_mask.jpg`. A related but different shape -- see Scope below.
   (Photogrammetry, MEMOS.)

---

## 3. Core concept: how a filename is split (the "basename")

The single most important rule in the library. It resolves the disagreement in behavior #1
above.

**Rule.** The library keeps an allowlist of recognized file-type endings. To reduce a
filename to its matchable **basename**:

1. If the filename ends with a recognized **multi-part** ending (one containing more than one
   dot, such as `.nii.gz`, `.mrk.json`, `.seg.nrrd`, `.seg.nhdr`, `.mrk.fcsv`, `.tar.gz`),
   strip exactly that ending.
2. Otherwise, if it ends with a recognized **single** ending (`.ply`, `.nrrd`, `.nii`,
   `.fcsv`, `.json`, `.obj`, ...), strip that.
3. Otherwise, leave the name unchanged.

Any dot that is **not** part of a recognized ending is treated as an ordinary character of
the name, **not** as an extension separator.

**Worked examples:**

| Filename                 | Basename        | Why                                          |
| ------------------------ | --------------- | -------------------------------------------- |
| `specimen_001.nii.gz`    | `specimen_001`  | recognized multi-part ending `.nii.gz`       |
| `AJ.mouse.nii.gz`        | `AJ.mouse`      | strip only `.nii.gz`; the `.mouse` is name   |
| `mouse.skull.nrrd`       | `mouse.skull`   | strip only `.nrrd`; the `.skull` is name     |
| `data.mrk.json`          | `data`          | recognized multi-part ending `.mrk.json`     |
| `specimen.left.femur.ply`| `specimen.left.femur` | strip only `.ply`                      |
| `notes.unknownext`       | `notes.unknownext` | ending not recognized; left as-is         |

**Rationale.** This is the rule decided with the project owner on 2026-06-10. It is also
what the current code already implements; the remaining work is to make the allowlist
complete (see section 7). It deliberately differs from the naive `name.split(".")[0]` used
in some old modules, which would wrongly turn `AJ.mouse.nii.gz` into `AJ`. Because of that
difference, migrating a module that used `split(".")[0]` can change which files match for
specimen names that contain dots; each migration must be checked. (See Migration, section 10.)

**Consequence to be aware of.** Because unrecognized endings are preserved, a file whose
real type is simply not in the allowlist will not have its ending stripped and may fail to
match. This is why completing the allowlist matters, and why callers will be able to extend
it (section 7).

---

## 4. Scope: which layouts are supported

Decided with the project owner on 2026-06-10.

**In scope:**

- **Two or more separate folders**, each holding one dataset, matched by basename. This is
  the primary case and the normal SlicerMorph data layout (each dataset in its own folder).
- **A single folder holding two or more different file *types*** (told apart by their
  endings) matched by basename -- e.g. one folder containing both `specimen_001.ply` and
  `specimen_001.mrk.json`. Most SlicerMorph modules will not arrange data this way, but a
  general-purpose tool should support it.

**Out of scope:**

- **Pairing a file with a same-type sibling distinguished only by an added tag** (e.g.
  `photo01.jpg` with `photo01_mask.jpg`). This is behavior #5 above. The Photogrammetry
  extension has specialized needs here (masks, video frames) and will handle it separately.

---

## 5. Current API (v0.1.0)

Implemented in `src/dataset_matcher/matcher.py`. Pure standard library.

- `get_basename(path) -> str`
  Reduce a path to its matchable basename per the rule in section 3.

- `match_datasets(primary, secondary, *, strategy="exact"|"substring", name=None, allow_missing=False) -> list`
  Reorder `secondary` so that entry *i* corresponds to `primary[i]` by basename. With
  `allow_missing=True`, unmatched positions are returned as `None` instead of raising.

- `match_multiple(*datasets, names=None, strategy=..., allow_missing=False) -> tuple`
  The same matching applied to N datasets against the first.

- `list_files(directory, extensions=None, recursive=False) -> list`
  List files in a directory (optionally filtered by ending), returned in plain
  alphabetical (lexicographic) order.

- Exceptions, all subclasses of `DatasetError`: `UnmatchedFileError`, `AmbiguousMatchError`,
  `EmptyDatasetError`, `IdenticalDatasetError`.

The current state matches one easy, clean case well and is covered by tests. It is used in
production by exactly one module so far: SlicerMorph's **MergeMarkups**.

---

## 6. Error handling and reporting model

Today the library communicates failure by raising exceptions. That is correct for scripts,
but most Slicer modules have a UI and want to **show the user** what matched and what did
not, then let them choose to proceed or cancel.

**Planned:** a non-raising "report" / dry-run entry point that returns a structured result:

- the matched pairs,
- entries in `primary` with no partner (**missing**),
- entries in `secondary` with no partner (**orphans / extras**) -- the current code only
  checks one direction and silently ignores extras,
- entries that matched more than one file (**ambiguous**).

The existing exception-raising functions remain (a thin wrapper over the report) for callers
that prefer "match or fail".

---

## 7. Planned additions

Derived from the ecosystem survey. Each should become a tracked issue.

1. **Complete the known-endings allowlist.** Do one careful pass over SlicerMorph and Slicer
   formats and add every multi-part and single ending in use. Known gaps today include
   `.seg.nhdr` and `.mrk.fcsv`. Allow callers to add their own endings rather than forking
   the list.
2. **Report / dry-run API** (section 6). Highest priority for UI adoption.
3. **Pluggable identifier extraction.** Let a caller supply a rule (a regular expression or a
   small function) for deriving the matchable identifier from a filename, to properly replace
   the fragile number-guessing and substring approaches (behavior #3). Harden or retire the
   current naive `"substring"` strategy.
4. **Better listing.** Add human-friendly natural-number sorting and case-insensitive
   ordering to `list_files`, and skip hidden/system files (e.g. `.DS_Store`) by default.
   Fold in the natural-sort logic that ImageStacks and the video tools wrote independently.
5. **Case-insensitive matching option,** for portability across case-insensitive (macOS,
   Windows) and case-sensitive (Linux) file systems.
6. **High-level convenience helper:** folder(s) + endings -> aligned, validated pairs (or a
   report), supporting both the two-folder layout and the two-types-in-one-folder layout
   from section 4.
7. **Packaging:** publish to PyPI and pin a version in each consumer's requirements, so an
   update to the library cannot quietly break the modules that depend on it. Resolve the
   currently-declared-but-unused `[fuzzy]` optional dependency (either implement a fuzzy
   strategy or remove it).

---

## 8. Distribution and versioning

- Currently **not on PyPI**. The one consumer installs it straight from the GitHub `main`
  branch (`dataset-matcher @ git+https://github.com/SlicerMorph/dataset-matcher.git`) with
  no version constraint, so every consumer tracks the latest commit. A breaking change would
  affect all consumers at once.
- **Plan:** tag releases, publish to PyPI, and have consumers depend on a pinned version.
  Slicer modules install Python packages at runtime via `slicer.packaging` /
  `slicer.util.pip_install`; that mechanism works with a normal PyPI release.
- Keep the core dependency-free and Qt-free so the package stays adoptable by Slicer core and
  by non-Slicer users.

---

## 9. Non-goals

- Reading or interpreting file *contents*. The library matches by name only.
- Knowing anything Slicer-specific (node types, the MRML scene, Qt). Callers do that.
- Same-folder suffix/tag sibling pairing (section 4, out of scope).

---

## 10. Migration plan

1. Land the planned additions (section 7), at least the report API and the completed ending
   list, before converting modules.
2. **Pilot on two modules** chosen for risk and coverage:
   - **DeCA** -- replace position-based pairing (behavior #2) with name-based matching. This
     is the highest-risk silent-bug site.
   - **ANTsPyRegistration** -- replace one-directional substring matching with the report API
     and, where needed, explicit identifier extraction.
3. Review each pilot against real datasets, watching specifically for cases where the new
   filename rule (section 3) changes which files match compared with the old code.
4. Roll out to the remaining modules (ALPACA, the semi-landmark tools, etc.) one repository at
   a time, each as its own commit/PR in that repository. Per ecosystem policy, code is not
   copied between extension repositories; each depends on the published `dataset-matcher`
   package.

---

## Appendix: ecosystem inventory (2026-06-10)

Locations are approximate (file and nearby line) and may shift as repositories change.

| Repo / module | Where | Behavior | Notes |
| ------------- | ----- | -------- | ----- |
| SlicerMorph / MergeMarkups | `MergeMarkups.py` ~389 | #1 name match | **Already uses this library.** |
| SlicerMorph / ALPACA | `ALPACA.py` ~1111, ~1228 | #1 name match | Hand-rolls `.mrk.json`/`.fcsv` stripping. |
| SlicerMorph / ALPACA (legacy) | `ALPACA_legacy.py` ~1068 | #3 substring | `baseName in lmFile`. |
| SlicerMorph / GPA | `GPA.py` ~1441 | #1 name match | Double-splits to peel `.mrk.json`. |
| SlicerMorph / PlaceSemiLMPatches | `PlaceSemiLMPatches.py` ~157 | #3 number-guess | First numeric token + substring. |
| SlicerMorph / ProjectSemiLM | `ProjectSemiLM.py` ~230 | #3 substring | Stem + substring. |
| SlicerMorph / MeshDistanceMeasurement | `MeshDistanceMeasurement.py` ~216 | #3 number-guess | Same regex-number pattern. |
| SlicerMorph / CreateSemiLMPatches | `CreateSemiLMPatches.py` ~450 | #4 listing | `os.walk` + `fnmatch`, unordered. |
| SlicerMorph / ImageStacks | `ImageStacks.py` ~14, ~29 | #4 natural sort | Hand-written natural sort + missing-file report. |
| SlicerMorph / ExportMorphoJLandmarkFile | `ExportMorphoJLandmarkFile.py` ~121 | #4 listing | `glob` + split-on-ending. |
| SlicerDeCA / DeCA | `DeCA.py` ~1275/1288 (+ run* callers) | #2 positional | `sorted(os.listdir())` zipped by index; up to four parallel lists. |
| SlicerDeCA / DeCA | `DeCA.py` ~1137/1149 | #1 name match | `getLandmarkFileByID` / `getModelFileByID`. |
| SlicerANTsPy / ANTsPyRegistration | `ANTsPyRegistration.py` ~1640 | #1 name match | `comparePathBasenames`, one direction only. |
| SlicerANTsPy / ANTsPyRegistration | `ANTsPyRegistration.py` ~2269 | #3 substring | `getLandmarksForImage`, `basename in p`. |
| SlicerPhotogrammetry | `PhotoMasking.py`, `ODM.py`, `VideoMasking.py` | #5 same-folder tag | Out of scope; handled separately. |
| SlicerMEMOs / MEMOS | `MEMOS.py` ~256 | #5 sibling output | Volume -> `{name}.seg.nrrd`. |
| VPs | `tools/generate_manifest.py` ~31 | #1 name match | Set-intersection of `.json` and `.png` by prefix. |
| SlicerMorphR | `read.malpaca.estimates.R` ~98; `log_parser*.R` | #2 positional | Sequential pairing; the log parsers add existence checks. |

Repositories with no relevant matching code: DeveloperAgent, SlicerScriptEditor, Tutorials,
Mouse_Models.
