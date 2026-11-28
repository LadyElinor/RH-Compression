#!/usr/bin/env python3
"""Archive explicit, completed Lake setup files between builds (POSIX)."""
import argparse
from contextlib import contextmanager
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import zlib


CHUNK = 256 * 1024
NAMESPACE = "setup-archive-v1"
MARKER = ".manager-v1"
PACKING = ".packing"
RETIRING = ".retiring"
PAYLOAD = "setup.gz"
RECEIPT = "receipt.json"
NEW_RECEIPT = ".receipt-new"
RESTORING = ".restoring"
MODULE = re.compile(r"[^\W\d][\w']*(?:\.[^\W\d][\w']*)*\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class ArchiveError(Exception):
    pass


def checkpoint(point):
    """Test seam for interrupting a subprocess at a durable state transition."""


def regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ArchiveError(f"expected a regular file: {path}")
    return info


def directory(path):
    if not stat.S_ISDIR(path.lstat().st_mode):
        raise ArchiveError(f"expected a directory, without symlinks: {path}")
    return path


def under(root, parts):
    for part in parts:
        root = directory(root / part)
    return root


def present(path):
    # A dangling symlink also occupies its path.
    return os.path.lexists(path)


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def module_name(name):
    if not isinstance(name, str) or not MODULE.fullmatch(name) or len(os.fsencode(name)) > 255:
        raise ArchiveError(f"unsupported module name: {name!r}")
    return name


def file_digest(path):
    regular(path)
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            digest.update(chunk)
        return digest.hexdigest()


class CountHash:
    def __init__(self):
        self.size = 0
        self.digest = hashlib.sha256()

    def write(self, data):
        self.size += len(data)
        self.digest.update(data)
        return len(data)


def fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def source_info(path):
    before = regular(path)
    if before.st_nlink != 1 or before.st_uid != os.geteuid() or before.st_mode & 0o7000:
        raise ArchiveError(f"expected an owned, singly linked ordinary setup: {path}")
    if os.listxattr(path):
        raise ArchiveError(f"setup has extended attributes: {path}")
    return before


def encode_setup(path, before, output=None):
    raw, compressed = CountHash(), CountHash()

    class Writer:
        def write(self, data):
            if output is not None:
                output.write(data)
            return compressed.write(data)

    with path.open("rb") as src, gzip.GzipFile(
        filename="", mode="wb", compresslevel=1, fileobj=Writer(), mtime=0
    ) as encoder:
        for chunk in iter(lambda: src.read(CHUNK), b""):
            raw.write(chunk)
            encoder.write(chunk)
    if fingerprint(regular(path)) != fingerprint(before):
        raise ArchiveError(f"setup changed during compression: {path}")
    return dict(size=raw.size, sha256=raw.digest.hexdigest(), gzip_size=compressed.size,
                gzip_sha256=compressed.digest.hexdigest(), mode=stat.S_IMODE(before.st_mode),
                uid=before.st_uid, gid=before.st_gid, mtime_ns=before.st_mtime_ns)


def decode_verified(payload, entry, output=None):
    if regular(payload).st_size != entry["gzip_size"] or file_digest(payload) != entry["gzip_sha256"]:
        raise ArchiveError(f"compressed digest or size mismatch: {payload}")
    raw = CountHash()
    with gzip.open(payload, "rb") as decoder:
        while chunk := decoder.read(CHUNK):
            raw.write(chunk)
            if raw.size > entry["size"]:
                raise ArchiveError(f"expanded size exceeds receipt: {payload}")
            if output is not None:
                output.write(chunk)
    if raw.size != entry["size"] or raw.digest.hexdigest() != entry["sha256"]:
        raise ArchiveError(f"uncompressed digest or size mismatch: {payload}")


def receipt_bytes(entry):
    return (json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n").encode()


def load_receipt(path):
    if regular(path).st_size > 16 * 1024:
        raise ArchiveError(f"oversized receipt: {path}")
    return json.loads(path.read_bytes())


def read_entry(record, name):
    directory(record)
    path = record / RECEIPT
    entry = load_receipt(path)
    fields = {"schema", "module", "size", "gzip_size", "mode", "mtime_ns", "uid", "gid",
              "sha256", "gzip_sha256", "olean_sha256", "trace_sha256"}
    if (not isinstance(entry, dict) or set(entry) != fields or entry["module"] != name
            or type(entry["schema"]) is not int or entry["schema"] != 1):
        raise ArchiveError(f"unexpected receipt format: {path}")
    for key in ("sha256", "gzip_sha256", "olean_sha256", "trace_sha256"):
        if not isinstance(entry[key], str) or not DIGEST.fullmatch(entry[key]):
            raise ArchiveError(f"invalid {key}: {path}")
    for key in ("size", "gzip_size", "mode", "mtime_ns", "uid", "gid"):
        if type(entry[key]) is not int or (key != "mtime_ns" and entry[key] < 0):
            raise ArchiveError(f"invalid {key}: {path}")
    if entry["uid"] != os.geteuid():
        raise ArchiveError(f"restore as the account that packed this setup: {path}")
    if entry["mode"] > 0o777:
        raise ArchiveError(f"invalid file mode: {path}")
    return entry


def remove_stage(path, allowed):
    directory(path)
    children = list(path.iterdir())
    for child in children:
        if child.name not in allowed:
            raise ArchiveError(f"unexpected entry in transaction directory: {child}")
        regular(child)
    # Keep the receipt until all payload and scratch entries are gone.
    for child in sorted(children, key=lambda p: p.name == RECEIPT):
        child.unlink()
        if child.name != RECEIPT:
            fsync_dir(path)
    path.rmdir()
    fsync_dir(path.parent)


class Manager:
    def __init__(self, workspace):
        self.lake = directory(workspace / ".lake")
        self.build = directory(self.lake / "build")
        self.store = self.lake / NAMESPACE

    def open_store(self, create=False):
        if not present(self.store):
            if not create:
                return False
            self.store.mkdir(mode=0o700)
            fsync_dir(self.lake)
        directory(self.store)
        marker = self.store / MARKER
        if not present(marker):
            if any(self.store.iterdir()):
                raise ArchiveError(f"unrecognized archive directory: {self.store}")
            if not create:
                return False
            with marker.open("xb") as stream:
                os.fsync(stream.fileno())
            fsync_dir(self.store)
        if regular(marker).st_size != 0:
            raise ArchiveError(f"invalid archive marker: {marker}")
        return True

    def paths(self, name):
        *parents, stem = module_name(name).split(".")
        ir = under(self.build, ["ir", *parents])
        lib = under(self.build, ["lib", "lean", *parents])
        return ir / (stem + ".setup.json"), lib / (stem + ".olean"), lib / (stem + ".trace")

    def witnesses(self, olean, trace):
        return dict(olean_sha256=file_digest(olean), trace_sha256=file_digest(trace))

    def check_witnesses(self, entry, olean, trace):
        for key, digest in self.witnesses(olean, trace).items():
            if entry[key] != digest:
                raise ArchiveError(f"completion witness changed for {entry['module']}: {key}")

    def names(self):
        if not self.open_store():
            return []
        return sorted(module_name(p.name) for p in self.store.iterdir()
                      if p.name not in {MARKER, PACKING, RETIRING})

    def read_record(self, name):
        record = directory(self.store / module_name(name))
        for path in record.iterdir():
            if path.name not in {RECEIPT, PAYLOAD, RESTORING}:
                raise ArchiveError(f"unexpected archive member: {path}")
            regular(path)
        return read_entry(record, name)

    def check_live(self, path, entry):
        info = regular(path)
        if (info.st_size != entry["size"] or file_digest(path) != entry["sha256"] or
            info.st_mtime_ns != entry["mtime_ns"] or stat.S_IMODE(info.st_mode) != entry["mode"] or
            info.st_gid != entry["gid"] or info.st_uid != os.geteuid() or os.listxattr(path)):
            raise ArchiveError(f"live setup conflicts with archive; both retained: {path}")
        return info

    def pack(self, name, dry_run):
        live, olean, trace = self.paths(name)
        record = self.store / name
        if self.open_store() and present(record):
            entry = self.read_record(name)
            self.check_witnesses(entry, olean, trace)
            decode_verified(record / PAYLOAD, entry)
            if present(live):
                self.check_live(live, entry)
                raise ArchiveError(f"both copies exist for {name}; run recover")
            return dict(module=name, action="already_archived", restore_bytes=entry["size"])

        witnesses = self.witnesses(olean, trace)
        original = source_info(live)
        destination = self.store if present(self.store) else self.lake
        if live.parent.stat().st_dev != destination.stat().st_dev:
            raise ArchiveError(f"restore requires setup and archive on the same filesystem: {live}")
        intent_bytes = receipt_bytes(dict(packing=name))
        if dry_run:
            fields = encode_setup(live, original)
        else:
            self.open_store(create=True)
            stage = self.store / PACKING
            stage.mkdir(mode=0o700)
            # Identify the live input durably before creating a partial gzip.
            with (stage / RECEIPT).open("xb") as intent:
                intent.write(intent_bytes)
                intent.flush()
                os.fsync(intent.fileno())
            fsync_dir(stage)
            with (stage / PAYLOAD).open("xb") as output:
                # Check that the same account can reproduce the group on restoration.
                if os.fstat(output.fileno()).st_gid != original.st_gid:
                    os.fchown(output.fileno(), -1, original.st_gid)
                fields = encode_setup(live, original, output)
                output.flush()
                os.fsync(output.fileno())
        entry = dict(schema=1, module=name, **fields, **witnesses)
        receipt = receipt_bytes(entry)
        if not dry_run:
            with (stage / NEW_RECEIPT).open("xb") as output:
                output.write(receipt)
                output.flush()
                os.fsync(output.fileno())
            (stage / NEW_RECEIPT).replace(stage / RECEIPT)
            decode_verified(stage / PAYLOAD, read_entry(stage, name))
            fsync_dir(stage)
            checkpoint("pack-staged")
            stage.rename(record)
            fsync_dir(self.store)
            checkpoint("pack-published")
            self.check_witnesses(entry, olean, trace)
            if fingerprint(regular(live)) != fingerprint(original):
                raise ArchiveError(f"setup changed before unlink: {live}")
            live.unlink()
            fsync_dir(live.parent)
            checkpoint("pack-unlinked")
        return dict(module=name, action="would_archive" if dry_run else "archived",
                    input_bytes=fields["size"], gzip_bytes=fields["gzip_size"],
                    receipt_bytes=len(receipt), input_allocated_bytes=original.st_blocks * 512,
                    staging_file_bytes=fields["gzip_size"] + len(receipt) + len(intent_bytes))

    def restore(self, name):
        live, olean, trace = self.paths(name)
        record = self.store / name
        if not self.open_store() or not present(record):
            regular(live)
            return dict(module=name, action="already_live")
        entry = self.read_record(name)
        self.check_witnesses(entry, olean, trace)
        tmp = record / RESTORING
        if present(live):
            self.check_live(live, entry)
            decode_verified(record / PAYLOAD, entry)
        else:
            if present(tmp):
                regular(tmp)
                tmp.unlink()
            with tmp.open("xb") as output:
                decode_verified(record / PAYLOAD, entry, output)
                output.flush()
                if os.fstat(output.fileno()).st_gid != entry["gid"]:
                    os.fchown(output.fileno(), -1, entry["gid"])
                os.fchmod(output.fileno(), entry["mode"])
                os.utime(output.fileno(), ns=(entry["mtime_ns"], entry["mtime_ns"]))
                os.fsync(output.fileno())
            self.check_live(tmp, entry)
            checkpoint("restore-staged")
            # A hard link publishes a complete file and fails if a writer created live.
            os.link(tmp, live)
        # The dual-copy path may reuse an original from an interrupted pack.
        with live.open("rb") as verified:
            os.fsync(verified.fileno())
        fsync_dir(live.parent)
        checkpoint("restore-published")
        tomb = self.store / RETIRING
        record.rename(tomb)
        fsync_dir(self.store)
        checkpoint("restore-retired")
        remove_stage(tomb, {RECEIPT, PAYLOAD, RESTORING})
        return dict(module=name, action="restored")

    def settle_stage(self, label):
        """Keep the last recoverable copy, including after an interrupted cleanup."""
        stage = directory(self.store / label)
        receipt, payload = stage / RECEIPT, stage / PAYLOAD
        allowed = {RECEIPT, PAYLOAD, NEW_RECEIPT} if label == PACKING else {RECEIPT, PAYLOAD, RESTORING}
        children = list(stage.iterdir())
        for child in children:
            if child.name not in allowed:
                raise ArchiveError(f"unexpected transaction entry: {child}")
            regular(child)
        if not present(payload) and label == PACKING:
            # No live unlink can happen before a pack has a published record.
            remove_stage(stage, allowed)
            return
        if not children:  # Empty retiring directory left by the final rmdir.
            remove_stage(stage, allowed)
            return
        info = load_receipt(receipt)
        if isinstance(info, dict) and set(info) == {"packing"} and label == PACKING:
            live, _, _ = self.paths(module_name(info["packing"]))
            regular(live)  # Preserve partial data if someone removed the original.
            remove_stage(stage, allowed)
            return
        if not isinstance(info, dict) or not isinstance(info.get("module"), str):
            raise ArchiveError(f"invalid transaction receipt: {receipt}")
        name = module_name(info["module"])
        entry = read_entry(stage, name)
        live, olean, trace = self.paths(name)
        if present(live):
            self.check_live(live, entry)
            with live.open("rb") as verified:
                os.fsync(verified.fileno())
            fsync_dir(live.parent)
            remove_stage(stage, allowed)
            return
        # The original disappeared after publication or before recovery. Move
        # the verified record back into the normal restoration path.
        self.check_witnesses(entry, olean, trace)
        decode_verified(payload, entry)
        record = self.store / name
        if present(record):
            raise ArchiveError(f"transaction conflicts with another archive: {record}")
        stage.rename(record)
        fsync_dir(self.store)

    def run(self, command, names):
        if command in {"recover", "status"} and names:
            raise ArchiveError(f"{command} takes no module names")
        if command in {"plan", "pack"} and not names:
            raise ArchiveError("select completed modules explicitly")
        for name in names:
            module_name(name)
        if len(set(names)) != len(names):
            raise ArchiveError("duplicate module")
        opened = self.open_store()
        if opened:
            for label in (PACKING, RETIRING):
                if present(self.store / label):
                    if command == "recover":
                        self.settle_stage(label)
                    elif command != "status":
                        raise ArchiveError("unfinished transaction; run recover")
        if command in {"plan", "pack"}:
            rows = [self.pack(name, command == "plan") for name in names]
            totals = {key: sum(row.get(key, 0) for row in rows)
                      for key in ("input_bytes", "gzip_bytes", "receipt_bytes", "input_allocated_bytes")}
            return dict(modules=rows, **totals,
                        payload_savings_bytes=totals["input_bytes"] - totals["gzip_bytes"],
                        file_content_savings_bytes=totals["input_bytes"] - totals["gzip_bytes"] - totals["receipt_bytes"],
                        largest_staged_archive_bytes=max(row.get("staging_file_bytes", 0) for row in rows),
                        largest_restored_setup_bytes=max(row.get("restore_bytes", row.get("input_bytes", 0)) for row in rows))
        targets = names or self.names()
        if command == "status":
            pending = [p for p in (PACKING, RETIRING) if opened and present(self.store / p)]
            both, restoring = [], []
            for name in targets:
                record = directory(self.store / name)
                live, _, _ = self.paths(name)
                if present(live):
                    both.append(name)
                if present(record / RESTORING):
                    restoring.append(name)
            return dict(archives=targets, pending=pending, live_and_archived=both,
                        staged_restores=restoring)
        return dict(modules=[self.restore(name) for name in targets])


@contextmanager
def locked_workspace(workspace):
    workspace = workspace.absolute()
    if ".." in workspace.parts:
        raise ArchiveError("workspace must not contain '..'")
    under(Path(workspace.anchor), workspace.parts[1:])
    fd = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as err:
            raise ArchiveError("another manager holds the workspace lock") from err
        yield workspace
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "pack", "restore", "recover", "status"))
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("modules", nargs="*", metavar="MODULE")
    args = parser.parse_intermixed_args(argv)
    try:
        with locked_workspace(args.workspace) as workspace:
            result = Manager(workspace).run(args.command, args.modules)
        print(json.dumps(result, sort_keys=True))
    except (ArchiveError, OSError, EOFError, ValueError, zlib.error) as err:
        print(f"setup-archive: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
