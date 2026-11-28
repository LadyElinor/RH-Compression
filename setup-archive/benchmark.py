"""Compare Lake with and without setup archiving in a fresh Linux workspace."""
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
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
# Share the repository's Linux process-group RSS sampler.
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent / "benchmark"))
from incremental import sample_group

MODULES = ("ArchiveFixture.Base", "ArchiveFixture.Left", "ArchiveFixture.Right", "ArchiveFixture")


def setup_paths(modules):
    return {f"ir/{name.replace('.', '/')}.setup.json" for name in modules}


SETUPS = setup_paths(MODULES)
TARGET = "+ArchiveFixture:olean"
LAKE = ["lake", "--no-cache", "--no-ansi"]
SAMPLE_S = 0.010
SCENARIOS = ("parallel_clean", "warm_no_build", "incremental", "native", "kernel", "new_dependent")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def manifest(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob("*")) if p.is_file()}


def fingerprint(mapping):
    return hashlib.sha256(json.dumps(mapping, sort_keys=True).encode()).hexdigest()


def storage(work):
    """Apparent file bytes and allocated bytes, including directory blocks, under .lake."""
    base = work / ".lake"
    if not base.exists():
        return {}
    sizes = {"setup": [0, 0, 0], "archive": [0, 0, 0], "other": [0, 0, 0]}
    for path in [base, *base.rglob("*")]:
        relative = path.relative_to(base).as_posix()
        group = ("archive" if relative.split("/")[0] == "setup-archive-v1" else
                 "setup" if relative.removeprefix("build/") in SETUPS else "other")
        stat = path.stat()
        if path.is_file():
            sizes[group][0] += 1
            sizes[group][1] += stat.st_size
        sizes[group][2] += stat.st_blocks * 512
    return sizes


def measure(argv, work, env):
    pagesize_kib = os.sysconf("SC_PAGE_SIZE") // 1024
    rss = overlap = samples = 0
    with tempfile.TemporaryFile(mode="w+") as log:
        start = time.perf_counter()
        with subprocess.Popen(argv, cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT,
                              start_new_session=True) as proc:
            while proc.poll() is None:
                group_rss, _, compilers = sample_group(proc.pid, pagesize_kib)
                rss = max(rss, group_rss)
                overlap = max(overlap, compilers)
                samples += 1
                try:
                    proc.wait(timeout=SAMPLE_S)
                except subprocess.TimeoutExpired:
                    pass
            elapsed = time.perf_counter() - start
        log.seek(0)
        output = log.read()
    return {"exit": proc.returncode, "elapsed_s": round(elapsed, 4),
            "sampled_peak_group_rss_kib": rss, "max_simultaneous_lean": overlap,
            "samples": samples}, output


def checked_measure(argv, work, env):
    result, log = measure(argv, work, env)
    require(result["exit"] == 0, f"{argv} failed in fixture:\n{log[-4000:]}")
    return result, log


def manage_command(op, work, modules=()):
    return [sys.executable, str(HERE / "manage.py"), op, "--workspace", str(work), *modules]


def stage_archive(op, work, env, inputs, record, selected=MODULES):
    modules = selected if op == "pack" else ()
    measured, _ = checked_measure(manage_command(op, work, modules), work, env)
    excluded = setup_paths(selected) if op == "pack" else set()
    expected = {p: v for p, v in inputs.items() if p not in excluded}
    require(manifest(work / ".lake/build") == expected, f"{op} changed unexpected build files")
    record["operations"][op] = measured
    record["storage"][op] = storage(work)


