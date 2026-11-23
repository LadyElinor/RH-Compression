# Reusing a compiled dependency on the merged branch

`RankLin` is in the import closure of the PR #266 target and imports only Mathlib. Its source and Lean, Mathlib and Lake configuration are identical in the original 4.36 reference and the merged candidate. Stock Lake calculates the same module input hash, `e74cb022a4054f6b`. This permits the older public cache to supply this one module. [Candidate source](https://github.com/rohanarun/riemann-hypothesis/blob/d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509/src/ReciprocityTheory/ReductiveGroups/ArithmeticGeometry/BirationalGeometry/ToroidalCompactification/RankLin.lean) · [Matching original source](https://github.com/rohanarun/riemann-hypothesis/blob/c7791603122c0328f79e49f6be5d7d4402effc53/src/ReciprocityTheory/ReductiveGroups/ArithmeticGeometry/BirationalGeometry/ToroidalCompactification/RankLin.lean)

The check uses the module index pinned by the upstream cache configuration. It checks the index digest, asks Lake for the candidate’s module input hash, and downloads the corresponding 42,698-byte output archive. After verifying its SHA-256, it restores the archive into a fresh checkout, asks Lake to accept the compiled module with rebuilding disabled, and replays that module with Lean’s kernel checker. It reuses the caller’s prepared Mathlib dependencies. [Upstream cache pins](https://github.com/rohanarun/riemann-hypothesis/blob/d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509/scripts/cache-baselines.json) · [Recorded run](receipt.txt)

Run from the root of RH-Compression with Python 3, Git, curl and the pinned Lean 4.36.0 tools on PATH. Supply an upstream checkout containing commit `d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509` with its Mathlib cache already prepared.

```bash
python3 upstream-checks/cache-reuse/verify.py /path/to/riemann-hypothesis
```

The check establishes reuse for this dependency. Each further candidate module needs its own matching Lake input and verified output archive.
