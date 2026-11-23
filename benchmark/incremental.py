"""Measure one proof edit with Lake, using the hash-pinned inputs from run.py."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import time

from run import HERE, LEAN_REV, MATHLIB_REV, prepare

EDIT_MODULE = "Development.AbelianVarietyTheory.Proofs.FormalGroupCharts.FlatMvPowerSeries"
BEFORE = b"    exact (Submodule.mem_span_range_iff_exists_fun T).1 hm\n"
AFTER = b"    exact id ((Submodule.mem_span_range_iff_exists_fun T).1 hm)\n"
SAMPLE_S = 0.025
CONFIG = f"""name = "rh_compression"
srcDir = "src"
platformIndependent = true
moreLeanArgs = ["--tstack=400000"]
[leanOptions]
autoImplicit = false
relaxedAutoImplicit = false
maxSynthPendingDepth = 3
pp.unicode.fun = true
maxHeartbeats = 4000000
[[require]]
name = "mathlib"
git = "https://github.com/leanprover-community/mathlib4"
rev = "{MATHLIB_REV}"
[[lean_lib]]
name = "Development"
globs = ["Development.+"]
"""


def create_layout(root, inputs, revision, checkout):
    root.mkdir()
    (root / "lakefile.toml").write_text(CONFIG)
    for filename in ("lean-toolchain", "lake-manifest.json"):
        shutil.copyfile(HERE.parent / filename, root / filename)
    (root / ".lake").mkdir()
    (root / ".lake/packages").symlink_to((HERE.parent / ".lake/packages").resolve())
    paths = [prepare(revision, entry, checkout, root) for entry in inputs]
    return {".".join(path.relative_to(root / "src").with_suffix("").parts): path for path in paths}


def sample_group(pgid, pagesize_kib):
    # Each child inherits Lake's private process group. Read rss and pgrp in one stat read.
    rss = compiler_rss = compilers = 0
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            line = path.read_bytes()
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        name, tail = line.rsplit(b")", 1)
        fields = tail.split()
        if int(fields[2]) != pgid:
            continue
        resident = int(fields[21]) * pagesize_kib
        rss += resident
        if name.endswith(b"(lean"):
            compiler_rss += resident
            compilers += 1
    return rss, compiler_rss, compilers


def build(root, modules, env, measure=False):
    command = ["lake", "--no-cache", "--no-ansi", "build", *["+" + m + ":olean" for m in modules]]
    with tempfile.TemporaryFile("w+") as log:
        start = time.monotonic()
        process = subprocess.Popen(command, cwd=root, env=env, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        rss = compiler_rss = compilers = samples = 0
        pagesize_kib = os.sysconf("SC_PAGE_SIZE") // 1024
        if measure:
            while process.poll() is None:
                group, lean, count = sample_group(process.pid, pagesize_kib)
                rss = max(rss, group)
                compiler_rss = max(compiler_rss, lean)
                compilers = max(compilers, count)
                samples += 1
                time.sleep(SAMPLE_S)
        code = process.wait()
        wall = time.monotonic() - start
        log.seek(0)
        output = log.read()
    if code:
        raise RuntimeError("Lake failed:\n" + output[-8000:])
    rebuilt = re.findall(r"\[\d+/\d+\] Built (\S+) \(", output)
    return {"wall_s": round(wall, 4), "rebuilt": rebuilt,
            "peak_process_group_rss_kib": rss, "peak_compiler_sum_rss_kib": compiler_rss,
            "max_simultaneous_compilers": compilers, "samples": samples}


def mtimes(root, modules):
    out = root / ".lake/build/lib/lean"
    return {m: (out / Path(*m.split("."))).with_suffix(".olean").stat().st_mtime_ns for m in modules}


def trial(root, sources, target, env, pair, direction):
    stamps = mtimes(root, sources)
    if direction != "no edit":
        old, new = (BEFORE, AFTER) if direction == "forward" else (AFTER, BEFORE)
        source = sources[target]
        data = source.read_bytes()
        if data.count(old) != 1 or new in data:
            raise ValueError("The selected proof line must occur exactly once in this layout.")
        source.write_bytes(data.replace(old, new))
    result = build(root, sources, env, measure=True)
    changed = [m for m, stamp in mtimes(root, sources).items() if stamp != stamps[m]]
    expected = [] if direction == "no edit" else [target]
    if changed != expected or result["rebuilt"] != expected:
        raise RuntimeError(f"Unexpected rebuild: {changed=}, {result=}")
    return dict(pair=pair, layout=root.name, direction=direction,
                target_oleans_rewritten=changed, **result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if platform.system() != "Linux":
        parser.error("Linux /proc is needed for sampling.")
    lean_hash = subprocess.check_output(["lean", "--githash"], text=True).strip()
    mathlib = HERE.parent / ".lake/packages/mathlib"
    mathlib_head = subprocess.check_output(["git", "-C", mathlib, "rev-parse", "HEAD"], text=True).strip()
    if (lean_hash, mathlib_head) != (LEAN_REV, MATHLIB_REV):
        parser.error("Pinned Lean 4.36 and Mathlib are required.")
    manifest = json.loads((HERE / "inputs.json").read_text())
    bundle_entry = dict(path=manifest["candidate_path"], sha256=manifest["candidate_sha256"])
    env = dict(os.environ, LEAN_NUM_THREADS="1")
    records = []
    report = dict(started_utc=datetime.now(timezone.utc).isoformat(),
                  os=platform.system(), arch=platform.machine(),
                  lake_version=subprocess.check_output(["lake", "--version"], text=True).strip(),
                  lean_commit=LEAN_REV, mathlib_commit=MATHLIB_REV,
                  original_commit=manifest["base_sha"], candidate_commit=manifest["candidate_sha"],
                  lake_manifest_sha256=hashlib.sha256((HERE.parent / "lake-manifest.json").read_bytes()).hexdigest(),
                  edit_module=EDIT_MODULE, before=BEFORE.decode().strip(), after=AFTER.decode().strip(),
                  sample_sleep_seconds=SAMPLE_S, lean_num_threads=1, facet="olean", trials=records)
    with tempfile.TemporaryDirectory(prefix="rh-edit-") as tmp:
        work = Path(tmp)
        layouts = {
            "separate": create_layout(work / "separate", manifest["files"], manifest["base_sha"], args.original),
            "bundle": create_layout(work / "bundle", [bundle_entry], manifest["candidate_sha"], args.candidate),
        }
        edited = {"separate": EDIT_MODULE, "bundle": next(iter(layouts["bundle"]))}
        for layout, sources in layouts.items():
            # Bring the full fixture up to date without six concurrent cold compilers.
            for m in sources:
                print(f"Preparing {m}", flush=True)
                result = build(work / layout, [m], env)
                if m not in result["rebuilt"]:
                    raise RuntimeError(f"Initial local module was not built: {m}")
        for layout in layouts:
            records.append(trial(work / layout, layouts[layout], edited[layout], env, 0, "no edit"))
        # Both directions are observed once in each order across the four comparisons.
        for pair, first in enumerate(["separate", "bundle", "bundle", "separate"], start=1):
            direction = "forward" if pair % 2 else "reverse"
            for layout in [first, "separate" if first == "bundle" else "bundle"]:
                record = trial(work / layout, layouts[layout], edited[layout], env, pair, direction)
                records.append(record)
                print(f"Pair {pair}: {direction}, {layout}, {record['wall_s']:.3f} s", flush=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
