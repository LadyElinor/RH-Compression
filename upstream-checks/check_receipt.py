"""Check producer module records for the pinned post-merge PR #266 build."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zlib

HEAD = "d4e7aaaaac1c4d07b3eadf35638fedfbb4ab3509"
TREE = "21ebc6018ab46e9fe24d7fa4696135077020202b"
INPUTS = {
    "source_tree": "88e6ed20f4e894e0570c00b396414a1c9dfbd940",
    "build_roots": {},
    "lakefile_sha256": "e12dd96eb155851de5107571dbfc959e5d9b230ead90331b4778b55b048590bb",
    "manifest_sha256": "ee003c5c7a9b2b2a82a142b6633916661c07117199dd143d94d1af63910237df",
    "toolchain": "leanprover/lean4:v4.36.0",
}
FINGERPRINT = hashlib.sha256(json.dumps(INPUTS, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
TARGETS = tuple("Development.AbelianVarietyTheory.Proofs.RingsOfIntegers." + name for name in (
    "SplitKernelFormalGroupOfRationalTorsion", "SumHvPrimaryKernel", "SumHarmonicValuesFormalKernelSimilitude",
))
LIMIT = 64 * 1024 * 1024
ROW_FORMAT = (r"[\w']+(?:\.[\w']+)*", r"[0-9a-f]{16}", r"[0-9a-f]{16}\.ltar", r"[0-9a-f]{64}")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def unique_keys(pairs):
    fields = dict(pairs)
    require(len(fields) == len(pairs), "duplicate JSON field")
    return fields


def limited(stream):
    data = stream.read(LIMIT + 1)
    require(len(data) <= LIMIT, "metadata exceeds 64 MiB")
    return data


def check(receipt_path, manifest_path, reference_sha=None):
    with receipt_path.open("rb") as stream:
        raw = limited(stream)
    digest = hashlib.sha256(raw).hexdigest()
    if reference_sha is not None:
        require(digest == reference_sha, "receipt file SHA-256 mismatch")
    receipt = json.loads(raw, object_pairs_hook=unique_keys)
    require(isinstance(receipt, dict), "expected a receipt object")
    require(type(receipt.get("schema")) is int and receipt["schema"] == 1, "unsupported receipt schema")
    require(receipt.get("candidate_head") == HEAD, "candidate revision mismatch")
    require(receipt.get("candidate_tree") == TREE, "candidate tree mismatch")
    for key, value in {**INPUTS, "input_fingerprint": FINGERPRINT}.items():
        require(receipt.get(key) == value, f"unexpected receipt {key}")
    if "repository" in receipt:
        require(receipt["repository"] == "leanprover-community/riemann-hypothesis", "unexpected cache repository")
        require(receipt.get("module_manifest_key") == f"ci/module-manifests/{receipt.get('module_manifest_sha256')}.jsonl.gz"
                and receipt.get("map_key") == f"ci/maps/{receipt.get('map_sha256')}.jsonl", "invalid public cache object key")
        nested = receipt.get("receipt")
        if nested is not None:
            fields = (*INPUTS, "candidate_head", "candidate_tree", "input_fingerprint", "build_exit_code",
                      "map_sha256", "module_manifest_bytes", "module_manifest_sha256")
            require(isinstance(nested, dict) and all(nested.get(k) == receipt.get(k) for k in fields),
                    "nested receipt conflicts with the public record")
    code = receipt.get("build_exit_code")
    require(type(code) is int and 0 <= code <= 255, "invalid build exit code")
    map_sha = receipt.get("map_sha256")
    require(isinstance(map_sha, str) and re.fullmatch(ROW_FORMAT[3], map_sha), "invalid map SHA-256")

    with manifest_path.open("rb") as stream:
        compressed = limited(stream)
    size = receipt.get("module_manifest_bytes")
    require(type(size) is int and size == len(compressed), "manifest size mismatch")
    require(hashlib.sha256(compressed).hexdigest() == receipt.get("module_manifest_sha256"), "manifest SHA-256 mismatch")
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        lines = limited(stream).splitlines()
    require(bool(lines), "missing manifest header")
    header = json.loads(lines[0], object_pairs_hook=unique_keys)
    expected = {"schema": 1, **INPUTS, "input_fingerprint": FINGERPRINT, "map_sha256": map_sha, "modules": len(lines) - 1}
    require(isinstance(header, dict) and type(header.get("schema")) is int
            and type(header.get("modules")) is int and header == expected, "manifest header or row count mismatch")

    seen_names, seen_inputs, targets = set(), set(), {}
    for line in lines[1:]:
        row = json.loads(line)
        require(isinstance(row, list) and len(row) == 4 and all(
            isinstance(v, str) and re.fullmatch(pattern, v) for v, pattern in zip(row, ROW_FORMAT)
        ), "malformed module output record")
        name, dep_hash, artifact, output_sha = row
        require(name not in seen_names and dep_hash not in seen_inputs, "duplicate module or input hash")
        seen_names.add(name)
        seen_inputs.add(dep_hash)
        if name in TARGETS:
            targets[name] = (artifact, output_sha)
    return code, targets, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--receipt-sha256", help="independently obtained SHA-256 of the supplied receipt file")
    args = parser.parse_args()
    try:
        code, records, digest = check(args.receipt, args.manifest, args.receipt_sha256)
    except (OSError, ValueError, EOFError, zlib.error) as error:
        print(f"Invalid evidence: {error}", file=sys.stderr)
        return 2
    basis = "matched supplied SHA-256" if args.receipt_sha256 else "origin uncorroborated"
    print(f"Receipt {digest} ({basis})\nRevision {HEAD}\nProducer build exit code {code}")
    for name in TARGETS:
        print(f"LISTED {name}  {' '.join(records[name])}" if name in records else f"ABSENT {name}")
    print(f"{len(records)}/3 outputs listed. This check inspects records only. Kernel replay was not performed.")
    return 0 if len(records) == 3 else 3


if __name__ == "__main__":
    sys.exit(main())
