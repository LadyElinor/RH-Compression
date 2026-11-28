"""Measure archive operations on generated path maps. Run on Linux with Python 3."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANAGER = HERE / "manage.py"
IMPORTS = 3000
MODULES = [f"Example.Proofs.Bundle{i:02d}" for i in range(12)]


def make_fixture(root):
    """Invent path strings and opaque witness bytes; nothing here is compiled."""
    artifacts = {}
    for i in range(IMPORTS):
        name = f"Example.Algebra.Family{i % 37:02d}.Lemma{i:04d}"
        base = ".lake/packages/example/.lake/build/lib/lean/" + name.replace(".", "/")
        artifacts[name] = [[base + suffix for suffix in (".olean", ".olean.server", ".olean.private")],
                           [base + suffix for suffix in (".ir.sig", ".ir")]]
    for module in MODULES:
        relative = Path(*module.split("."))
        setup = (root / ".lake/build/ir" / relative).with_suffix(".setup.json")
        setup.parent.mkdir(parents=True, exist_ok=True)
        setup.write_text(json.dumps({"name": module, "importArts": artifacts}, separators=(",", ":")),
                         encoding="utf-8")
        witness = root / ".lake/build/lib/lean" / relative
        witness.parent.mkdir(parents=True, exist_ok=True)
        for suffix in (".olean", ".trace", ".ilean"):
            witness.with_suffix(suffix).write_text(f"synthetic {module}{suffix}\n", encoding="utf-8")


def files(root):
    return {p.relative_to(root) for p in root.rglob("*") if p.is_file()}


def fingerprint(root, paths):
    entries = [(p.as_posix(), hashlib.sha256((root / p).read_bytes()).hexdigest()) for p in sorted(paths)]
    return hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()


def check_originals(stock, managed, paths):
    for path in sorted(paths):
        if (stock / path).read_bytes() != (managed / path).read_bytes():
            raise ValueError(f"Byte mismatch for {path}")


def storage(root, original_files):
    """Count the entire workspace. st_blocks also includes allocated directories."""
    totals = {"regular_files": 0, "directories": 0, "file_bytes": 0,
              "allocated_bytes_including_dirs": 0, "live_setup_bytes": 0,
              "original_other_file_bytes": 0, "additional_file_bytes": 0}
    for path in [root, *root.rglob("*")]:
        metadata = path.lstat()
        totals["allocated_bytes_including_dirs"] += metadata.st_blocks * 512
        if stat.S_ISDIR(metadata.st_mode):
            totals["directories"] += 1
        if stat.S_ISREG(metadata.st_mode):
            totals["regular_files"] += 1
            if path.relative_to(root) not in original_files:
                category = "additional_file_bytes"
            elif path.name.endswith(".setup.json"):
                category = "live_setup_bytes"
            else:
                category = "original_other_file_bytes"
            totals[category] += metadata.st_size
            totals["file_bytes"] += metadata.st_size
    return totals


def measure(operation, workspace, modules):
    command = [sys.executable, str(MANAGER), operation, "--workspace", str(workspace), *modules]
    # Linux wait4 includes the child’s pre-exec RSS. A fresh, small launcher
    # keeps fixture generation and verification memory out of this measurement.
    launcher = """
