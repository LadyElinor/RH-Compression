"""Time six separately compiled Lean modules and their consolidated bundle on Linux."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
LEAN_REV = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"
MATHLIB_REV = "fc4f59e577feb1a4956671bc04ac18aaaf8cd842"
FLAGS = ["-j1", "--tstack=400000", "-DautoImplicit=false", "-DrelaxedAutoImplicit=false",
         "-DmaxSynthPendingDepth=3", "-Dpp.unicode.fun=true", "-DmaxHeartbeats=4000000"]


def prepare(revision, entry, checkout, root):
    relative = entry["path"]
    url = f"https://raw.githubusercontent.com/rohanarun/riemann-hypothesis/{revision}/{relative}"
    if checkout:
        data = (checkout / relative).read_bytes()
    else:
        with urlopen(url, timeout=60) as response:
            data = response.read()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError(f"Source hash mismatch for {relative}")
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def compile_one(source, root, outdir):
    relative = source.relative_to(root)
    target = (outdir / relative).with_suffix(".olean")
    target.parent.mkdir(parents=True, exist_ok=True)
    command = ["lean", *FLAGS, f"--root={root}", "-o", str(target), str(source)]
    start = time.perf_counter()
    process = subprocess.Popen(command)
    _, status, usage = os.wait4(process.pid, 0)
    seconds = time.perf_counter() - start
    process.returncode = os.waitstatus_to_exitcode(status)
    if process.returncode or not target.is_file():
        raise RuntimeError(f"Compilation failed for {relative} (exit {process.returncode})")
    return {"file": str(relative), "wall_s": round(seconds, 4),
            "peak_rss_kib": usage.ru_maxrss, "user_s": round(usage.ru_utime, 4),
            "system_s": round(usage.ru_stime, 4)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, help="local original checkout (default: download pinned files)")
    parser.add_argument("--candidate", type=Path, help="local candidate checkout (default: download pinned file)")
    parser.add_argument("--output", type=Path, required=True, help="write the completed timing record here")
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("This benchmark records Linux wait4 peak RSS in KiB.")
    if subprocess.check_output(["lean", "--githash"], text=True).strip() != LEAN_REV:
        parser.error("Run with the repository's pinned Lean using lake env.")
    mathlib = HERE.parent / ".lake/packages/mathlib"
    revision = subprocess.check_output(["git", "-C", mathlib, "rev-parse", "HEAD"], text=True).strip()
    if revision != MATHLIB_REV:
        parser.error("Unexpected Mathlib checkout.")
    manifest = json.loads((HERE / "inputs.json").read_text())
    report = {"started_utc": datetime.now(timezone.utc).isoformat(), "os": platform.system(),
              "arch": platform.machine(), "lean_commit": LEAN_REV, "mathlib_commit": MATHLIB_REV,
              "original_commit": manifest["base_sha"], "candidate_commit": manifest["candidate_sha"],
              "lean_flags": FLAGS, "rounds": []}
    with tempfile.TemporaryDirectory(prefix="rh-bundle-") as temp:
        work = Path(temp)
        root = work / "src"
        original = [prepare(manifest["base_sha"], entry, args.original, work) for entry in manifest["files"]]
        entry = {"path": manifest["candidate_path"], "sha256": manifest["candidate_sha256"]}
        bundle = prepare(manifest["candidate_sha"], entry, args.candidate, work)
        header = b"module\n\npublic import Mathlib\n\n@[expose] public section\n\n"
        sections = []
        for source, entry in zip(original, manifest["files"]):
            data = source.read_bytes()
            if not data.startswith(header):
                raise ValueError(f"Unexpected module header in {source.name}")
            prefix = f"-- bundled from {entry['module']}\nsection\n".encode()
            sections.append(prefix + data[len(header):] + b"end\n\n")
        if bundle.read_bytes() != header + b"".join(sections):
            raise ValueError("Bundle differs from the six original module bodies.")
        warmup = root / "Warmup.lean"
        warmup.write_text("module\npublic import Mathlib\n")
        compile_one(warmup, root, work / "warmup")
        sources = {"separate": original, "bundle": [bundle]}
        for pair, order in enumerate([("separate", "bundle"), ("bundle", "separate")], start=1):
            for mode in order:
                outdir = work / f"round-{pair}-{mode}"
                measurements = []
                for source in sources[mode]:
                    result = compile_one(source, root, outdir)
                    measurements.append(result)
                    print(f"{pair} {mode} {source.stem} {result['wall_s']:.2f}s", flush=True)
                report["rounds"].append({"pair": pair, "mode": mode, "files": measurements,
                    "total_compiler_wall_s": round(sum(x["wall_s"] for x in measurements), 4),
                    "max_process_rss_kib": max(x["peak_rss_kib"] for x in measurements)})
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
