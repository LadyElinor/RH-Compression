# Archive completed Lean setup files

`manage.py` packs selected compiler setup files between Lake invocations. For module `A.B`, it reads `.lake/build/ir/A/B.setup.json` and binds the archive to the SHA-256 digests of `.lake/build/lib/lean/A/B.olean` and `A/B.trace`. It never writes the witnesses. Native `.irsetup.json` files, proof outputs and dependency traces remain in the build tree.

Use a private, idle workspace on Linux with Python 3.10 or later and a local filesystem that supports directory locks, hard links and directory fsync. Keep the setup directory and archive on the same filesystem. The manager accepts dotted module names up to 255 UTF-8 bytes and ordinary identifiers, including underscores and apostrophes. It requires singly linked setups owned by the running account and rejects symlinks, extended attributes and special mode bits. The operator selects modules from a **successful build**. The two witness files identify that build's outputs, but can also survive an interrupted later compile. A successful Lake check with rebuilding disabled provides an additional check before packing. The workspace lock serializes manager commands. Lake, editors and other writers do not acquire it.

## Try it in a disposable workspace

Run these commands from the repository root with the desired Lean release active. They build a copy of the included fixture. `plan` streams the actual inputs through the compressor without creating any files.

```bash
set -eu
manager="$(pwd -P)/setup-archive/manage.py"
toolbin="$(lean --print-prefix)/bin"
trial="$(mktemp -d)"
cp -R setup-archive/fixture "$trial/workspace"
cd "$trial/workspace"
export PATH="$toolbin:$PATH"

lake --no-cache build +ArchiveFixture:olean
lake --no-cache --no-build build +ArchiveFixture:olean
python3 "$manager" plan --workspace "$PWD" ArchiveFixture.Base ArchiveFixture.Left
python3 "$manager" pack --workspace "$PWD" ArchiveFixture.Base ArchiveFixture.Left
python3 "$manager" status --workspace "$PWD"
python3 "$manager" restore --workspace "$PWD" ArchiveFixture.Left
python3 "$manager" restore --workspace "$PWD"
lake --no-cache --no-build build +ArchiveFixture:olean
```

`plan` and `pack` require explicit module names. Restore can select individual modules, or expand all archives when called without names. Restore the setups that an upcoming edit or facet may regenerate. For an unfamiliar workload, restore all before starting Lake. For long-lived archives, keep `.lake/setup-archive-v1` with the matching workspace, including its witnesses.

## Restoration and interruption

Each module has a separate `setup.gz` and `receipt.json` under `.lake/setup-archive-v1/<module>/`. Compression uses gzip level 1, an empty filename and timestamp zero. The manager reads the compressed file back and verifies both compressed and decompressed sizes and SHA-256 digests. It flushes the archive to disk before unlinking the live setup. Restore verifies the witnesses and the payload, prepares the restored file with its recorded permissions, group and modification time, then publishes it atomically. An existing conflicting destination is preserved.

After an interruption, stop workspace writers and run the following with the same workspace and manager paths as above.

```bash
python3 "$manager" status --workspace "$PWD"
python3 "$manager" recover --workspace "$PWD"
```

`recover` rolls back to live setups across the workspace. A multi-module operation commits one module at a time, so earlier modules may have completed when a later one fails. Allow room for the expanded files. After a space-related failure, make additional space available and retry recovery. If Lake has regenerated a setup or changed a witness, keep both the archive and current build outputs. The diagnostic identifies the conflict. A retained copy of the original build can supply the matching witnesses for a separate recovery. A zero-byte marker and its containing directory remain after a full restore. For a regenerated module whose current build must continue, first preserve the entire old record directory with its receipt in a separate private location. Its standard gzip can also be expanded to a separate file and checked against the recorded setup digest. The receipts check local integrity and assume a trusted workspace.

## Reading the measurements

`payload_savings_bytes` subtracts gzip bytes from original bytes. `file_content_savings_bytes` also subtracts receipt bytes. Negative savings mean the archive is larger. The largest staging estimate includes the gzip, final receipt and temporary intent for one module. The restore estimate gives the largest expanded setup in the selection. Both count file contents. Restoring multiple modules also needs space for the files already restored. Filesystem block rounding and directory allocations affect the change in free disk space.

Run the regression suite and benchmarks from the repository root. Supply each installed release's real binary directory, containing `lean`, `lake` and `leanchecker`.

```bash
# Choose a scratch directory on the filesystem you intend to measure.
export TMPDIR="$(mktemp -d -p "$PWD" archive-trials.XXXXXXXX)"
reports="$(mktemp -d -p "$TMPDIR")"
python3 -B -m unittest discover -s setup-archive -p 'test_*.py'
python3 setup-archive/synthetic_benchmark.py --output "$reports/synthetic.json"
python3 setup-archive/benchmark.py --bin-dir "$(lean --print-prefix)/bin" \
  --pairs 2 --output "$reports/lean.json"
python3 setup-archive/import_breadth.py --bin-dir "$(lean --print-prefix)/bin" \
  --output "$reports/import-breadth.json"
```

