"""Offline checker tests. All output rows here are synthetic and have no proof value."""
import contextlib
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import check_receipt as checker


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.receipt = Path(temporary.name) / "receipt.json"
        self.manifest = Path(temporary.name) / "module-manifest.jsonl.gz"

    def fixture(self, names, code, **header_changes):
        header = {"schema": 1, **checker.INPUTS, "input_fingerprint": checker.FINGERPRINT,
                  "map_sha256": "a" * 64, "modules": len(names)}
        receipt = {**header, "candidate_head": checker.HEAD, "candidate_tree": checker.TREE,
                   "build_exit_code": code}
        del receipt["modules"]
        rows = [[name, f"{i:016x}", f"{i:016x}.ltar", "b" * 64] for i, name in enumerate(names)]
        lines = [{**header, **header_changes}, *rows]
        data = gzip.compress(("\n".join(map(json.dumps, lines)) + "\n").encode(), mtime=0)
        self.manifest.write_bytes(data)
        receipt.update(module_manifest_bytes=len(data), module_manifest_sha256=hashlib.sha256(data).hexdigest())
        self.receipt.write_text(json.dumps(receipt))
        return hashlib.sha256(self.receipt.read_bytes()).hexdigest()

    def run_check(self, *extra):
        log = io.StringIO()
        with patch.object(sys, "argv", ["checker", str(self.receipt), str(self.manifest), *extra]), \
                contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            code = checker.main()
        return code, log.getvalue()

    def test_partial_run_with_all_three_outputs(self):
        digest = self.fixture(checker.TARGETS, 137)
        code, text = self.run_check("--receipt-sha256", digest)
        self.assertEqual(code, 0)
        self.assertIn("build exit code 137", text)
        self.assertIn("3/3 outputs listed", text)

    def test_successful_run_with_one_output(self):
        self.fixture(checker.TARGETS[:1], 0)
        code, text = self.run_check()
        self.assertEqual(code, 3)
        self.assertIn("origin uncorroborated", text)
        self.assertIn("LISTED " + checker.TARGETS[0], text)
        self.assertIn("ABSENT " + checker.TARGETS[1], text)

    def test_changed_manifest_and_wrong_receipt_digest(self):
        self.fixture([], 1)
        self.assertEqual(self.run_check("--receipt-sha256", "0" * 64)[0], 2)
        data = bytearray(self.manifest.read_bytes())
        data[-1] ^= 1
        self.manifest.write_bytes(data)
        self.assertEqual(self.run_check(), (2, "Invalid evidence: manifest SHA-256 mismatch\n"))

    def test_header_and_duplicates(self):
        for changes in ({"source_tree": "0" * 40}, {"modules": 2}):
            with self.subTest(changes=changes):
                self.fixture(checker.TARGETS[:1], 1, **changes)
                self.assertEqual(self.run_check()[0], 2)
        self.fixture([checker.TARGETS[0], checker.TARGETS[0]], 1)
        self.assertEqual(self.run_check()[0], 2)


if __name__ == "__main__":
    unittest.main()
