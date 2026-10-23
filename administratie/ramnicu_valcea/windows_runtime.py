"""Native Windows collection, evidence backup and operational status. No API calls."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import sqlite3
import sys
import traceback
import uuid
import zipfile

from .collector import Store, atomic_write, collect, now, run_lock


def write_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))


def digest_file(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def checked_member(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError("Unsafe backup member: " + name)
    return path


def verify_backup(archive):
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate backup members")
        manifest = json.loads(z.read("manifest.json"))
        expected = manifest["members"]
        if manifest.get("schema_version") != 1 or set(names) != set(expected) | {"manifest.json"}:
            raise ValueError("Backup manifest mismatch")
        for name, metadata in expected.items():
            checked_member(name)
            h, size = hashlib.sha256(), 0
            with z.open(name) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(chunk)
                    size += len(chunk)
            if size != metadata["bytes"] or h.hexdigest() != metadata["sha256"]:
                raise ValueError("Backup checksum mismatch: " + name)
    return manifest


def backup_evidence(data, backup_dir, keep=7):
    """Called under runner lock. SQLite backup API yields a consistent database."""
    data, backup_dir = Path(data), Path(backup_dir)
    database = data / "evidence.sqlite"
    if not database.is_file():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    snapshot = backup_dir / (token + ".sqlite.tmp")
    pending = backup_dir / (token + ".zip.tmp")
    archive = backup_dir / ("ramnicu-" + token + ".zip")
    try:
        source = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        target = sqlite3.connect(snapshot)
        try:
            source.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Evidence database integrity check failed")
        finally:
            target.close()
            source.close()
        members = {"evidence.sqlite": snapshot}
        for directory in ("blobs", "text", "receipts"):
            for path in (data / directory).rglob("*"):
                if path.is_file() and not path.is_symlink():
                    path.resolve().relative_to(data.resolve())
                    members[path.relative_to(data).as_posix()] = path
        for name in ("analysis_queue.json", "latest_run.json"):
            if (data / name).is_file():
                members[name] = data / name
        manifest = {"schema_version": 1, "created_at": now(), "kind": "local_evidence_backup",
                    "members": {name: {"bytes": p.stat().st_size, "sha256": digest_file(p)}
                                for name, p in members.items()}}
        with zipfile.ZipFile(pending, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for name, path in sorted(members.items()):
                z.write(path, name)
            z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        verify_backup(pending)
        pending.replace(archive)
        # Keep only files created by this backup routine; never delete evidence.
        for old in sorted(backup_dir.glob("ramnicu-*.zip"), reverse=True)[max(keep, 1):]:
            old.resolve().relative_to(backup_dir.resolve())
            old.unlink()
        return {"path": str(archive.resolve()), "sha256": digest_file(archive),
                "files": len(members), "verified": True, "offsite": False}
    finally:
        snapshot.unlink(missing_ok=True)
        pending.unlink(missing_ok=True)


def restore_evidence(archive, target):
    """Reject overwrite and traversal. Verify every hash before creating destination."""
    manifest = verify_backup(archive)
    target = Path(target)
    if target.exists():
        raise FileExistsError("Restore target must be a new directory")
    target.mkdir(parents=True)
    with zipfile.ZipFile(archive) as z:
        for name in manifest["members"]:
            destination = target.joinpath(*checked_member(name).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with z.open(name) as source, destination.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
    db = sqlite3.connect((target / "evidence.sqlite").resolve().as_uri() + "?mode=ro", uri=True)
    try:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Restored database failed integrity check")
        for blob, sha in db.execute("SELECT DISTINCT blob_path,sha FROM versions"):
            member = checked_member(blob.replace("\\", "/"))
            if digest_file(target.joinpath(*member.parts)) != sha:
                raise ValueError("Restored original failed checksum validation")
    finally:
        db.close()
    return {"restored_to": str(target.resolve()), "files": len(manifest["members"]), "verified": True}


def status(root):
    root = Path(root)
    path = root / "runtime" / "windows" / "status.json"
    result = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"health": "NEVER_RUN"}
    finished = result.get("finished_at")
    if finished and datetime.now(timezone.utc) - datetime.fromisoformat(finished) > timedelta(hours=30):
        result["last_recorded_health"] = result["health"]
        result["health"] = "STALE"
    result["scheduler"] = "NOT_VERIFIED"
    scheduler = root / "runtime" / "windows" / "scheduler.json"
    if scheduler.is_file():
        result["scheduler_installation"] = json.loads(scheduler.read_text(encoding="utf-8-sig"))
    result.update(model_execution="NOT_CONNECTED", social_collection="NOT_CONNECTED", publication="DISABLED")
    return result


def run(root, config=None, fetcher=None):
    root = Path(root).resolve()
    control = root / "runtime" / "windows"
    data = root / "runtime" / "ramnicu"
    config = config or json.loads((root / "administratie" / "ramnicu_valcea" / "sources.json").read_text(encoding="utf-8"))
    with run_lock(control / "runner.lock"):
        record = {"started_at": now(), "host": __import__("socket").gethostname(), "mode": "collect_only",
                  "health": "RUNNING", "published": 0}
        write_json(control / "status.json", record)
        try:
            receipt = collect(config, data, fetcher=fetcher)
            record.update(health=receipt["collection_status"], run_id=receipt["run_id"],
                          requests=receipt["requests"], changed=receipt["changed"],
                          errors=receipt["errors"], jobs=receipt["jobs_total"],
                          due_remaining=receipt["due_remaining"], extraction_pending=receipt["extraction_pending"],
                          pilot_status=receipt["pilot_status"])
            record["backup"] = backup_evidence(data, root / "runtime" / "backups")
        except Exception as exc:
            record.update(health="FAILED", error=str(exc)[:1000])
            atomic_write(control / "logs" / ("failure-" + uuid.uuid4().hex + ".log"),
                         traceback.format_exc().encode("utf-8"))
        record["finished_at"] = now()
        write_json(control / "status.json", record)
        write_json(control / "logs" / (record.get("run_id", uuid.uuid4().hex) + ".json"), record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "status", "backup", "restore"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--target", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.action == "run":
        result = run(root)
        code = 0 if result["health"] == "BOUNDED_SCAN_COMPLETE" else 2
    elif args.action == "status":
        result, code = status(root), 0
    elif args.action == "backup":
        with run_lock(root / "runtime" / "windows" / "runner.lock"):
            result = backup_evidence(root / "runtime" / "ramnicu", root / "runtime" / "backups")
        code = 0 if result else 1
    else:
        if not args.archive or not args.target:
            parser.error("restore requires --archive and --target")
        result, code = restore_evidence(args.archive, args.target), 0
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
