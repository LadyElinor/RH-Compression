# Six source files versus one Lean bundle

With one compiler process at a time, six formal-group modules took **18.84 seconds on average** to compile separately. The consolidated module took **6.20 seconds**. That is **67.1% less elapsed compiler time** over four paired comparisons. Peak memory for a single compiler process ranged from 3.35 to 3.42 GiB across all eight observations. The bundle used more peak memory in three of the four pairs.

The benchmark uses `Development.AbelianVarietyTheory.Proofs.FormalGroupCharts.Bundle0001`, a direct import of the module repaired in PR #266. We chose it because its six constituents all import only Mathlib and their complete, unchanged proof bodies fit on this machine. This selection favors a case where bundling can save repeated compiler startup and import work. [Consolidated source](https://github.com/rohanarun/riemann-hypothesis/blob/eb1bc40eb455decc150131a2f2fca72c72ae3a2d/src/Development/AbelianVarietyTheory/Proofs/FormalGroupCharts/Bundle0001.lean) · [Original source directory](https://github.com/rohanarun/riemann-hypothesis/tree/c7791603122c0328f79e49f6be5d7d4402effc53/src/Development/AbelianVarietyTheory/Proofs/FormalGroupCharts) · [Consolidation by Rohan Arun and contributors](https://github.com/leanprover-community/riemann-hypothesis/pull/120)

| Run and order | Six files, seconds | Bundle, seconds | Time saved | Six files, peak GiB | Bundle, peak GiB |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1, six first | 18.47 | 6.21 | 66.4% | 3.364 | 3.393 |
| 1, bundle first | 18.93 | 6.58 | 65.2% | 3.364 | 3.349 |
| 2, six first | 21.07 | 6.14 | 70.8% | 3.384 | 3.416 |
| 2, bundle first | 16.90 | 5.88 | 65.2% | 3.385 | 3.416 |

Each run started with one untimed Mathlib import. For each comparison every measured source compiled in a fresh Lean process, with one compiler thread and a fresh output directory. The original sources required six invocations and the bundle required one. Elapsed time is summed across the serial invocations. Peak memory is the largest Linux child-process resident set size in each group. The overall time saving is calculated from the unrounded totals, 75.3673 and 24.8110 seconds. [First run](measurements.json) · [Repeat with freshly downloaded source](replication.json)

After both layouts were already built, one edit to `FlatMvPowerSeries` took 8.18 seconds on average to rebuild separately and 9.39 seconds in the bundle. [One-edit Lake benchmark and measurements](incremental.md)

## What these measurements establish

This bundle saves time in a serial build with compiled Mathlib dependencies available. The measurements include compiler startup, import loading, elaboration and writing Lean module artifacts. They exclude downloading dependencies, Lake scheduling, native compilation, linking and kernel replay. Both runs used the same Linux x86-64 workspace (AMD EPYC 9V45, 9.7 GiB reported memory). The host can have other workloads.

A parallel Lake build can overlap some of the six independent compilations and can hold several compiler processes in memory at once. Estimating the full project's wall time and peak memory therefore requires a separate benchmark with the same concurrency, cache state and hardware on each revision. This experiment supplies one measured example for that broader comparison. [Project build and verification](https://github.com/leanprover-community/riemann-hypothesis/pull/120)

## Reproduce

Run the following from this repository's root on Linux with Git, Python 3 and elan installed.

```bash
lake exe mathlib/cache get
lake env python3 benchmark/run.py --output /tmp/rh-bundle-timings.json
```

The runner fetches only the seven source files, verifies their hashes and reconstructs the entire candidate file byte for byte from the six original bodies plus the bundler’s headers and section wrappers. Alternatively, pass `--original /path/to/original --candidate /path/to/candidate` for local copies of those revisions. The original commit and candidate use byte-identical Lean toolchain, Lake configuration and dependency manifest files. Both use Lean 4.36.0 and Mathlib commit `fc4f59e577feb1a4956671bc04ac18aaaf8cd842`. The output contains per-process times and peak memory, revisions, compiler options and trial order. [Benchmark script](run.py) · [Pinned source paths and hashes](inputs.json)
