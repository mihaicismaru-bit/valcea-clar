"""Bounded, resumable official-source collector. No model calls or publishing.

Run: python -m administratie.ramnicu_valcea.collector --data-dir /data/ramnicu
All collected content is untrusted evidence, never executable instructions.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import time
import unicodedata
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit, unquote, quote
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser
import uuid

CONFIG = Path(__file__).with_name("sources.json")
AGENTS = {"consiliu_local", "urbanism", "editorial_triage"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def folded(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c))


def safe_url(value, allowed_hosts):
    """Keep meaningful Joomla/Domino query parameters; reject off-scope URLs."""
    p = urlsplit(value)
    if p.scheme != "https" or p.hostname not in allowed_hosts or p.username or p.password or p.port not in (None, 443):
        raise ValueError("URL outside official HTTPS scope")
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit(("https", p.hostname, quote(p.path or "/", safe="/%:@!$&'()*+,;=-._~"), urlencode(sorted(query)), ""))


class Page(HTMLParser):
    """Extract visible content, retaining links to annexes and nested folders."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.text, self.main, self.titles, self.links = [], [], [], []
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in {"meta", "link", "img", "br", "hr", "input", "source", "wbr", "area", "base", "embed", "param", "col"}:
            self.stack.append(tag)
        if tag == "a" and attrs.get("href"):
            self.anchor = [attrs["href"], []]
        if tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3"}:
            self.text.append("\n")
            if "main" in self.stack or "article" in self.stack:
                self.main.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "a" and self.anchor:
            self.links.append((self.anchor[0], " ".join(self.anchor[1])))
            self.anchor = None
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack) - 1 - self.stack[::-1].index(tag)]

    def handle_data(self, data):
        if "title" in self.stack:
            self.titles.append(data)
        if any(t in self.stack for t in {"script", "style", "nav", "footer", "header", "aside", "head"}):
            return
        value = re.sub(r"\s+", " ", data).strip()
        if value:
            self.text.append(value + " ")
            if "main" in self.stack or "article" in self.stack:
                self.main.append(value + " ")
            if self.anchor:
                self.anchor[1].append(value)

    def result(self):
        main_text = "".join(self.main).strip()
        return " ".join(self.titles).strip(), main_text or "".join(self.text).strip(), self.links


def route(title, text, lane):
    # Text establishes a routing hint only; it cannot establish an administrative status.
    sample = folded(title + "\n" + text)
    agents = set()
    if lane == "consiliu_local" or re.search(r"hotarar|consiliul local|proiect.*hcl|sedinta", sample):
        agents.add("consiliu_local")
    if lane == "urbanism" or re.search(r"urbanism|\bpuz\b|\bpud\b|\bpug\b|autorizati.*constru|autorizati.*desfiint", sample):
        agents.add("urbanism")
    return agents or {"editorial_triage"}


def link_kind(url, label, inherited_lane):
    value = folded(unquote(url) + " " + label)
    if re.search(r"logout|login|task=delete|task=remove|format=feed|print=1", value):
        return None
    document = bool(re.search(r"\.(pdf|docx?|xlsx?|csv|htm)(?:$|\?)|\$file/|task=download", value))
    if re.search(r"urbanism|\bpuz\b|\bpud\b|\bpug\b|autorizati|certificat.*urban", value):
        lane = "urbanism"
    elif re.search(r"consili|hotarar|hotarir|convocar|sedint|hcl|\.nsf", value):
        lane = "consiliu_local"
    elif document and inherited_lane != "discovery":
        lane = inherited_lane
    elif inherited_lane != "discovery" and re.search(r"jsmallfib|dir=|start=|page=", value):
        lane = inherited_lane
    else:
        return None
    # Numeric Joomla article slug and Domino attachments are evidence candidates.
    role = "document" if document or re.search(r"/\d{3,}-[^/]+$", urlsplit(url).path) else "index"
    return lane, role


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


