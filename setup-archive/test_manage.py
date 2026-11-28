"""Black-box regression checks. Every build tree here is a fresh temporary fixture."""

import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


MANAGER = Path(__file__).with_name("manage.py").resolve()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup_bytes(label):
    return json.dumps({
        "name": label,
        "imports": [f"/example/.lake/build/lib/lean/Dependency{n}.olean" for n in range(1200)],
    }).encode() + b"\r\n"


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.ir = self.workspace / ".lake/build/ir"
        self.lib = self.workspace / ".lake/build/lib/lean"
        self.ir.mkdir(parents=True)
        self.lib.mkdir(parents=True)
        (self.workspace / "lakefile.toml").write_text('name = "fixture"\n')

    def module(self, name):
        rel = Path(*name.split("."))
        setup = (self.ir / rel).with_suffix(".setup.json")
        proof = (self.lib / rel).with_suffix(".olean")
        trace = (self.lib / rel).with_suffix(".trace")
        setup.parent.mkdir(parents=True, exist_ok=True)
        proof.parent.mkdir(parents=True, exist_ok=True)
        setup.write_bytes(setup_bytes(name))
        proof.write_bytes(b"disposable proof witness\x00" + name.encode())
        trace.write_text(json.dumps({"module": name, "fixture": True}))
        return setup, proof, trace

    def cli(self, operation, *modules, success=True):
        proc = subprocess.run(
            [sys.executable, str(MANAGER), operation, "--workspace", str(self.workspace), *modules],
            capture_output=True, text=True, timeout=30,
        )
        message = f"{operation} {modules} exited {proc.returncode}\n{proc.stdout}{proc.stderr}"
        if success:
            self.assertEqual(proc.returncode, 0, message)
        else:
            self.assertNotEqual(proc.returncode, 0, message)
        return proc

    def inventory(self):
        # Ignore access times: reading a file can update its atime on some mounts.
        return {
            str(p.relative_to(self.workspace)): (digest(p), p.stat().st_mtime_ns, p.stat().st_mode)
            for p in self.workspace.rglob("*") if p.is_file()
        }

    def archives(self):
        return sorted(self.workspace.rglob("*.gz"))

    def test_round_trip_affects_only_selected_setups(self):
        a, _, _ = self.module("A.One")
        b, _, _ = self.module("B.Two'")
        c, _, _ = self.module("C.Three")
        for suffix in [".olean.private", ".olean.server", ".ilean", ".olean.hash"]:
            (self.lib / f"A/One{suffix}").write_bytes(suffix.encode())
        for suffix in (".c", ".irsetup.json", ".irsetup.json.trace"):
            (self.ir / f"A/One{suffix}").write_bytes(suffix.encode())
        (self.workspace / "record.json").write_bytes(b'{"retained":true}')
        before = self.inventory()
        expected = {str(p.relative_to(self.workspace)): p.read_bytes() for p in (a, b)}
        self.cli("pack", "A.One", "B.Two'")
        self.assertFalse(a.exists())
        self.assertFalse(b.exists())
        self.assertTrue(c.is_file())
        for path, attributes in before.items():
            if path not in expected:
                p = self.workspace / path
                self.assertEqual((digest(p), p.stat().st_mtime_ns, p.stat().st_mode), attributes, path)
        self.cli("restore", "B.Two'")
        self.assertTrue(b.exists())
        self.assertFalse(a.exists())
        self.cli("restore")
        for path, raw in expected.items():
            self.assertEqual((self.workspace / path).read_bytes(), raw)

    def test_plan_never_writes_and_predicts_stream_sizes(self):
        setup, _, _ = self.module("Data.Example")
        before = self.inventory()
        dirs = sorted(p.relative_to(self.workspace) for p in self.workspace.rglob("*") if p.is_dir())
        report = json.loads(self.cli("plan", "Data.Example").stdout)
        self.assertEqual(self.inventory(), before)
        self.assertEqual(sorted(p.relative_to(self.workspace) for p in self.workspace.rglob("*") if p.is_dir()), dirs)
        size = setup.stat().st_size
        self.cli("pack", "Data.Example")
        (archive,) = self.archives()
        self.assertEqual(report["input_bytes"], size)
        self.assertEqual(report["gzip_bytes"], archive.stat().st_size)
        self.assertEqual(report["payload_savings_bytes"], size - archive.stat().st_size)

    def test_deterministic_gzip_independent_of_file_time(self):
        setup, _, _ = self.module("Stable")
        expected = setup.read_bytes()
        self.cli("pack", "Stable")
        (archive,) = self.archives()
        first = archive.read_bytes()
        self.assertEqual(gzip.decompress(first), expected)
        self.assertEqual(first[4:8], bytes(4), "gzip header timestamp")
        self.assertEqual(first[3] & 0x08, 0, "gzip must omit the source filename")
        self.cli("restore")
        os.utime(setup, (1_000_000, 1_000_000))
        self.cli("pack", "Stable")
        (again,) = self.archives()
        self.assertEqual(again.read_bytes(), first)

    def test_no_implicit_pack_or_plan(self):
        self.module("Explicit")
        before = self.inventory()
        for operation in ("plan", "pack"):
            self.cli(operation, success=False)
            self.assertEqual(self.inventory(), before)

    def test_incomplete_module_leaves_setup_live(self):
        for missing in ("proof", "trace"):
            with self.subTest(missing=missing):
                name = "Incomplete." + missing.title()
                setup, proof, trace = self.module(name)
                {"proof": proof, "trace": trace}[missing].unlink()
                raw = setup.read_bytes()
                self.cli("pack", name, success=False)
                self.assertEqual(setup.read_bytes(), raw)

    def test_suspicious_module_paths_rejected(self):
        self.module("Test")
        outside = self.root / "outside.setup.json"
        outside.write_bytes(b"outside")
        for name in ("../outside", "/outside", "A/B", "A..B", ".A", "A."):
            with self.subTest(name=name):
                self.cli("pack", name, success=False)
                self.assertEqual(outside.read_bytes(), b"outside")
                self.assertEqual((self.ir / "Test.setup.json").read_bytes(), setup_bytes("Test"))

    def test_symbolic_setup_and_parent_refused(self):
        a, _, _ = self.module("Direct")
        b, _, _ = self.module("Indirect.Entry")
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        outside_setup = elsewhere / a.name
        a.rename(outside_setup)
        a.symlink_to(outside_setup)
        (self.ir / "Indirect").rename(elsewhere / "moved")
        (self.ir / "Indirect").symlink_to(elsewhere / "moved", target_is_directory=True)
        for name, path in (("Direct", a), ("Indirect.Entry", b)):
            with self.subTest(name=name):
                self.cli("pack", name, success=False)
                self.assertEqual(path.read_bytes(), setup_bytes(name))
                self.cli("recover")
                self.assertEqual(self.archives(), [])

    def test_hardlinked_setup_remains_linked(self):
        setup, _, _ = self.module("Linked")
        other = self.root / "other-name"
        os.link(setup, other)
        for operation in ("plan", "pack"):
            with self.subTest(operation=operation):
                self.cli(operation, "Linked", success=False)
                self.assertTrue(setup.samefile(other))
                self.assertEqual(other.read_bytes(), setup_bytes("Linked"))
        self.cli("recover")

    def test_non_regular_completion_witness_refused(self):
        setup, proof, _ = self.module("Witness")
        original = setup.read_bytes()
        proof.unlink()
        proof.mkdir()
        self.cli("pack", "Witness", success=False)
        self.assertEqual(setup.read_bytes(), original)
        self.assertFalse(self.archives())

    def test_restore_refuses_dangling_symlink(self):
        setup, _, _ = self.module("Link")
        expected = setup.read_bytes()
        self.cli("pack", "Link")
        outside = self.root / "absent.json"
        setup.symlink_to(outside)
        self.cli("restore", success=False)
        self.assertTrue(setup.is_symlink())
        self.assertFalse(outside.exists())
        (archive,) = self.archives()
        self.assertEqual(gzip.decompress(archive.read_bytes()), expected)
        setup.unlink()
        self.cli("recover")
        self.assertEqual(setup.read_bytes(), expected)

    def test_restore_does_not_clobber_regenerated_setup(self):
        setup, _, _ = self.module("Changed")
        original = setup.read_bytes()
        self.cli("pack", "Changed")
        (archive,) = self.archives()
        setup.write_bytes(b"new setup generated independently")
        self.cli("restore", success=False)
        self.cli("recover", success=False)
        self.assertEqual(setup.read_bytes(), b"new setup generated independently")
        self.assertEqual(gzip.decompress(archive.read_bytes()), original)

    def test_corrupt_archive_never_publishes_partial_setup(self):
        setup, proof, trace = self.module("Truncated")
        protected = {p: digest(p) for p in (proof, trace)}
        raw = setup.read_bytes()
        self.cli("pack", "Truncated")
        (archive,) = self.archives()
        good = archive.read_bytes()
        for bad in (good[:-7], gzip.compress(raw.replace(b"Dependency", b"Xependency"), mtime=0)):
            with self.subTest(size=len(bad)):
                archive.write_bytes(bad)
                self.cli("restore", success=False)
                self.assertFalse(setup.exists())
                self.assertEqual({p: digest(p) for p in (proof, trace)}, protected)
                self.assertEqual(archive.read_bytes(), bad)
        archive.write_bytes(good)
        self.cli("restore")
        self.assertEqual(setup.read_bytes(), raw)

    def test_raw_content_digest_is_verified_independently(self):
        setup, _, _ = self.module("Content")
        original = setup.read_bytes()
        self.cli("pack", "Content")
        (archive,) = self.archives()
        receipt_path = archive.parent / "receipt.json"
        receipt = json.loads(receipt_path.read_bytes())
        # Valid gzip and matching compressed size/hash but different same-length content.
        altered = gzip.compress(original.replace(b"Dependency", b"Xependency"), mtime=0)
        archive.write_bytes(altered)
        receipt["gzip_sha256"] = digest(archive)
        receipt["gzip_size"] = len(altered)
        receipt_path.write_text(json.dumps(receipt))
        self.cli("restore", success=False)
        self.assertFalse(setup.exists())
        self.assertEqual(archive.read_bytes(), altered)

    def test_repeated_operations_keep_one_verified_version(self):
        setup, _, _ = self.module("Repeat")
        expected = setup.read_bytes()
        self.cli("pack", "Repeat")
        (archive,) = self.archives()
        archive_bytes = archive.read_bytes()
        self.cli("pack", "Repeat")
        self.assertEqual(self.archives(), [archive])
        self.assertEqual(archive.read_bytes(), archive_bytes)
        self.cli("restore", "Repeat")
        self.cli("restore", "Repeat")
        self.cli("recover")
        self.assertEqual(setup.read_bytes(), expected)
        self.assertFalse(self.archives())

    def test_conflicting_manager_fails_without_mutation(self):
        self.module("Locked")
        before = self.inventory()
        lock = os.open(self.workspace, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.cli("pack", "Locked", success=False)
            self.assertEqual(self.inventory(), before)
        finally:
            os.close(lock)
        self.cli("pack", "Locked")
        self.cli("restore", "Locked")

    def test_receipt_matches_live_witnesses_and_verified_stream(self):
        setup, proof, trace = self.module("Receipt")
        raw_sha = digest(setup)
        setup.chmod(0o640)
        os.utime(setup, ns=(1700000000123456789, 1700000000123456789))
        original = setup.stat()
        self.cli("pack", "Receipt")
        (archive,) = self.archives()
        receipt = json.loads((archive.parent / "receipt.json").read_text())
        self.assertEqual(receipt["sha256"], raw_sha)
        self.assertEqual(receipt["gzip_sha256"], digest(archive))
        self.assertEqual(receipt["olean_sha256"], digest(proof))
        self.assertEqual(receipt["trace_sha256"], digest(trace))
        self.assertEqual(receipt["size"], original.st_size)
        self.assertEqual(receipt["uid"], original.st_uid)
        self.assertEqual(receipt["gid"], original.st_gid)
        self.assertEqual(receipt["gzip_size"], archive.stat().st_size)
        self.cli("restore", "Receipt")
        self.assertEqual(setup.stat().st_mode, original.st_mode)
        self.assertEqual(setup.stat().st_mtime_ns, original.st_mtime_ns)

    def test_restore_rejects_changed_completion_witnesses(self):
        setup, proof, trace = self.module("Stale")
        raw = setup.read_bytes()
        self.cli("pack", "Stale")
        for witness in (proof, trace):
            with self.subTest(witness=witness.name):
                original = witness.read_bytes()
                changed = original + b" regenerated"
                witness.write_bytes(changed)
                self.cli("recover", success=False)
                self.assertFalse(setup.exists())
                self.assertEqual(witness.read_bytes(), changed)
                (archive,) = self.archives()
                self.assertEqual(gzip.decompress(archive.read_bytes()), raw)
                witness.write_bytes(original)
        self.cli("restore")
        self.assertEqual(setup.read_bytes(), raw)

    def test_namespace_collision_preserves_unrecognized_data(self):
        self.module("Collision")
        unknown = self.workspace / ".lake/setup-archive-v1" / ".packing"
        unknown.mkdir(parents=True)
        (unknown / "setup.gz").write_bytes(b"preexisting, unrelated content")
        before = self.inventory()
        for operation, names in (("pack", ["Collision"]), ("recover", [])):
            self.cli(operation, *names, success=False)
            self.assertEqual(self.inventory(), before)

    def test_write_limit_failure_preserves_recoverable_copy(self):
        # Simulate a filesystem refusing additional bytes in the child only.
        script = """
import resource
import runpy
import signal
import sys
limit = int(sys.argv.pop(1))
del sys.argv[0]
signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
runpy.run_path(sys.argv[0], run_name="__main__")
"""
        setup, proof, trace = self.module("Limited")
        before = {p: digest(p) for p in (setup, proof, trace)}
        for operation, limit in (("pack", 512), ("restore", 8192)):
            with self.subTest(operation=operation):
                if operation == "restore":
                    self.cli("pack", "Limited")
                proc = subprocess.run(
                    [sys.executable, "-c", script, str(limit), str(MANAGER),
                     operation, "--workspace", str(self.workspace), "Limited"],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
                if operation == "pack":
                    self.assertEqual(digest(setup), before[setup])
                else:
                    self.assertFalse(setup.exists())
                    (archive,) = self.archives()
                    self.assertEqual(gzip.decompress(archive.read_bytes()), setup_bytes("Limited"))
                self.cli("recover")
                self.assertEqual({p: digest(p) for p in before}, before)

    def crash_at(self, operation, point, name):
        # Inject abrupt process death at the same boundaries used by the normal CLI.
        script = """
import os
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv.pop(1))
import manage
point = sys.argv.pop(1)
def crash(current):
    if current == point:
        os._exit(73)
manage.checkpoint = crash
raise SystemExit(manage.main())
"""
        proc = subprocess.run(
            [sys.executable, "-c", script, str(MANAGER.parent), point, operation,
             "--workspace", str(self.workspace), name], capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 73, proc.stdout + proc.stderr)

    def test_recover_with_unexpected_argument_does_not_mutate(self):
        self.module("Pending")
        self.crash_at("pack", "pack-staged", "Pending")
        before = self.inventory()
        self.cli("recover", "Pending", success=False)
        self.assertEqual(self.inventory(), before)
        self.cli("recover")

    def test_recovery_keeps_verified_staged_copy_if_live_path_disappears(self):
        for operation, point in (("pack", "pack-staged"), ("restore", "restore-retired")):
            with self.subTest(point=point):
                name = "Missing"
                setup, proof, trace = self.module(name)
                before = {p: digest(p) for p in (setup, proof, trace)}
                if operation == "restore":
                    self.cli("pack", name)
                self.crash_at(operation, point, name)
                setup.unlink()
                self.cli("recover")
                self.assertEqual({p: digest(p) for p in before}, before)
                self.assertFalse(self.archives())

    def test_staged_archive_survives_conflicting_live_file(self):
        for operation, point in (("pack", "pack-staged"), ("restore", "restore-retired")):
            with self.subTest(point=point):
                name = "Replacement"
                setup, _, _ = self.module(name)
                raw = setup.read_bytes()
                if operation == "restore":
                    self.cli("pack", name)
                self.crash_at(operation, point, name)
                moved = self.root / "restored"
                setup.rename(moved)
                setup.write_bytes(b"generated after interruption")
                self.cli("recover", success=False)
                self.assertEqual(setup.read_bytes(), b"generated after interruption")
                (archive,) = self.archives()
                self.assertEqual(gzip.decompress(archive.read_bytes()), raw)
                setup.unlink()
                moved.rename(setup)
                self.cli("recover")
                self.assertFalse(self.archives())

    def test_crash_at_each_durable_boundary_recovers_exact_input(self):
        for operation, milestones in (
            ("pack", ("staged", "published", "unlinked")),
            ("restore", ("staged", "published", "retired")),
        ):
            for step in milestones:
                point = operation + "-" + step
                with self.subTest(point=point):
                    setup, proof, trace = self.module("Crash")
                    before = {p: digest(p) for p in (setup, proof, trace)}
                    if operation == "restore":
                        self.cli("pack", "Crash")
                    self.crash_at(operation, point, "Crash")
                    interrupted = self.inventory()
                    status = json.loads(self.cli("status").stdout)
                    pending = {"pack-staged": [".packing"], "restore-retired": [".retiring"]}
                    self.assertEqual(status["pending"], pending.get(point, []))
                    self.assertEqual(status["archives"], [] if point in pending else ["Crash"])
                    both = point in {"pack-published", "restore-published"}
                    self.assertEqual(status["live_and_archived"], ["Crash"] if both else [])
                    restoring = point in {"restore-staged", "restore-published"}
                    self.assertEqual(status["staged_restores"], ["Crash"] if restoring else [])
                    self.assertEqual(self.inventory(), interrupted)
                    self.cli("recover")
                    self.cli("recover")
                    self.assertEqual({p: digest(p) for p in before}, before)
                    self.assertFalse(self.archives())


if __name__ == "__main__":
    unittest.main()