def exercise(scenario, work, env, mode, record):
    if scenario == "incremental":
        base = work / "ArchiveFixture/Base.lean"
        body = base.read_text()
        require(body.count("seed : Nat := 5") == 1, "Missing unique incremental edit")
        base.write_text(body.replace("seed : Nat := 5", "seed : Nat := 7"))
    if scenario == "new_dependent":
        (work / "ArchiveFixture/Next.lean").write_text(
            "import ArchiveFixture\n\ntheorem nextAnswer : ArchiveFixture.answer = 13 := by decide\n")
    commands = {
        "parallel_clean": [*LAKE, "build", TARGET],
        "warm_no_build": [*LAKE, "--no-build", "build", TARGET],
        "incremental": [*LAKE, "build", TARGET],
        "native": [*LAKE, "build", "ArchiveFixture:static", "fixture_check"],
        "kernel": ["lake", "env", "leanchecker", "--verbose", "ArchiveFixture"],
        "new_dependent": [*LAKE, "build", "+ArchiveFixture.Next:olean"],
    }
    measured, log = measure(commands[scenario], work, env)
    record["operations"]["lake"] = measured
    if measured["exit"]:
        if mode != "setups_absent":
            raise RuntimeError(f"{scenario}, {mode} failed:\n{log[-4000:]}")
        record["diagnostic"] = log[-2000:]
        return
    if scenario in {"parallel_clean", "incremental", "warm_no_build", "new_dependent"}:
        built = sorted(re.findall(r"\[\d+/\d+\] Built (\S+) \(", log))
        expected = {"new_dependent": ["ArchiveFixture.Next"], "warm_no_build": []}.get(scenario, sorted(MODULES))
        require(built == expected, f"{scenario} rebuilt {built}, expected {expected}")
        record["built"] = built
    elif scenario == "native":
        require(any((work / ".lake/build/lib").glob("*.a")), "Static library missing")
        measured, out = checked_measure([str(work / ".lake/build/bin/fixture_check")], work, env)
        require(out.strip() == "13", f"Native executable returned {out!r}")
        record["operations"]["execute"] = measured
        record["stdout"] = out.strip()
    else:
        replayed = sorted(re.findall(r"^replaying (\S+)$", log, re.M))
        require(replayed == sorted(MODULES), f"Unexpected leanchecker replay: {log}")
        record["replayed"] = replayed


def run_case(work, template, env, scenario, mode):
    # work is always the same fresh path inside our own TemporaryDirectory.
    shutil.copytree(template, work)
    try:
        build = work / ".lake/build"
        before = manifest(build)
        record = {"mode": mode, "operations": {}, "storage": {"initial": storage(work)}}
        selected = MODULES[:2] if mode == "archived_dependencies" else MODULES
        if mode != "stock" and scenario != "parallel_clean":
            require(SETUPS <= before.keys(), "Incomplete baseline")
            stage_archive("pack", work, env, before, record, selected)
            if mode == "restored":
                stage_archive("restore", work, env, before, record)
        exercise(scenario, work, env, mode, record)
        after = manifest(build)
        if scenario == "incremental" and "diagnostic" not in record:
            for name in MODULES:
                proof = "lib/lean/" + name.replace(".", "/") + ".olean"
                require(before[proof] != after[proof], f"Edit left {proof} unchanged")
        record["target_setups_present_after_lake"] = sorted(SETUPS & after.keys())
        if mode == "archived_dependencies":
            expected = {p: v for p, v in before.items() if p not in setup_paths(selected)}
            require(all(after.get(p) == v for p, v in expected.items()), "A dependency changed")
            require(not (setup_paths(selected) & after.keys()), "Downstream build regenerated a setup")
        if mode in {"archived_dependencies", "setups_absent"} and "diagnostic" not in record:
            record["storage"]["after_lake"] = storage(work)
            if scenario == "incremental":
                require(SETUPS <= after.keys(), "Expected regenerated setups for edited import closure")
                snapshot = manifest(work / ".lake")
                measured, log = measure(manage_command("restore", work), work, env)
                require(measured["exit"] != 0 and "changed" in log, f"Expected stale-archive refusal: {log}")
                require(snapshot == manifest(work / ".lake"), "Refusal altered a build or archive")
                record["operations"]["refused_restore"] = measured
                record["restore_diagnostic"] = log.strip()
            else:
                missing = {p: before[p] for p in setup_paths(selected)}
                stage_archive("restore", work, env, {**after, **missing}, record, selected)
        if mode != "stock" and scenario == "parallel_clean":
            stage_archive("pack", work, env, after, record)
            stage_archive("restore", work, env, after, record)
        record["storage"]["final"] = storage(work)
        protected = {p: v for p, v in after.items() if p not in SETUPS}
        if scenario in {"warm_no_build", "kernel"} and "diagnostic" not in record:
            expected = {p: v for p, v in before.items() if p not in SETUPS}
            require(protected == expected, f"{scenario} rewrote build outputs")
        record["protected_build_files"] = len(protected)
        record["protected_manifest_sha256"] = fingerprint(protected)
        phases = record["operations"].values()
        record["measured_cycle_elapsed_s"] = round(sum(p["elapsed_s"] for p in phases), 4)
        record["sampled_cycle_peak_group_rss_kib"] = max(p["sampled_peak_group_rss_kib"] for p in phases)
        # All output files apart from the four named setup files, including native objects and traces.
        return record, protected
    finally:
        shutil.rmtree(work)