@contextmanager
def run_lock(path):
    """OS lock is released on crash, avoiding stale sentinel locks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "evidence.sqlite", timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS documents(url TEXT PRIMARY KEY, current_sha TEXT,
            last_checked TEXT, last_success TEXT, status TEXT, error TEXT, etag TEXT, modified TEXT);
          CREATE TABLE IF NOT EXISTS versions(url TEXT, sha TEXT, first_seen TEXT, final_url TEXT,
            title TEXT, content_type TEXT, extraction_status TEXT, blob_path TEXT, text_path TEXT,
            PRIMARY KEY(url,sha));
          CREATE TABLE IF NOT EXISTS frontier(url TEXT PRIMARY KEY, lane TEXT, role TEXT, depth INTEGER, priority INTEGER);
          CREATE TABLE IF NOT EXISTS edges(parent_url TEXT, child_url TEXT, label TEXT, PRIMARY KEY(parent_url,child_url));
          CREATE TABLE IF NOT EXISTS version_links(parent_url TEXT, parent_sha TEXT, child_url TEXT, label TEXT,
            PRIMARY KEY(parent_url,parent_sha,child_url));
          CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, url TEXT, sha TEXT, agent TEXT, state TEXT,
            created_at TEXT, UNIQUE(url,sha,agent));
          CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, receipt TEXT);
        """)

    def enqueue(self, url, lane, role, depth, seed=False):
        self.db.execute("""INSERT INTO frontier VALUES(?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
          depth=min(depth,excluded.depth), priority=min(priority,excluded.priority)""",
          (url, lane, role, depth, -1 if seed else (0 if role == "document" else 1)))
        self.db.commit()

    def due(self, cutoff):
        return self.db.execute("""SELECT f.* FROM frontier f LEFT JOIN documents d USING(url)
          WHERE d.last_checked IS NULL OR d.last_checked < ?
          ORDER BY f.priority, d.last_checked IS NOT NULL, d.last_checked, f.url LIMIT 1""", (cutoff,)).fetchone()

    def failure(self, url, error):
        self.db.execute("""INSERT INTO documents(url,last_checked,status,error) VALUES(?,?,?,?)
          ON CONFLICT(url) DO UPDATE SET last_checked=excluded.last_checked,status=excluded.status,error=excluded.error""",
          (url, now(), "BLOCKED", str(error)[:500]))
        self.db.commit()

    def ingest(self, url, final_url, body, content_type, lane, role, headers=None):
        headers = headers or {}
        sha = hashlib.sha256(body).hexdigest()
        blob = Path("blobs") / sha[:2] / sha
        if not (self.root / blob).exists():
            atomic_write(self.root / blob, body)
        title, text, links = "", "", []
        if "html" in content_type:
            encoding = re.search(r"charset=([^;\s]+)", content_type)
            try:
                decoded = body.decode(encoding.group(1).strip('"\'') if encoding else "utf-8")
            except (UnicodeDecodeError, LookupError):
                decoded = body.decode("cp1250", errors="replace")
            page = Page()
            page.feed(decoded)
            title, text, links = page.result()
            status = "EXTRACTED" if len(text.strip()) >= 40 else "NEEDS_REVIEW"
        elif body.startswith(b"%PDF-"):
            status = "NEEDS_PDF_EXTRACTOR"
            if shutil.which("pdftotext"):
                try:
                    result = subprocess.run(["pdftotext", "-layout", str(self.root / blob), "-"],
                                            capture_output=True, timeout=45, check=True)
                    text = result.stdout.decode("utf-8", errors="replace")
                    status = "EXTRACTED" if len(text.strip()) >= 40 else "NEEDS_OCR"
                except (subprocess.SubprocessError, OSError):
                    status = "EXTRACTION_FAILED"
        elif content_type.startswith("text/plain"):
            text = body.decode("utf-8", errors="replace")
            status = "EXTRACTED" if len(text.strip()) >= 40 else "NEEDS_REVIEW"
        else:
            status = "NEEDS_FORMAT_ADAPTER"
        if "html" in content_type and (urlsplit(url).path.lower().endswith(".pdf") or re.search(r"access denied|forbidden|just a moment|service unavailable|pagina inexistenta", folded(title))):
            status = "NEEDS_REVIEW"
        text_path = Path("text") / (sha + ".txt")
        atomic_write(self.root / text_path, text.encode("utf-8"))
        current = self.db.execute("SELECT current_sha FROM documents WHERE url=?", (url,)).fetchone()
        previous_sha = current[0] if current else None
        stamp = now()
        with self.db:
            self.db.execute("""INSERT INTO versions VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(url,sha)
              DO UPDATE SET extraction_status=excluded.extraction_status,text_path=excluded.text_path""",
              (url, sha, stamp, final_url, title, content_type, status, str(blob), str(text_path)))
            self.db.execute("""INSERT INTO documents VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
              current_sha=excluded.current_sha,last_checked=excluded.last_checked,last_success=excluded.last_success,
              status=excluded.status,error=NULL,etag=excluded.etag,modified=excluded.modified""",
              (url, sha, stamp, stamp, "HEALTHY", None, headers.get("ETag"), headers.get("Last-Modified")))
            if role == "document":
                for agent in route(title, text, lane):
                    job_id = hashlib.sha256((url + "\n" + sha + "\n" + agent).encode()).hexdigest()
                    self.db.execute("INSERT OR IGNORE INTO jobs VALUES(?,?,?,?,?,?)",
                                    (job_id, url, sha, agent, "READY" if status == "EXTRACTED" else "WAITING_EXTRACTION", stamp))
                    self.db.execute("UPDATE jobs SET state='READY' WHERE id=? AND state='WAITING_EXTRACTION' AND ?='EXTRACTED'", (job_id, status))
        return {"sha": sha, "previous_sha": previous_sha, "changed": previous_sha != sha,
                "extraction_status": status, "links": links, "title": title}

    def export_queue(self):
        jobs = []
        for row in self.db.execute("""SELECT j.*,v.title,v.final_url,v.blob_path,v.text_path,v.extraction_status,v.first_seen
          FROM jobs j JOIN versions v ON j.url=v.url AND j.sha=v.sha ORDER BY j.created_at,j.id"""):
            job = dict(row)
            job["input_trust"] = "UNTRUSTED_SOURCE_CONTENT"
            job["publication_eligible"] = False
            current = self.db.execute("SELECT current_sha FROM documents WHERE url=?", (row["url"],)).fetchone()[0]
            job["is_current_version"] = current == row["sha"]
            job["actionable"] = job["is_current_version"] and job["state"] == "READY"
            jobs.append(job)
        atomic_write(self.root / "analysis_queue.json", json.dumps({"schema_version": 1, "jobs": jobs}, ensure_ascii=False, indent=2).encode())
        return len(jobs)


