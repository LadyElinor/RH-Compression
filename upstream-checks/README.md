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

## Integration build on the merged revision

We requested the three named modules together on a clean source checkout of `d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509`, with pinned Mathlib and the two previously verified dependency builds. The first target has 10,185 distinct project modules in its transitive import tree, including itself. The two importers have 18,278 and 18,273 respectively, with 18,278 across the combined request. These counts exclude Mathlib and Lean's own modules. At 20:42 UTC the running three-target command had reported 178 distinct prerequisite modules built. None of the three requested output files existed at that checkpoint. [Timestamped local build record](integration-checkpoint.json)

We separately built the complete `ToroidalCompactification.ToStkAInjective` module on the merged sources and replayed it with Lean’s kernel. This is the actual file defining the competing closed-point `cpt` from PR #266’s error. Its import tree contains 83 project modules, including itself. After incorporating the dependency artifacts in the merged checkout, Lake accepted this target with rebuilding disabled. This check reaches the competing definition. The full `splitKer_of_allRat` proof remains a separate target. [Build and replay record](closed-point-replay.txt) · [Source of the closed-point definition](https://github.com/rohanarun/riemann-hypothesis/blob/d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509/src/ReciprocityTheory/ReductiveGroups/ArithmeticGeometry/BirationalGeometry/ToroidalCompactification/ToStkAInjective.lean#L22)

Both importers also depend on `RingsOfIntegers.Bundle0046`. Its reported cast error reproduces on this revision in a small Lean test. Selecting the standard-form identity from dga471’s PR #287 makes the same cast compile and pass kernel replay. This issue lies outside the first target’s import tree. [Reproduction, paths and source credits](../hermitian-rewrite/README.md)

The GitHub job at the merged revision compiled `Challenge` alone, and the community full-build workflow skipped its proof jobs. The publicly available first-build shard logs predate the fixes. The pinned older baseline manifest lacks 8,346 of the 18,278 required module names, so it cannot supply all artifacts. Comparing original Git source blobs across the 18,278-module tree gave 3,566 identical files and only 1,218 with identical source throughout their project dependencies. These are candidates for reuse. Each still requires its own Lake input check. [Merged-revision job](https://github.com/rohanarun/riemann-hypothesis/actions/runs/45257114980/job/137981734451) · [Community workflow](https://github.com/leanprover-community/riemann-hypothesis/actions/runs/45257138517) · [Earlier shard logs](https://github.com/rohanarun/alpoge-rh-replay/tree/841acaf4bb30c7133a6ffe6efbb3e77ad67bde29/evidence/pr120-first-build) · [Older cache index](https://rh-cache.taucetiproject.org/ci/revisions/c7791603122c0328f79e49f6be5d7d4402effc53.json)

We verified one reusable dependency end to end. On the merged checkout, Lake computed the same input hash for `RankLin` as the older public cache. After we checked the archive digest and restored it to a fresh project output directory, stock Lake accepted the cached module and Lean replayed it. [Verifier and output](cache-reuse/README.md)

### Checking a producer's module records

When a build host supplies its `receipt.json` and `module-manifest.jsonl.gz`, this command checks the pinned source and configuration identity, verifies the manifest hash, and reports an individual result for each of the three targets.

```bash
python3 upstream-checks/check_receipt.py receipt.json module-manifest.jsonl.gz
```

If you have a SHA-256 for the receipt from an independent source, pass it with `--receipt-sha256`. Exit code 0 means that the manifest lists all three outputs, 3 means at least one is absent, and 2 means the evidence failed validation. A partial build can contain useful completed outputs. A listed output still needs its actual artifact and a kernel replay for independent verification. The included tests exercise missing records, altered metadata and a partial build that lists all three targets. [Checker](check_receipt.py) · [Tests](test_check_receipt.py) · [Producer format](https://github.com/rohanarun/riemann-hypothesis/blob/d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509/scripts/ci-build.py#L947-L984)

## Outstanding target

The integration attempt uses the merged consolidation revision `d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509`. In that checkout with its matching dependencies, run the following to build the patched module and its two direct importers. The local build was launched with these targets and `--fail-fast`. The transcripts linked above cover the individual dependencies. [Patch revision](https://github.com/rohanarun/riemann-hypothesis/pull/266/files)

```bash
prefix=Development.AbelianVarietyTheory.Proofs.RingsOfIntegers
lake build "+${prefix}.SplitKernelFormalGroupOfRationalTorsion:olean" \
           "+${prefix}.SumHvPrimaryKernel:olean" \
           "+${prefix}.SumHarmonicValuesFormalKernelSimilitude:olean"
```