import os, sys, time
metrics_fd, executable, *args = sys.argv[1:]
start = time.perf_counter()
pid = os.posix_spawn(executable, [executable, *args], os.environ)
_, status, usage = os.wait4(pid, 0)
os.write(int(metrics_fd), f"{time.perf_counter() - start} {usage.ru_maxrss}".encode())
sys.exit(os.waitstatus_to_exitcode(status))
"""
    with tempfile.TemporaryFile() as metrics:
        proc = subprocess.run([sys.executable, "-S", "-c", launcher, str(metrics.fileno()), *command],
                              capture_output=True, pass_fds=(metrics.fileno(),))
        if proc.returncode:
            raise RuntimeError(f"{operation} failed ({proc.returncode}): {proc.stderr.decode()}")
        metrics.seek(0)
        elapsed, rss = metrics.read().split()
    return {"elapsed_s": round(float(elapsed), 6), "process_peak_rss_kib": int(rss)}, json.loads(proc.stdout)


def run():
    started = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix="rh-synthetic-archive-") as temp:
        filesystem = (subprocess.check_output(["findmnt", "-T", temp, "-n", "-o", "FSTYPE"], text=True).strip()
                      if shutil.which("findmnt") else "unreported")
        stock = Path(temp) / "stock"
        managed = Path(temp) / "managed"
        make_fixture(stock)
        shutil.copytree(stock, managed)
        original = files(stock)
        setup = {p for p in original if p.name.endswith(".setup.json")}
        protected = original - setup
        check_originals(stock, managed, original)
        initial_entries = set(managed.rglob("*"))
        setup_digest = fingerprint(stock, setup)
        protected_digest = fingerprint(stock, protected)
        stock_storage = storage(stock, original)
        baseline = storage(managed, original)

        plan_timing, plan = measure("plan", managed, MODULES)
        if set(managed.rglob("*")) != initial_entries or storage(managed, original) != baseline:
            raise ValueError("Dry run changed the workspace")
        check_originals(stock, managed, original)

        pack_timing, _ = measure("pack", managed, MODULES)
        if any((managed / path).exists() for path in setup):
            raise ValueError("A selected setup is still present after pack")
        check_originals(stock, managed, protected)
        archived = storage(managed, original)
        gzip_bytes = sum(path.stat().st_size for path in managed.rglob("setup.gz"))
        metadata_bytes = archived["additional_file_bytes"] - gzip_bytes
        if (plan["input_bytes"] != baseline["live_setup_bytes"] or plan["gzip_bytes"] != gzip_bytes
                or plan["receipt_bytes"] != metadata_bytes):
            raise ValueError("Dry run sizes differ from measured payload sizes")

        restore_timing, _ = measure("restore", managed, [])
        check_originals(stock, managed, original)
        restored = storage(managed, original)

    return {
        "started_utc": started, "trial_filesystem": filesystem,
        "benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "Single synthetic storage trial; generated strings and opaque fixture witnesses.",
        "platform": platform.platform(), "python": platform.python_version(),
        "zlib": zlib.ZLIB_RUNTIME_VERSION, "manager_sha256": hashlib.sha256(MANAGER.read_bytes()).hexdigest(),
        "fixture": {"modules": len(MODULES), "imports_per_module": IMPORTS,
                    "protected_files": len(protected), "setup_tree_sha256": setup_digest,
                    "protected_tree_sha256": protected_digest},
        "plan": {k: plan[k] for k in ("input_bytes", "gzip_bytes", "receipt_bytes", "file_content_savings_bytes")},
        "storage": {"units": "bytes; allocated totals sum Linux st_blocks * 512 for files and directories",
                    "stock": stock_storage, "managed_before": baseline, "packed": archived, "restored": restored,
                    "packed_gzip_bytes": gzip_bytes,
                    "packed_metadata_file_bytes": metadata_bytes,
                    "net_file_bytes_saved": baseline["file_bytes"] - archived["file_bytes"],
                    "net_allocated_bytes_saved": (baseline["allocated_bytes_including_dirs"]
                                                  - archived["allocated_bytes_including_dirs"])},
        "operations": {"plan": plan_timing, "pack": pack_timing, "restore": restore_timing},
        "verification": {"plan_preserved_input_tree": True,
                         "all_selected_setups_absent_after_pack": True,
                         "all_protected_files_byte_equal_stock_while_packed": True,
                         "all_restored_original_files_byte_equal_stock": True},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write JSON to this file (default: stdout)")
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("This benchmark uses Linux wait4 peak RSS and st_blocks units")
    if args.output and args.output.exists():
        parser.error("choose an unused output path")
    report = json.dumps(run(), indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as output:
            output.write(report)
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