The synthetic benchmark compares invented import maps against an untouched copy and reports wall time, per-process peak RSS and allocated workspace bytes. The Lean benchmark runs at the same path for each arm and restores the same initial tree for warm operations. It records Lake and archive operations separately, counts allocated blocks under `.lake` and samples total process-group RSS. Short-lived peaks can fall between samples, and shared pages can count once per process. These fixtures measure the listed toolchains and operations. The upstream RH build and its full set of native targets still require a separate end-to-end comparison.

The November 23 study measured compressed payload bytes for 457 real setup files. Its 35.6 GB figure projected future raw setup contents. Neither number measures the full project's disk high-water mark with this manager. [Original study](../upstream-checks/focused-build.md) · [Original run record](../upstream-checks/focused-build.json)

## Measurements on the disposable workspaces

All recorded trials used ext4. The two Lean releases used the same four-module source fixture with four worker threads. Each release ran two stock/managed pairs in alternating order for six scenarios, plus four trials that started Lake with every completed setup archived. The dependency-free fixture uses local imports and the Lean distribution. It requires no Mathlib cache.

| Storage experiment | Live setup contents | Packed file contents including receipts | Change in allocated workspace bytes while packed |
| --- | ---: | ---: | ---: |
| 12 synthetic import maps | 17,676,588 B | 1,038,374 B | 16,510,976 B saved |
| Four compiled modules, 4.36.0 | 1,385 B | 2,635 B | 36,864 B more |
| Four compiled modules, 4.37.0-rc1 | 1,385 B | 2,637 B | 36,864 B more |
| One compiled module with 128 local imports, 4.36.0 | 21,136 B | 1,415 B | 8,192 B saved |

For the synthetic maps, the dry run predicted the exact gzip and receipt sizes. Pack took 0.243 s at 12.74 MiB peak process RSS. Restore took 0.230 s at 12.70 MiB. All 36 other files matched the stock copy while packed. All 48 original files matched after restoration. One 4 KiB archive directory remained. [Synthetic run](synthetic-results.json)

In a separate Lean 4.36.0 package, Lake generated setup files of 1,457, 5,394 and 21,136 bytes for modules with 8, 32 and 128 local imports. We packed only the 128-import module. Its 958-byte gzip plus 457-byte receipt saved two allocated ext4 blocks, including directory costs. The same 8 KiB difference was present immediately after building its new dependent. Restoring the setup produced the same full build-tree content digest as stock. The stock command took 0.3533 s and peaked at 591,836 KiB sampled group RSS. The managed commands took 0.0597 s to pack, 0.3622 s to build and 0.0638 s to restore, with a cycle peak of 583,696 KiB. This single stock-first pair measures a generated Lean package without Mathlib. [Import breadth run](import-breadth-results.json)

Both Lean releases exhibited the same behavior. Two compiler processes overlapped in the clean and incremental builds. Building a new downstream theorem succeeded with two dependencies' setups archived. Only the new module compiled, its output matched stock, and both dependencies' setups restored byte for byte. The warm check, static library and executable build, and kernel replay also succeeded with all four setups absent. Editing the shared prerequisite regenerated all four setups. The manager detected a changed proof digest and preserved the new build and the old archive on its attempted restore.

### Time and peak memory by operation

Each cell gives **stock / managed**. Elapsed seconds are the median summed command times for two runs of each arm. They include archive operations and execution of the native test binary where applicable. Peak memory is the largest sampled process-group RSS across those runs, in MiB. Harness setup, hashing for comparisons, and workspace copies are outside the timed commands.

| Fixture operation | 4.36.0 time (s) | 4.36.0 peak (MiB) | 4.37.0-rc1 time (s) | 4.37.0-rc1 peak (MiB) |
| --- | ---: | ---: | ---: | ---: |
| Clean parallel build | 0.811 / 0.873 | 1,034.6 / 1,034.5 | 0.554 / 0.821 | 757.3 / 735.0 |
| Warm no-build check | 0.167 / 0.308 | 111.5 / 111.5 | 0.159 / 0.304 | 117.9 / 118.0 |
| Incremental edit | 0.706 / 0.894 | 1,037.4 / 1,017.0 | 0.556 / 0.757 | 730.1 / 753.4 |
| Native library and executable | 0.764 / 0.913 | 585.6 / 574.9 | 0.662 / 1.150 | 571.2 / 572.0 |
| Kernel replay | 2.012 / 1.690 | 893.9 / 882.5 | 1.798 / 1.885 | 687.8 / 700.7 |
| Build a new dependent | 0.306 / 0.397 | 571.5 / 571.3 | 0.361 / 0.379 | 431.0 / 431.1 |

The clean managed arm packs and restores after building. The new-dependent arm keeps two dependencies packed through the build and then restores them. The remaining paired arms pack and restore before calling Lake. The four additional absent-setup probes appear separately in the raw reports. All successful matched operations produced identical SHA-256 inventories for the compared outputs, including proofs, traces and native artifacts. Filesystem caches were shared across successive runs. Two repetitions describe this fixture and cannot establish a general build-time or RAM difference. [Lean 4.36.0 trials](lean-4.36.0.json) · [Lean 4.37.0-rc1 trials](lean-4.37.0-rc1.json)
