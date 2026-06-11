# Companion design: the Slicer "match review" module

Status: agreed design, not yet built. Last updated 2026-06-10.

This note records the design of the Slicer-side companion to the `dataset-matcher`
library: a shared UI module that displays file-matching results the same way in every
SlicerMorph module, so each module does not reimplement matching or its own error pop-up.

The Python library (`dataset-matcher`) is the **engine** (pure stdlib, no Qt). This module
is its **face** in Slicer (Qt UI). They are separate on purpose: the engine must run in any
Python; only the face needs Qt/Slicer.

## Decisions (settled 2026-06-10 with the project owner)

1. **Home.** A dedicated module of its own inside the **SlicerMorph extension** (alongside
   GPA, ALPACA, MergeMarkups), not buried inside any one module. Working name
   `DatasetMatcher` (placeholder; note the mild name overlap with the pip package).
   - SlicerMorph's own modules import it directly (same repo, no new dependency).
   - External SlicerMorph-org extensions (DeCA, ANTsPy, MEMOS) currently declare **no**
     dependency on SlicerMorph (`EXTENSION_DEPENDS "NA"`; MEMOS depends only on PyTorch).
     Adopting the widget there later means adding a SlicerMorph extension dependency -- a
     deliberate, per-extension decision made at migration time, not now.

2. **Form.** One widget, usable **both** as a pop-up dialog and embedded in a module's panel.

3. **Scope.** **File-based matching only** for now. Interactive in-scene node pairing (the
   other MergeMarkups tabs) is out for now but planned. The widget therefore consumes a
   **generic report** (matched / leftovers-A / leftovers-B / ambiguous), agnostic to whether
   the items are files or nodes, so the future node version reuses the same panel.

4. **Behavior on unpaired files.** The widget always shows leftovers on **both** sides plus
   ambiguous names. The **calling module sets the policy**: "strict" (Proceed disabled until
   the match is 100% clean) or "partial" (Proceed runs on just the matched pairs).

5. **Standalone view.** In addition to being embeddable/poppable by other modules, the
   module also offers a **standalone interface** a user can open to sanity-check that two
   folders line up before running a batch.

## What it shows

```
  Match review ---------------------------------------
   Matched (48)
     A_J.nii.gz            <->  A_J.mrk.json
     129S1_SVLMJ_.nii.gz   <->  129S1_SVLMJ_.mrk.json
     ... (46 more)
   Volumes with no landmark (2):  C57.nii.gz, X9.nii.gz
   Landmarks with no volume (1):  spare.mrk.json
   Ambiguous (0)
  ----------------------------------------------------
        [ Cancel ]      [ Proceed with 48 matched ]
```

## Proposed pieces (subject to refinement during build)

- **A review widget class** (Qt) that takes a `MatchReport` (from `dataset-matcher`) plus a
  policy (strict / partial) and labels for the two sides, and renders the table above. It
  exposes the user's decision (proceed / cancel) and the approved matched pairs.
- **A one-call convenience** for modules: hand it two directories (or two file lists) and the
  matching options (extensions, key rule, case sensitivity); it ensures the pip package is
  installed, runs `match_report`, shows the review (as a dialog by default), and returns the
  approved pairs or a cancellation.
- **An install helper** that centralizes the `slicer.packaging.pip_ensure(...)` boilerplate
  currently hand-written in MergeMarkups, so no module repeats it.
- **A standalone module UI** (decision 5): pick two folders + extensions, preview the match.

The widget must stay usable without forcing a particular workflow: per Slicer convention,
do not hard-require Qt in any logic that could be reused headless -- keep the matching/report
logic (the library) separate from the Qt widget.

## What this replaces / fixes

- MergeMarkups' batch tab currently uses `match_datasets` one-directionally: it reports a
  fixed landmark with no semi (as a blocking text pop-up) but **silently drops** a semi file
  with no fixed partner. The shared widget uses the full report and surfaces both sides.
- Removes the per-module "install package / catch error / show messageBox" boilerplate.
- (Unrelated, noted during review: MergeMarkups rebinds `self.markupsView` for two tabs, so
  the Curves tab reads the Merge-All tree's selection. Separate bug, not part of this work.)

## Out of scope (for now)

- Interactive in-scene node pairing (the Curves / Point Sets / All tabs). Same review panel
  is intended to serve it later.
- Migrating the external extensions (DeCA, ANTsPy, MEMOS) -- separate, per-extension steps
  that each add a SlicerMorph dependency.

## Build path (when approved)

The module lands in the **SlicerMorph** repo on its development branch (`geomorphTab` per the
ExtensionsIndex). Because it adds a **new module** (new files + CMakeLists entries), it
requires a local factory build before any push, per the ecosystem rule -- a dev-Slicer run is
not sufficient to catch a missing CMakeLists entry. First consumer: the MergeMarkups batch
tab; then SlicerMorph's other batch modules.
