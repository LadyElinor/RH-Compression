"""Measure three fixed import widths in a generated, dependency-free Lean package."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
from benchmark import HERE, LAKE, SAMPLE_S, checked_measure, fingerprint, manage_command, manifest, require, storage


WIDTHS = {8: "Small", 32: "Medium", 128: "Wide"}
WIDE = "ImportBreadth.Wide"
TARGET_SETUP = "ir/ImportBreadth/Wide.setup.json"


def generate(work):
    sources = work / "ImportBreadth"
    sources.mkdir(parents=True)
    (work / "lakefile.toml").write_text('name = "import_breadth"\n[[lean_lib]]\nname = "ImportBreadth"\n')
    leaves = []
    for n in range(1, max(WIDTHS) + 1):
        name = f"Leaf{n:03}"
        (sources / f"{name}.lean").write_text(f"def ImportBreadth.leaf{n} : Nat := {n}\n")
        leaves.append(f"ImportBreadth.{name}")
    for n, name in WIDTHS.items():
        imports = "".join(f"import {module}\n" for module in leaves[:n])
        (sources / f"{name}.lean").write_text(
            imports + f"\ntheorem ImportBreadth.{name}Value : ImportBreadth.leaf{n} = {n} := rfl\n")
    return leaves


def footprint(work):
    columns = list(zip(*storage(work).values()))
    return dict(apparent_bytes=sum(columns[1]), allocated_bytes=sum(columns[2]))


def compare(work, checkpoint, env, before, managed):
    shutil.copytree(checkpoint, work)
    try:
        (work / "ImportBreadth/Next.lean").write_text(
            "import ImportBreadth.Wide\n\ntheorem nextValue : ImportBreadth.leaf128 = 128 := ImportBreadth.WideValue\n")
        build = work / ".lake/build"
        row = {"mode": "managed" if managed else "stock", "operations": {}, "storage": {"before": footprint(work)}}
        ops = row["operations"]
        expected = dict(before)
        if managed:
            ops["pack"], _ = checked_measure(manage_command("pack", work, [WIDE]), work, env)
            del expected[TARGET_SETUP]
            require(manifest(build) == expected, "Pack changed other build files")
            row["storage"]["packed"] = footprint(work)
        ops["lake"], log = checked_measure([*LAKE, "build", "+ImportBreadth.Next:olean"], work, env)
        require(log.count("] Built ") == 1 and "] Built ImportBreadth.Next (" in log, "Expected only Next to build")
        after = manifest(build)
        require(all(after.get(k) == v for k, v in expected.items()), "A completed artifact changed")
        row["storage"]["after_lake"] = footprint(work)
        if managed:
            require(TARGET_SETUP not in after, "Build regenerated the archived setup")
            ops["restore"], _ = checked_measure(manage_command("restore", work), work, env)
            require(manifest(build) == {**after, TARGET_SETUP: before[TARGET_SETUP]}, "Restore mismatch")
        row["storage"]["final"] = footprint(work)
        row["final_build_sha256"] = fingerprint(manifest(build))
        return row
    finally:
        shutil.rmtree(work)


def run(bin_dir):
    env = dict(os.environ, PATH=f"{bin_dir.resolve()}:{os.environ['PATH']}", LEAN_NUM_THREADS="2")
    require(all((bin_dir / tool).is_file() for tool in ("lean", "lake")), "Lean and Lake must share --bin-dir")
    with tempfile.TemporaryDirectory(prefix="lean-imports-") as tmp:
        base = Path(tmp)
        work = base / "workspace"
        leaves = generate(work)
        report = {"started_utc": datetime.now(timezone.utc).isoformat(),
                  "source_sha256": fingerprint(manifest(work)),
                  "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "manager_sha256": hashlib.sha256((HERE / "manage.py").read_bytes()).hexdigest(),
                  "measurement_harness_sha256": hashlib.sha256((HERE / "benchmark.py").read_bytes()).hexdigest(),
                  "lean_version": subprocess.check_output(["lean", "--version"], env=env, text=True).strip(),
                  "filesystem": subprocess.check_output(["findmnt", "-T", tmp, "-n", "-o", "FSTYPE"], text=True).strip(),
                  "block_bytes": os.statvfs(work).f_frsize, "sample_pause_s": SAMPLE_S, "lean_num_threads": 2}
        importers = [f"ImportBreadth.{name}" for name in WIDTHS.values()]
        # Cap the number of outstanding leaf elaborations as well as Lean's worker threads.
        batches = [leaves[i:i + 2] for i in range(0, len(leaves), 2)] + [[m] for m in importers]
        for modules in batches:
            checked_measure([*LAKE, "build", *[f"+{m}:olean" for m in modules]], work, env)
        before = manifest(work / ".lake/build")
        report["plan_measurement"], plan = checked_measure(manage_command("plan", work, importers), work, env)
        require(manifest(work / ".lake/build") == before and not (work / ".lake/setup-archive-v1").exists(),
                "Dry run changed fixture")
        report["plan_by_import_count"] = {width: row for width, row in zip(WIDTHS, json.loads(plan)["modules"])}
        checkpoint = base / "completed"
        work.rename(checkpoint)
        trials = [compare(work, checkpoint, env, before, managed) for managed in (False, True)]
        require(trials[0]["final_build_sha256"] == trials[1]["final_build_sha256"], "Stock and managed outputs differ")
        report["trials"] = trials
        size = trials[1]["storage"]
        report["packed_allocated_savings_bytes"] = size["before"]["allocated_bytes"] - size["packed"]["allocated_bytes"]
        return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="unused result JSON path")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    report = run(args.bin_dir)
    with args.output.open("x") as out:
        json.dump(report, out, indent=2)
        out.write("\n")
