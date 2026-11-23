# Testing the two matrix rewrites in PR #272

An upstream proof of a statement about unimodular lattices uses a Gram matrix twice. Both steps need to turn a column multiplication into a row multiplication inside a scalar pairing. In dga471’s repair, `Matrix.dotProduct_mulVec` gives the identity
`c ⬝ᵥ (A *ᵥ w) = (c ᵥ* A) ⬝ᵥ w`. The first step can then use the hypothesis that the row vector kills the matrix. In the second, the rewritten product lets Lean cancel the inverse matrix and evaluate the chosen coordinate. [Upstream PR #272](https://github.com/rohanarun/riemann-hypothesis/pull/272) · [Original proof, lines 176–188](https://github.com/rohanarun/riemann-hypothesis/blob/eb1bc40eb455decc150131a2f2fca72c72ae3a2d/src/Development/AbelianVarietyTheory/Proofs/FlagMeasures/ExistsIsometryOfUnimodularLatticesAtPlace.lean#L176-L188) · [Repaired source](https://github.com/dga471/riemann-hypothesis/blob/0516da577ae482539238e38e7581a8acbe86cfda/src/Development/AbelianVarietyTheory/Proofs/FlagMeasures/ExistsIsometryOfUnimodularLatticesAtPlace.lean#L176-L188)

The two lemmas in this test begin after the upstream argument expresses the Hermitian form as a dot product. Both work over an arbitrary field, with the final vector written as `w`. Removing the inserted identity makes Lean report a missing rewrite pattern at each site. Restoring it makes both proofs compile and replay. The surrounding arithmetic, the Hermitian-form conversion, and the downstream lattice-membership argument lie outside this test. [Original rewrites](GramBefore.lean) · [Repaired rewrites](GramAfter.lean) · [Observed diagnostics and kernel replay](verification.txt)

## Reproduce

Run from the repository root with Bash and elan installed. The manifest pins Mathlib at `fc4f59e577feb1a4956671bc04ac18aaaf8cd842` and Lean at 4.36.0.

```bash
lake exe mathlib/cache get Mathlib.LinearAlgebra.Matrix.NonsingularInverse
bash matrix-rewrite/check.sh
```

The check requires the two observed failure patterns, checks that only the two rewrites changed, compiles the repaired module into a fresh temporary directory, and replays it with `leanchecker`. It also checks each lemma’s exact axiom report against `propext`, `Classical.choice`, and `Quot.sound`. LadyElinor’s project used OpenAI Codex to construct this independent test of dga471’s patch to Rohan Arun’s consolidation of Levent Alpöge’s formalization. [Consolidation PR #120](https://github.com/leanprover-community/riemann-hypothesis/pull/120) · [Mathlib’s matrix identity](https://github.com/leanprover-community/mathlib4/blob/fc4f59e577feb1a4956671bc04ac18aaaf8cd842/Mathlib/Data/Matrix/Mul.lean#L786)