def run(args):
    env = dict(os.environ, PATH=f"{args.bin_dir.resolve()}:{os.environ['PATH']}",
               LEAN_NUM_THREADS="4", SOURCE_DATE_EPOCH="1700000000")
    tools = ("lean", "lake", "leanchecker")
    for tool in tools:
        require((args.bin_dir / tool).is_file(), f"{tool} missing in --bin-dir")
    def get(cmd):
        return subprocess.check_output(cmd, env=env, text=True).strip()

    report = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "fixture_sha256": fingerprint(manifest(HERE / "fixture")),
        "manager_sha256": hashlib.sha256((HERE / "manage.py").read_bytes()).hexdigest(),
        "lean_version": get(["lean", "--version"]), "lean_commit": get(["lean", "--githash"]),
        "lake_version": get(["lake", "--version"]), "platform": platform.platform(),
        "lean_num_threads": 4, "sample_pause_s": SAMPLE_S, "pairs": args.pairs,
        "storage_columns": ["regular files", "apparent file bytes", "allocated bytes including directories"],
        "trials": [],
    }
    with tempfile.TemporaryDirectory(prefix="lean-archive-") as tmp:
        base = Path(tmp)
        if shutil.which("findmnt"):
            report["trial_filesystem"] = get(["findmnt", "-T", tmp, "-n", "-o", "FSTYPE"])
        report["filesystem_block_bytes"] = os.statvfs(base).f_frsize
        work = base / "workspace"
        fixture = HERE / "fixture"
        # Seed every warm operation with exactly the same successful stock tree.
        shutil.copytree(fixture, work)
        checked_measure([*LAKE, "build", TARGET], work, env)
        baseline = base / "initial-built-tree"
        work.rename(baseline)
        report["baseline_build_sha256"] = fingerprint(manifest(baseline / ".lake/build"))
        for i in range(args.pairs):
            for j, scenario in enumerate(SCENARIOS):
                managed = "archived_dependencies" if scenario == "new_dependent" else "restored"
                order = ["stock", managed] if (i + j) % 2 == 0 else [managed, "stock"]
                if i == 0 and scenario not in {"parallel_clean", "new_dependent"}:
                    order.append("setups_absent")
                reference = None
                for mode in order:
                    source = fixture if scenario == "parallel_clean" else baseline
                    row, hashes = run_case(work, source, env, scenario, mode)
                    row.update(pair=i + 1, scenario=scenario)
                    if reference is None:
                        reference = hashes
                    elif "diagnostic" not in row:
                        require(hashes == reference, f"{scenario}, {mode}: differing proof, trace or native outputs: "
                                + ", ".join(p for p in sorted(hashes.keys() | reference.keys())
                                            if hashes.get(p) != reference.get(p)))
                    report["trials"].append(row)
    require(any(row["operations"]["lake"]["max_simultaneous_lean"] > 1
                for row in report["trials"] if row["scenario"] == "parallel_clean"),
            "The sampler saw no concurrent clean-build compilers; parallel operation remains unverified")
    for path, field in ((Path(__file__), "benchmark_sha256"), (HERE / "manage.py", "manager_sha256")):
        require(hashlib.sha256(path.read_bytes()).hexdigest() == report[field], f"{path.name} changed during run")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin-dir", type=Path, required=True, help="directory of a Lean release's binaries")
    parser.add_argument("--pairs", type=int, default=2, help="paired repetitions (default 2, alternating order)")
    parser.add_argument("--output", type=Path, required=True, help="new result JSON")
    args = parser.parse_args()
    if platform.system() != "Linux" or args.pairs < 1 or args.output.exists():
        parser.error("requires Linux, positive --pairs and an unused output path")
    data = run(args)
    with args.output.open("x") as out:
        json.dump(data, out, indent=2)
        out.write("\n")
