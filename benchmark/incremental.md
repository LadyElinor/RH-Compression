# Rebuilding after one proof edit

After a one-line proof edit, the six-file layout rebuilt in **8.18 seconds** on average. The consolidated layout took **9.39 seconds**, an extra **1.21 seconds (14.7%)** across four paired comparisons. Lake rebuilt one local module each time. In the separate layout, that module contained the edited proof. In the bundle it contained all six original proof bodies.

| Pair and order | Edit | Six files, seconds | Bundle, seconds | Six files, peak GiB | Bundle, peak GiB |
| --- | --- | ---: | ---: | ---: | ---: |
| 1, six first | Apply | 8.39 | 9.73 | 3.700 | 3.799 |
| 2, bundle first | Revert | 8.18 | 9.43 | 3.711 | 3.813 |
| 3, bundle first | Apply | 7.84 | 9.35 | 3.707 | 3.804 |
| 4, six first | Revert | 8.33 | 9.07 | 3.699 | 3.808 |

The no-change builds took 5.93 seconds for six files and 6.31 seconds for the bundle. Neither rebuilt a module or started a sampled compiler. The table reports full command wall time without subtracting either control. Peak GiB is the largest sampled sum of resident memory across Lake and its descendants. Each edit had one observed compiler process. [Individual observations](incremental-results.json)

In the [fresh serial compiler benchmark](README.md), building all six proof bodies favored consolidation. Here, after an edit to this one member, five separate modules could reuse their existing outputs. The two studies time different commands and workloads. A full-project estimate would need to include downstream imports and additional bundles.

## The edit

We changed line 29 of `FlatMvPowerSeries.lean` in the proof of `GlobalTheory.PowerSeriesFlat.flat_pi`. The identical edit appears in the consolidated file. Lean’s identity function returns the same proof and the theorem statement stays the same. [Original line](https://github.com/rohanarun/riemann-hypothesis/blob/c7791603122c0328f79e49f6be5d7d4402effc53/src/Development/AbelianVarietyTheory/Proofs/FormalGroupCharts/FlatMvPowerSeries.lean#L29) · [Consolidated source](https://github.com/rohanarun/riemann-hypothesis/blob/eb1bc40eb455decc150131a2f2fca72c72ae3a2d/src/Development/AbelianVarietyTheory/Proofs/FormalGroupCharts/Bundle0001.lean)

```diff
-    exact (Submodule.mem_span_range_iff_exists_fun T).1 hm
+    exact id ((Submodule.mem_span_range_iff_exists_fun T).1 hm)
```

## Measurement

Each layout used its own temporary Lake project. The separate layout contained all six pinned modules, the consolidated layout their pinned bundle. Each proof file imports Mathlib. Both layouts used the same precompiled Mathlib dependencies, Lean 4.36.0 and project elaboration options. Lake was asked to build the `olean` target of every module in the layout in a single command.

We first built all seven local targets, then measured one build with no changes in each layout. For four paired comparisons we alternately applied and reverted the edit. Both directions ran once in each layout order. The runner checks Lake's report of newly built modules and the modification time of every target's `.olean` file. The machine had an AMD EPYC 9V45 processor and 9.7 GiB reported RAM. We set `LEAN_NUM_THREADS=1` for every invocation.

Elapsed time includes Lake startup, dependency traversal, elaboration and the writing of module artifacts. The runner sampled all resident memory in Lake's process group, including the compiler, with a 25 ms pause between samples. It also recorded the sum for compiler processes alone. Short peaks can fall between samples, and shared pages count once per resident process. The command excludes native linking, kernel replay and modules elsewhere in the proof that import these targets.

## Reproduce

On Linux, use the repository's Lean toolchain and compiled Mathlib cache, then run from the repository root.

```sh
lake exe mathlib/cache get Mathlib
lake env python3 benchmark/incremental.py --output /tmp/rh-incremental.json
```

Use `--original /path/to/original --candidate /path/to/candidate` for local source. Otherwise the runner downloads the seven pinned files. Each source is checked against its SHA-256 digest before the baseline build. [Source commits and hashes](inputs.json) · [Runner](incremental.py) · [Raw results](incremental-results.json)