class ScopedRedirect(HTTPRedirectHandler):
    def __init__(self, config):
        self.config = config

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl, self.config["allowed_hosts"])
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Fetcher:
    def __init__(self, config):
        self.config, self.robots = config, {}
        self.opener = build_opener(ScopedRedirect(config))
        self.last_request = 0.0

    def request(self, url, headers=None):
        safe_url(url, self.config["allowed_hosts"])
        time.sleep(max(0, self.config["delay_seconds"] - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        req = Request(url, headers={"User-Agent": self.config["user_agent"], **(headers or {})})
        with self.opener.open(req, timeout=self.config["timeout_seconds"]) as response:
            safe_url(response.url, self.config["allowed_hosts"])
            data = response.read(self.config["max_bytes"] + 1)
            if len(data) > self.config["max_bytes"]:
                raise ValueError("Document exceeds configured byte limit")
            return data, response.headers.get("Content-Type", "application/octet-stream"), response.url, dict(response.headers)

    def get(self, url):
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self.robots:
            parser = RobotFileParser(origin + "/robots.txt")
            try:
                body, _, _, _ = self.request(parser.url)
                parser.parse(body.decode("utf-8", errors="replace").splitlines())
                delay = parser.crawl_delay(self.config["user_agent"])
                if delay:
                    self.config["delay_seconds"] = max(self.config["delay_seconds"], delay)
                self.robots[origin] = parser
            except HTTPError as exc:
                if exc.code == 404:
                    parser.parse([])
                    self.robots[origin] = parser
                else:
                    self.robots[origin] = None
                    raise RuntimeError(f"robots.txt unavailable: HTTP {exc.code}") from exc
            except Exception:
                self.robots[origin] = None
                raise
        parser = self.robots[origin]
        if parser is None or not parser.can_fetch(self.config["user_agent"], url):
            raise RuntimeError("robots.txt disallows collection or could not be verified")
        return self.request(url)


def collect(config, data_dir, fetcher=None, force=False):
    if config.get("mode") != "collect_only" or config.get("publication", {}).get("enabled"):
        raise ValueError("Pilot supports collection only; publication migration is not complete")
    fetcher = fetcher or Fetcher(dict(config))
    root = Path(data_dir)
    with run_lock(root / "collector.lock"):
        store = Store(root)
        receipt = {"run_id": uuid.uuid4().hex, "started_at": now(), "module_id": config["module_id"],
                   "mode": "collect_only", "requests": 0, "changed": 0, "errors": [], "depth_limited": [],
                   "coverage_requirements": config.get("coverage_requirements", []), "published": 0}
        cutoff = receipt["started_at"] if force else (datetime.now(timezone.utc) - timedelta(hours=config["interval_hours"])).isoformat(timespec="seconds")
        if force:
            # Reset check scheduling, preserving the last successful version and evidence.
            with store.db:
                store.db.execute("UPDATE documents SET last_checked=NULL")
        for seed in config["seeds"]:
            store.enqueue(safe_url(seed["url"], config["allowed_hosts"]), seed["lane"], seed["role"], 0, seed=True)
        try:
            while receipt["requests"] < config["max_requests"]:
                item = store.due(cutoff)
                if item is None:
                    break
                url = item["url"]
                receipt["requests"] += 1
                try:
                    body, mime, final, headers = fetcher.get(url)
                    result = store.ingest(url, final, body, mime, item["lane"], item["role"], headers)
                    receipt["changed"] += int(result["changed"])
                    for href, label in result["links"]:
                        try:
                            target = safe_url(urljoin(final, href), config["allowed_hosts"])
                        except ValueError:
                            continue
                        kind = link_kind(target, label, item["lane"])
                        if not kind or target == url:
                            continue
                        store.db.execute("INSERT OR REPLACE INTO version_links VALUES(?,?,?,?)", (url, result["sha"], target, label))
                        store.db.commit()
                        if item["depth"] >= config["max_depth"]:
                            receipt["depth_limited"].append(target)
                        else:
                            store.enqueue(target, *kind, item["depth"] + 1)
                except Exception as exc:
                    store.failure(url, exc)
                    receipt["errors"].append({"url": url, "error": str(exc)[:500]})
            receipt["jobs_total"] = store.export_queue()
            receipt["due_remaining"] = store.db.execute("""SELECT count(*) FROM frontier f LEFT JOIN documents d USING(url)
              WHERE d.last_checked IS NULL OR d.last_checked < ?""", (cutoff,)).fetchone()[0]
            receipt["extraction_pending"] = store.db.execute("SELECT count(*) FROM documents d JOIN versions v ON d.url=v.url AND d.current_sha=v.sha WHERE v.extraction_status != 'EXTRACTED'").fetchone()[0]
            receipt["finished_at"] = now()
            receipt["collection_status"] = "DEGRADED" if (receipt["errors"] or receipt["due_remaining"] or receipt["depth_limited"] or receipt["extraction_pending"]) else "BOUNDED_SCAN_COMPLETE"
            receipt["pilot_status"] = "INCOMPLETE_COVERAGE" if any(x["status"] != "verified" for x in config.get("coverage_requirements", [])) else receipt["collection_status"]
            payload = json.dumps(receipt, ensure_ascii=False, indent=2)
            with store.db:
                store.db.execute("INSERT INTO runs VALUES(?,?)", (receipt["run_id"], payload))
            atomic_write(root / "receipts" / (receipt["run_id"] + ".json"), payload.encode())
            atomic_write(root / "latest_run.json", payload.encode())
            return receipt
        finally:
            store.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--config", default=CONFIG, type=Path)
    parser.add_argument("--force", action="store_true", help="Recheck known pages even inside the daily interval")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    receipt = collect(config, args.data_dir, force=args.force)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 2 if receipt["collection_status"] == "DEGRADED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
