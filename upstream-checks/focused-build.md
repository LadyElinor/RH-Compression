# Building the repaired module on its own

We resumed the existing Lean 4.36.0 checkout at `d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509` with its pinned Mathlib and requested the complete `SplitKernelFormalGroupOfRationalTorsion` module. We first built six of its eleven immediate project imports as a group. Lake completed all six and subsequently accepted all six with rebuilding disabled. Lean’s kernel then replayed the declarations in each of the six modules successfully. The group added 45 compiled modules to the checkout. The [run record](focused-build.json) includes the source and `.olean` digests and individual kernel replay results. Each successful default `leanchecker` replay checks the named module's declarations in its imported environment. [Pinned list of direct imports](https://github.com/rohanarun/riemann-hypothesis/blob/d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509/src/Development/AbelianVarietyTheory/Proofs/RingsOfIntegers/SplitKernelFormalGroupOfRationalTorsion.lean#L3-L14)

The complete target covers 10,185 project modules including itself. One direct import, `RingsOfIntegers.Bundle0045`, accounts for the other 10,184. At the start, 409 artifacts were present. The full-target check with rebuilding disabled exited 3. We then ran the stock build with a 100-second diagnostic limit while other kernel replays ran. Lake reported two additional modules built before the time limit interrupted the command. At that point 456 project `.olean` files were present in the closure and 9,729 were still absent, including the target. That run produced no compiler diagnostic identifying a failed proof. The earlier three-target log had reached 325 distinct completed modules beyond its initial state. It contains no concluding Lake result.

The older `c779160` cache indexes 5,529 names in this particular closure. Comparing their original Git source blobs recursively gives 872 names with matching sources and indexed dependencies, of which 788 were missing locally at the start. This prefilter still leaves 8,988 missing artifacts outside its scope. Successful reuse of an individual artifact additionally requires Lake to accept its input trace. The two error entries in the pinned coordinator table for this closure refer to bare `cpt` expressions. At each cited line the pinned source already qualifies `GlobalTheory.PlaceInt.cpt`. [Coordinator table](https://github.com/rohanarun/alpoge-rh-replay/blob/5aca8ca21aefde932a079f94f07e4062b0dfe615/PR120-BUGS.md) · [Cache comparison method](README.md#integration-build-on-the-merged-revision)

## Which checks carry forward to PR #120?

On November 23 we compared the locally tested revision `d4e7aaaa` with PR #120 at `8d493853`. The latter was 84 commits ahead. All 52 changed paths were existing Lean source files. The Lean toolchain, Lake configuration and dependency manifest were unchanged. [Pinned revision comparison](https://github.com/rohanarun/riemann-hypothesis/compare/d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509...8d4938534bb96a38bd646569fa37a81e542d8ba2)

| Target | Project sources including the target | Changed sources in that set |
| --- | ---: | ---: |
| `SplitKernelFormalGroupOfRationalTorsion` | 10,185 | 0 |
| `SumHvPrimaryKernel` | 18,278 | 23 |
| `SumHarmonicValuesFormalKernelSimilitude` | 18,273 | 23 |

We followed project imports recursively in the tested checkout, matched module names to their files under `src/`, and intersected each set with the paths changed between the two revisions. The two downstream modules share the same 23 changed prerequisites. The six direct imports that passed kernel replay on the older revision each had zero changed files in their own project dependencies. [Per-module results and changed paths](revision-comparison.json)

The six compiled outputs are candidates for reuse. Lake still has to accept their input traces on the newer checkout. The repaired module itself has no recorded full build or replay in our study. After it builds, the two downstream modules require their own current-revision checks. [Public project summary](https://four-primes.owonm.chatgpt.site/lean-verification.html)

## Disk use on a small machine

At an intermediate checkpoint, 454 compiler setup JSON files occupied 2,412,287,188 bytes of file contents, with a median size of 5,335,700 bytes. They record paths for transitive import artifacts. For example, the setup for `RingsOfIntegers.Bundle0003` names 9,128 inputs and takes 5,341,264 bytes. We moved this one completed module's setup aside. Stock `lake --no-build` accepted its `.olean` and left the setup file absent. We restored the file and verified that its SHA-256 and the `.olean` SHA-256 matched their original values. This test covers a warm `.olean` check for one module. Native compilation, interrupted compiles, and other Lake facets need their own tests. [Lake's setup writer](https://github.com/leanprover/lean4/blob/611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9/src/lake/Lake/Build/Actions.lean#L66-L68)

Copying the sampled module's 4,951,486-byte compact Mathlib path map into 7,186 missing files that directly import Mathlib would take about 35.6 GB, before proof outputs. The checkout had about 33.3 GB free. This is a projection for this path layout and encoding. A reversible storage experiment is to compress completed setup records between runs and restore each on demand. The timing of the 100-second probe included startup and competing work, so it gives no reliable completion time.

In a later read-only pass we compressed each of the 457 `*.setup.json` files in `.lake/build/ir` separately with Python's `gzip.compress(data, compresslevel=1, mtime=0)`. Their combined file contents fell from 2,428,286,062 bytes to 113,071,707 bytes, a **95.34% reduction**. Every file decompressed to exactly its original bytes. This measures the space required to archive completed setup files. Build time and peak RAM would require a separate comparison using a build that manages those archives. The [run record](focused-build.json) includes the runtime versions and a digest over the sorted input paths and their contents.

To resume on the same pin, retain the checkout, its pinned packages, and `.lake/build` and run the following in the repository root with its Lean toolchain. The final command should run only after the build exits successfully.

```sh
module=Development.AbelianVarietyTheory.Proofs.RingsOfIntegers.SplitKernelFormalGroupOfRationalTorsion
lake --no-ansi --fail-fast build "+${module}:olean" && lake env leanchecker --verbose "$module"
```
