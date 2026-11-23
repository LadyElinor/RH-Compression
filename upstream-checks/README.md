# How far did the PR #266 repair build?

We traced the repair submitted by dga471 to the `cpt` simplification in `splitKer_of_allRat`. The PR’s green check ran the job that compiles `Challenge`, the file stating the five exported theorems. The full-build workflow for consolidation commit `eb1bc40e` was skipped. Neither run establishes that the patched module or its downstream importers compile. [Repair PR #266](https://github.com/rohanarun/riemann-hypothesis/pull/266) · [Challenge job](https://github.com/rohanarun/riemann-hypothesis/actions/runs/45254295859/job/137971886317) · [Full-build workflow](https://github.com/leanprover-community/riemann-hypothesis/actions/runs/45253256543)

Both [PR #266](https://github.com/rohanarun/riemann-hypothesis/pull/266) and [PR #272](https://github.com/rohanarun/riemann-hypothesis/pull/272) merged into the consolidation branch on November 23, 2026. The later commit contains both edits. The 20:13 UTC tracker still listed their original diagnostics, so that snapshot supplies no successful post-merge build for either module. [Merged cpt line](https://github.com/rohanarun/riemann-hypothesis/blob/d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509/src/Development/AbelianVarietyTheory/Proofs/RingsOfIntegers/SplitKernelFormalGroupOfRationalTorsion.lean#L466) · [Merged matrix rewrites](https://github.com/rohanarun/riemann-hypothesis/blob/d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509/src/Development/AbelianVarietyTheory/Proofs/FlagMeasures/ExistsIsometryOfUnimodularLatticesAtPlace.lean#L182-L186) · [Pinned tracker](https://github.com/rohanarun/alpoge-rh-replay/blob/5aca8ca21aefde932a079f94f07e4062b0dfe615/PR120-BUGS.md)

## Complete dependencies checked locally

The reduced test uses the affine spectrum abbreviation `Sp`, the multivariable power series type `PS` and the point type `Pt`. We built and kernel-replayed the entire upstream module that defines them, `ToroidalCompactification.Bundle0001`, using the unchanged source file from the consolidation commit. It imports Mathlib. Both commands exited 0, and the build produced linter and deprecation warnings. The two competing `cpt` definitions live in other modules. [Pinned source](https://github.com/rohanarun/riemann-hypothesis/blob/eb1bc40eb455decc150131a2f2fca72c72ae3a2d/src/ReciprocityTheory/ReductiveGroups/ArithmeticGeometry/BirationalGeometry/ToroidalCompactification/Bundle0001.lean) · [Compiler and replay output](toroidal-bundle.txt)

| Item | SHA |
| --- | --- |
| Candidate revision | `eb1bc40eb455decc150131a2f2fca72c72ae3a2d` |
| Lean compiler | `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9` (4.36.0) |
| Mathlib | `fc4f59e577feb1a4956671bc04ac18aaaf8cd842` |
| Source file (SHA-256) | `14f327877609b297a7747064c2af5a344b05105928b7e0487b28bdd38220a1d3` |
| Compiled .olean in this run (SHA-256) | `d1afa5c92b28bc7758d48b399b59c638dd0b61ca2d27a113b5dc3870ee74e4e1` |

Run in a checkout of the candidate revision with its pinned Lean and Mathlib. The final command replays the named module against its installed dependencies. Lake’s job count includes cached dependency work.

```bash
lake exe mathlib/cache get
module=ReciprocityTheory.ReductiveGroups.ArithmeticGeometry.BirationalGeometry.ToroidalCompactification.Bundle0001
lake build "+${module}:olean"
lake env leanchecker --verbose "$module"
```

The other complete dependency we built and kernel-replayed is `Development.AbelianVarietyTheory.Proofs.FormalGroupCharts.Bundle0001`. The repaired module imports it directly. We ran the same two commands with this module name after all timings finished, on the same pinned consolidation revision. Its complete source is also the input to the [six-file timing comparison](../benchmark/README.md). [Compiler and kernel replay output](formal-group-bundle.txt)

## Outstanding target

The next integration check is on the merged consolidation revision `d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509`. In that checkout with its matching dependencies, run the following to build the patched module and its two direct importers. These commands describe the outstanding check. The two transcripts above cover the named dependencies. [Patch revision](https://github.com/rohanarun/riemann-hypothesis/pull/266/files)

```bash
prefix=Development.AbelianVarietyTheory.Proofs.RingsOfIntegers
lake build "+${prefix}.SplitKernelFormalGroupOfRationalTorsion:olean" \
           "+${prefix}.SumHvPrimaryKernel:olean" \
           "+${prefix}.SumHarmonicValuesFormalKernelSimilitude:olean"
```
