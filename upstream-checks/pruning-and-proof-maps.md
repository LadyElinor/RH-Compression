# How the other RH projects connect to our three modules

Rohan Arun's November 21 announcement points to merged PR #45. Trimming unused top-level imports made 11,163 source files unreachable, or 6.37% of the source tree at that stage. He proposed doing that pruning on Lean 4.33 before porting the surviving modules to 4.36. PR #120 later consolidated modules into bundles on the 4.36 branch. The two percentages refer to different operations and revisions. [Rohan Arun's post](https://x.com/rohanarun/status/2124247822228656289) · [Merged pruning PR #45](https://github.com/leanprover-community/riemann-hypothesis/pull/45) · [Consolidation PR #120](https://github.com/leanprover-community/riemann-hypothesis/pull/120)

## Graphs for different questions

In the Lean Zulip thread, **shorya** asked to see a dependency graph of the entire proof. Simon DeDeo linked a graph of Lean declaration dependencies. Yaroslav Kharkov shared the DeepTheory visualizations, and Rohan Arun and Bartosz Naskręcki linked the Riemann Proof Atlas. These maps let a reader explore which mathematical statements depend on earlier ones. Our counts of 10,185 or 18,278 refer to source modules reached through import statements on one particular consolidation revision. A module can import many declarations that an individual theorem never uses. [Zulip question](https://leanprover.zulipchat.com/#narrow/channel/113488-general/topic/Discussion.3A.20Alp.C3.B6ge.20Proves.20the.20Riemann.20Hypothesis/near/642525425) · [DeDeo’s dependency graph](https://proofsandreasons.io/rh-graph.html) · [Kharkov’s 3D visualization](https://deeptheory-labs.github.io/GRH/blueprints/threejs-original/full.html) · [Naskręcki’s atlas](https://nasqret.github.io/riemann-proof-atlas/)

## What rh-trim checked

Keith Adler's 20:33 UTC status snapshot on November 23 reports that the byte-exact original Lean 4.33.1 source built. Exporting the dependencies of its five main theorems produced 1,468,414 declarations, with the three standard Lean axioms. Tenet (C#), nanoda and tenet-jvm each reported acceptance of that same export. Adler's separate attempt to rebuild minified source was paused in round 69 with errors still reported. The source build, export replay and minified rebuild are three separate results. [Pinned status](https://github.com/keithadler/rh-trim/blob/e63c01e857edceb2cdf98ed3adee46028a6f10ad/BUILD-STATUS.md) · [Source of the original formalization](https://alpo.ge/remark.pdf) · [Joint Lean FRO and Mathlib Initiative statement about the original proof](https://leanprover-community.github.io/blog/posts/riemann-hypothesis/)

Adler’s first two pruning rounds illustrate why the compiler still matters. Removing declarations outside the final proof terms also removed dependencies needed by instances and names used by tactics. Our `cpt` reproducer shows the converse problem: bundling can bring an extra name into scope and change how a tactic interprets a proof line. A declaration graph can guide a proposed cut. A rebuild tests whether Lean can still read the edited source. [Minification rounds](https://github.com/keithadler/rh-trim/blob/e63c01e857edceb2cdf98ed3adee46028a6f10ad/BUILD-STATUS.md#step-5-building-the-smallest-proof) · [Our cpt reproducer](../reproduction/Before.lean)

## Matching module names across the projects

We looked up the three exact module names in Adler's published replay map. The IDs below identify entries in that map; their packets are for the earlier replay effort. The `reusable_from_replay` column is Adler's field for that stage. Its three values supply no compiled artifact for our merged Lean 4.36 revision. [Pinned replay map](https://github.com/keithadler/rh-trim/blob/e63c01e857edceb2cdf98ed3adee46028a6f10ad/data/replay-map.tsv.gz) · [Our merged-revision build check](README.md)

| Module under `Development.AbelianVarietyTheory.Proofs.RingsOfIntegers` | Replay ID | Packet | Reusable from replay |
| --- | --- | --- | --- |
| `SplitKernelFormalGroupOfRationalTorsion` | M086474 | P1597 | no |
| `SumHarmonicValuesFormalKernelSimilitude` | M086477 | P1947 | no |
| `SumHvPrimaryKernel` | M086479 | P1985 | no |

For contributors, the crosswalk makes older discussions searchable by module and packet ID. Checking the refactor still requires the matching inputs and compiled outputs on the consolidation branch. The SHA-256 of the compressed map read for this comparison was `f0f051665c2a515b7d991eb580f0321b81cb010845b49d1bcb46b688eb0ab954`.
