"""Restore and check one unchanged Lean module from the older 4.36 cache."""
import argparse
import gzip
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

CANDIDATE = "d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509"
BASELINE = "9e273ce65776c200fb97b7edaa288d637632bf7d"
MANIFEST_SHA256 = "651214f93c4c4bb05590ec1b717984f71e5511ddd973a89ca481d1cc1b51b232"
LEAN = "611c117bfaf7b7ae1cfcf246ce6fba31e8f509e9"
MODULE = "ReciprocityTheory.ReductiveGroups.ArithmeticGeometry.BirationalGeometry.ToroidalCompactification.RankLin"
SERVER = "https://rh-cache.taucetiproject.org"


def download(url, target, digest):
    subprocess.run(["curl", "--fail", "--silent", "--show-error", "--location", "--max-time", "120",
                    "--output", str(target), url], check=True)
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise ValueError(f"SHA-256 mismatch for {target.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="candidate Git checkout with a prepared Mathlib cache")
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    packages = (checkout / ".lake/packages").resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="rh-ranklin-") as temporary:
        work = Path(temporary)
        project = work / "project"
        subprocess.run(["git", "clone", "--quiet", "--shared", "--no-checkout", str(checkout), str(project)], check=True)
        subprocess.run(["git", "checkout", "--quiet", "--detach", CANDIDATE], cwd=project, check=True)
        (project / ".lake").mkdir(exist_ok=True)
        (project / ".lake/packages").symlink_to(packages, target_is_directory=True)
        def output(*command):
            return subprocess.check_output(command, cwd=project, text=True).strip()
        if output("lean", "--githash") != LEAN:
            raise ValueError("Select the pinned Lean 4.36.0 compiler")
        manifest = work / "manifest.gz"
        download(f"{SERVER}/bootstrap/{BASELINE}/modules.jsonl.gz", manifest, MANIFEST_SHA256)
        with gzip.open(manifest, "rt") as stream:
            next(stream)
            rows = [row for line in stream if (row := json.loads(line))[0] == MODULE]
        if len(rows) != 1:
            raise ValueError("Expected one baseline manifest entry for the target")
        _, input_hash, archive_name, digest = rows[0]
        actual = output("lake", "--no-build", "query", f"+{MODULE}:depHash")
        if actual != input_hash:
            raise ValueError(f"Candidate input {actual} differs from baseline {input_hash}")
        print(f"Candidate {CANDIDATE}\nBaseline {BASELINE}\nModule {MODULE}\nMatching Lake input {actual}", flush=True)
        archive = work / archive_name
        download(f"{SERVER}/artifacts/leanprover-community/riemann-hypothesis/{archive.stem}.art", archive, digest)
        print(f"Verified {archive_name} ({archive.stat().st_size} bytes, SHA-256 {digest})", flush=True)
        relative = Path(*MODULE.split("."))
        build = project / ".lake/build"
        compiled = (build / "lib/lean" / relative).with_suffix(".olean")
        if compiled.exists():
            raise ValueError("Expected a clean project output directory")
        directories = [build / facet / relative.parent for facet in ["lib/lean", "ir"]]
        for path in directories:
            path.mkdir(parents=True, exist_ok=True)
        job = [{"file": str(archive), "hash": actual, "base": [str(path) for path in directories]}]
        subprocess.run(["leantar", "-f", "-x", "-j", "-"], cwd=project, input=json.dumps(job), text=True, check=True)
        if not compiled.is_file():
            raise ValueError("Archive did not restore the compiled module")
        subprocess.run(["lake", "--no-build", "build", f"+{MODULE}:olean"], cwd=project, check=True)
        subprocess.run(["lake", "env", "leanchecker", "--verbose", MODULE], cwd=project, check=True)
        print("PASS: cached module accepted by stock Lake and replayed by Lean's kernel.", flush=True)


if __name__ == "__main__":
    main()
