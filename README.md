# RH Compression

This repository records independent Lean checks for the effort to consolidate the formalization published by Levent Alpöge. The checks below cover repairs submitted by **dga471**, two full upstream dependencies, and the cost of compiling six original modules separately or as one bundle. [Original source](https://alpo.ge/remark.pdf) · [Rohan Arun’s consolidation PR #120](https://github.com/leanprover-community/riemann-hypothesis/pull/120) · [dga471’s repair, PR #266](https://github.com/rohanarun/riemann-hypothesis/pull/266)

## Results

| Study | What the test covers |
| --- | --- |
| [Six files versus one bundle](benchmark/README.md) | Timings and peak process memory from four paired comparisons of the same proof bodies under Lean 4.36.0. |
| [Matrix rewrites in PR #272](matrix-rewrite/README.md) | Two failures reproduce in isolation. Both repaired algebraic steps compile and pass kernel replay. |
| [Hermitian-form rewrite in PR #287](hermitian-rewrite/README.md) | Reproduces a failure in a shared prerequisite of the two PR #266 importers and kernel-checks the proposed one-line repair. |
| [Extent of upstream verification](upstream-checks/README.md) | Two complete upstream dependencies compiled and passed kernel replay. The record identifies the remaining full-module check for PR #266. |

## Why one name broke the build

Inside `splitKer_of_allRat`, the proof needs the constant coefficient of a constant power series. The intended `GlobalTheory.PlaceInt.cpt` maps each coordinate to its constant power series. Consolidation exposed a second `cpt` that selects the closed point of a local ring’s spectrum. In the expression with arguments, Lean has enough type information to select the intended definition. In the simplifier’s list `[cpt]`, Lean selects the closed-point definition and reports an invalid simplification theorem. [Original proof step](https://github.com/rohanarun/riemann-hypothesis/blob/eb1bc40eb455decc150131a2f2fca72c72ae3a2d/src/Development/AbelianVarietyTheory/Proofs/RingsOfIntegers/SplitKernelFormalGroupOfRationalTorsion.lean#L465-L466)

```diff
-      fun b i => by simpa [cpt] using hα.1 b i
+      fun b i => by simpa [GlobalTheory.PlaceInt.cpt] using hα.1 b i
```

The test retains the two definitions, the constant-coefficient goal and the hypothesis it uses. It replaces an unused conjunct with `True` and omits the surrounding number-field construction. This lets contributors check the failure using cached Mathlib on a machine without the RH project build. [Before](reproduction/Before.lean) · [After](reproduction/After.lean) · [Definitions](reproduction/Contributions.lean) · [Patch against the pinned project source](reproduction/qualify-cpt.patch)

## Run the check

From a checkout of this repository, with Git, Bash and [elan](https://github.com/leanprover/elan) installed, run the following. The first command downloads compiled Mathlib dependencies. Allow disk space for the Lean toolchain and Mathlib cache.

```bash
lake exe mathlib/cache get Mathlib.AlgebraicGeometry.Scheme Mathlib.RingTheory.MvPowerSeries.Basic
bash check.sh
```

The test expects the original proof to fail with the closed-point diagnostic. It then builds the corrected theorem, replays both local modules with Lean’s kernel checker, and checks that the theorem reports exactly the three expected Lean axioms. [Recorded output](reproduction/verification.txt)

| What was checked | Evidence |
| --- | --- |
| Source revision | Candidate commit `eb1bc40eb455decc150131a2f2fca72c72ae3a2d`; the patch applies at line 466 with `git apply --check --unidiff-zero` in that checkout. |
| Toolchain | Lean 4.36.0, commit `611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9`; Mathlib `fc4f59e577feb1a4956671bc04ac18aaaf8cd842`. |
| Reduced theorem | The unqualified line produces the reported error. The qualified line compiles and its proof passes kernel replay. |
| Full consolidated RH proof | This run covers the reduced theorem only. Checking the original module, its importers, and the five exported theorems requires the corresponding upstream build and theorem comparison. |

PR #120 reports a reduction from 149,396 to 47,884 Lean source files. Measuring compile time and peak memory requires comparable builds on the same hardware, toolchain and cache settings. The [six-file timing study](benchmark/README.md) measures one bundle under a serial compiler workload. [Upstream consolidation and verification](https://github.com/leanprover-community/riemann-hypothesis/pull/120) · [Project contributor guide](https://github.com/rohanarun/alpoge-rh-replay/blob/main/auto-research.md)

## Source credits

Levent Alpöge published the original formalization. Rohan Arun and the consolidation contributors maintain the candidate. **dga471** submitted the simplifier and matrix repairs. LadyElinor’s project used OpenAI Codex to run the independent proof checks and timing comparison. It uses the Lean compiler and the Mathlib community’s algebraic geometry and power series libraries.

The local declarations are adapted from the following files in the pinned candidate.

- [Constant power series and the smallness predicate](https://github.com/rohanarun/riemann-hypothesis/blob/eb1bc40eb455decc150131a2f2fca72c72ae3a2d/src/Development/AbelianVarietyTheory/Definitions/PlaceAdaptation/AdaptStd.lean#L31-L33).
- [Closed point of a local ring’s spectrum](https://github.com/rohanarun/riemann-hypothesis/blob/eb1bc40eb455decc150131a2f2fca72c72ae3a2d/src/ReciprocityTheory/ReductiveGroups/ArithmeticGeometry/BirationalGeometry/ToroidalCompactification/ToStkAInjective.lean#L22).
- [Power series and point types](https://github.com/rohanarun/riemann-hypothesis/blob/eb1bc40eb455decc150131a2f2fca72c72ae3a2d/src/ReciprocityTheory/ReductiveGroups/ArithmeticGeometry/BirationalGeometry/ToroidalCompactification/Bundle0001.lean#L136-L140) and [the affine spectrum abbreviation](https://github.com/rohanarun/riemann-hypothesis/blob/eb1bc40eb455decc150131a2f2fca72c72ae3a2d/src/ReciprocityTheory/ReductiveGroups/ArithmeticGeometry/BirationalGeometry/ToroidalCompactification/Bundle0001.lean#L359-L365).
