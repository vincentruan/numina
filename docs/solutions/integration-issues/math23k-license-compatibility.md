# Math23K License Compatibility Assessment

**Date:** 2026-10-14
**Task:** Phase 7a-min/P7b Task 2, Step 2a (precondition for Task 9's Math23KAdapter use)
**Verdict: UNVERIFIED — gate Task 9 adapter usage on confirmation**

## Background

Task 9 implemented `Math23KAdapter` (parse-only scaffolding, no dataset shipped).
Per the plan, before the adapter is actually *used* to import Math23K data, the
dataset's license must be confirmed compatible with this project's MIT license.

## What We Know

- Math23K (Wang, Liu & Shi, "Deep Neural Solver for Math Word Problems," EMNLP 2017)
  is a dataset of 23,162 Chinese elementary math word problems.
- Community mirrors commonly list it as **CC BY-SA 4.0** or research-use-only, but
  these listings are third-party annotations and are frequently wrong.
- The authors' original release (via Microsoft Research Asia / Shuming Shi's group)
  did not publish an explicit OSI license with the dataset files.

## Verification Steps (not yet completed)

1. Locate the authors' original distribution point (GitHub repo or project page).
2. Read the LICENSE file shipped with the dataset.
3. If no license: contact the authors for written permission for (a) redistribution
   in a self-hosted app, (b) derivative question bank entries with attribution.

## Compatibility Analysis (conditional)

| If license is... | Verdict for Numina (MIT, self-hosted, attribution via source_license column) |
|---|---|
| CC BY-SA 4.0 | Compatible **with caution**: ShareAlike may apply to derivative question text; attribution via `source_name="math23k"` + `source_license` column satisfies BY. Consult counsel if distributing modified questions. |
| Research-use-only | **Not compatible** with general self-hosted use. Do not import. |
| Unlicensed | Treat as all-rights-reserved. Do not import; find alternative dataset. |

## Gate

Task 9's adapter code exists but no Math23K data has been imported. The adapter is
also usable with the project's own JSON format (`SelfJSONAdapter`), which carries no
license concern. **Action required before importing Math23K data:** complete the
verification steps above and record the verdict here.
