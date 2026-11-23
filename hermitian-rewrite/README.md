# Which Hermitian identity supports the cast?

Two upstream lemmas both evaluate the Hermitian pairing with the identity matrix. One writes the result as a finite sum. The other writes it as `stdForm x y`, the name appearing in the hypothesis that an algebraic integer equals the pairing. The next Lean proof step transports integrality across that equality using `▸`. With the expanded sum in its goal, Lean reports that the equality contains neither side of the expected cast. Giving the rewrite the named standard form lets the original cast go through. [Failure at the pinned source line](https://github.com/rohanarun/riemann-hypothesis/blob/d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509/src/Development/AbelianVarietyTheory/Proofs/RingsOfIntegers/Bundle0046.lean#L69-L75) · [dga471’s PR #287](https://github.com/rohanarun/riemann-hypothesis/pull/287)

The reduced theorem keeps the actual ring of integers of a CM number field, complex conjugation, the matrix pairing, and both directions of the equivalence at issue. The two `herm_one` identities are proved in the fixture. The before and after files differ in the name of the rewrite lemma alone. The surrounding existence theorem and its lattice hypotheses are outside this test. [Definitions and identities](HermForms.lean) · [Before](CastBefore.lean) · [After](CastAfter.lean)

## Where the failure occurs

At the pinned merged revision, both direct importers of the PR #266 target reach `RingsOfIntegers.Bundle0046`. The target `SplitKernelFormalGroupOfRationalTorsion` has no import path to this bundle. All entries below are in `Development.AbelianVarietyTheory.Proofs.RingsOfIntegers`.

| Importer | Shortest path from the importer to the affected file |
| --- | --- |
| `SumHvPrimaryKernel` | `Bundle0047` → `Bundle0046` |
| `SumHarmonicValuesFormalKernelSimilitude` | `ExistsTranslateUnitSymmetricFormalGroupPoint` → `Bundle0049` → `Bundle0047` → `Bundle0046` |

The source tracker listed the cast error for this file, and its source still uses the original rewrite on that revision. The local test isolates the failing expression. Certification of either complete importer requires a build of that importer. [Pinned tracker](https://github.com/rohanarun/alpoge-rh-replay/blob/5aca8ca21aefde932a079f94f07e4062b0dfe615/PR120-BUGS.md) · [Merged revision](https://github.com/rohanarun/riemann-hypothesis/tree/d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509/src/Development/AbelianVarietyTheory/Proofs/RingsOfIntegers)

## Reproduce

From the repository root, run the following with the pinned Lean toolchain.

```bash
lake exe mathlib/cache get Mathlib.NumberTheory.NumberField.CMField Mathlib.Data.Matrix.Basic
bash hermitian-rewrite/check.sh
```

The script checks the original diagnostic, compiles the changed theorem, replays both local modules through Lean’s kernel checker, and checks the three reported axioms. [Recorded output](verification.txt)

## Credits

The mathematical definitions and lemma statements follow Levent Alpöge’s formalization as organized by Rohan Arun’s consolidation project. dga471 submitted the rewrite used here. LadyElinor’s project used OpenAI Codex to construct and run the independent check. [Hermitian pairing and conjugation](https://github.com/rohanarun/riemann-hypothesis/blob/d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509/src/ReciprocityTheory/ReductiveGroups/ArithmeticGeometry/FundamentalDomains/Bundle0001.lean#L217-L220) · [Standard form](https://github.com/rohanarun/riemann-hypothesis/blob/d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509/src/Development/AbelianVarietyTheory/BlockTheory/ExistenceTori/Bundle0003.lean#L26) · [Expanded identity](https://github.com/rohanarun/riemann-hypothesis/blob/d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509/src/Development/AbelianVarietyTheory/Definitions/SpanningFamilies/FirstCoordinateAdmissible.lean#L319) · [Named identity](https://github.com/rohanarun/riemann-hypothesis/blob/d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509/src/Development/AbelianVarietyTheory/Proofs/UnitaryExistence/FiniteNotIsUnitOneAddSmul.lean#L386)
