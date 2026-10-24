"""Inspectable SQLite chunks and a persisted term index, ranked with BM25.

Only the runbook directory, service catalogue and sanitized memory store are
inputs. Retrieval never loads a diagnostic fixture or an injection journal.
Dense retrieval is optional and disabled here; no model download is attempted.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any

from rank_bm25 import BM25Okapi
import yaml

from tools.redact import is_sensitive, sanitize

ROOT = Path(__file__).resolve().parents[1]
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,180}\Z")
_STOPWORDS = frozenset("a an and are as at be by for from in is it of on or that the to with".split())


def tokens(text: str) -> list[str]:
    """Keep service/query identifiers and their parts; normalize simple plurals."""
    words = re.findall(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", text.casefold())
    result = []
    for word in words:
        for part in (word, *re.split(r"[-_]", word)) if "-" in word or "_" in word else (word,):
            if part not in _STOPWORDS:
                result.append(part[:-1] if len(part) > 4 and part.endswith("s") and not part.endswith("ss") else part)
    return result


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _section(title: str) -> str:
    title = title.casefold().strip()
    aliases = {"allowed remediation": "remediation", "what to check first": "investigation",
               "how to confirm": "confirmation", "verification criteria": "verification",
               "known pitfalls": "pitfalls"}
    return aliases.get(title, re.sub(r"[^a-z0-9]+", "-", title).strip("-"))


class KnowledgeIndex:
    def __init__(self, path: str | Path | None = None, *, root: str | Path | None = None):
        self.root = Path(root).resolve() if root is not None else ROOT
        self.path = Path(path) if path is not None else self.root / "knowledge" / "index.sqlite"

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, document_id TEXT NOT NULL,
                text TEXT NOT NULL, file TEXT NOT NULL, section TEXT NOT NULL,
                version TEXT NOT NULL, sha256 TEXT NOT NULL, tokens TEXT NOT NULL,
                embedding BLOB, attributes TEXT NOT NULL DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS terms (
                term TEXT NOT NULL, chunk_id TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
                frequency INTEGER NOT NULL, PRIMARY KEY(term, chunk_id)
            );
            CREATE INDEX IF NOT EXISTS chunks_kind ON chunks(kind);
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        if "attributes" not in {row[1] for row in db.execute("PRAGMA table_info(chunks)")}:
            db.execute("ALTER TABLE chunks ADD COLUMN attributes TEXT NOT NULL DEFAULT '{}'")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return str(path.resolve())

    @staticmethod
    def _write(db: sqlite3.Connection, chunk: dict[str, Any]) -> None:
        term_list = chunk.pop("_tokens")
        db.execute("DELETE FROM chunks WHERE id=?", (chunk["id"],))
        db.execute("""INSERT INTO chunks
            (id,kind,document_id,text,file,section,version,sha256,tokens,attributes)
            VALUES (:id,:kind,:document_id,:text,:file,:section,:version,:sha256,:tokens,:attributes)""",
            {**chunk, "tokens": _json(term_list), "attributes": _json(chunk.get("attributes", {}))})
        db.executemany("INSERT INTO terms(term,chunk_id,frequency) VALUES (?,?,?)",
                       [(term, chunk["id"], count) for term, count in Counter(term_list).items()])

    def _runbook_chunks(self, path: Path) -> list[dict[str, Any]]:
        if path.is_symlink() or not path.resolve().is_relative_to((self.root / "knowledge" / "runbooks").resolve()):
            raise ValueError("Runbook sources must remain inside the runbook directory")
        raw = path.read_text(encoding="utf-8-sig")
        if is_sensitive(raw):
            raise ValueError(f"Excluded diagnostic control content in {path.name}")
        match = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", raw, re.S)
        if not match:
            raise ValueError(f"Missing runbook front matter: {path.name}")
        meta = yaml.safe_load(match[1])
        if not isinstance(meta, dict) or not all(key in meta for key in ("id", "applies_to", "category", "version")):
            raise ValueError(f"Incomplete runbook front matter: {path.name}")
        if not isinstance(meta["id"], str) or not _SAFE_ID.fullmatch(meta["id"]):
            raise ValueError(f"Unsafe runbook identifier in {path.name}")
        if not isinstance(meta["applies_to"], list) or not all(isinstance(s, str) for s in meta["applies_to"]):
            raise ValueError(f"Invalid applies_to in {path.name}")
        body = match[2]
        headings = list(re.finditer(r"^## (.+)$", body, re.M))
        if not headings:
            raise ValueError(f"Runbook has no sections: {path.name}")
        title = body[:headings[0].start()].strip()
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        result, seen = [], set()
        for position, heading in enumerate(headings):
            section = _section(heading[1])
            if section in seen:
                raise ValueError(f"Duplicate section in {path.name}: {section}")
            seen.add(section)
            stop = headings[position + 1].start() if position + 1 < len(headings) else len(body)
            text = title + "\n\n" + body[heading.start():stop].strip()
            result.append({"id": f"kb:{meta['id']}#{section}", "kind": "runbook",
                           "document_id": meta["id"], "text": text,
                           "file": self._relative(path), "section": section,
                           "version": str(meta["version"]), "sha256": digest,
                           "attributes": {"action_types": meta.get("action_types", []),
                                          "applies_to": list(meta["applies_to"]),
                                          "category": meta["category"]},
                           "_tokens": tokens(text + " " + _json(meta))})
        return result

    def _memory_chunk(self, record: dict[str, Any], file: str | Path | None = None) -> dict[str, Any]:
        clean = sanitize(record)
        identity = clean.get("incident_id") if isinstance(clean, dict) else None
        if not isinstance(identity, str) or not _SAFE_ID.fullmatch(identity):
            raise ValueError("Memory must have a safe incident_id")
        text = _json(clean)
        path = Path(file) if file is not None else self.root / "memory" / "store" / f"{identity}.json"
        return {"id": f"mem:{identity}", "kind": "memory", "document_id": identity,
                "text": text, "file": self._relative(path), "section": "summary",
                "version": str(clean.get("schema_version", clean.get("version", "1"))),
                "attributes": {key: clean[key] for key in ("component", "category", "outcome") if key in clean},
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "_tokens": tokens(text)}

    def build(self) -> dict[str, Any]:
        started = time.perf_counter()
        chunks: list[dict[str, Any]] = []
        paths = sorted((self.root / "knowledge" / "runbooks").glob("*.md"))
        identities = set()
        for path in paths:
            parsed = self._runbook_chunks(path)
            identity = parsed[0]["document_id"]
            if identity in identities:
                raise ValueError(f"Duplicate runbook identifier: {identity}")
            identities.add(identity)
            chunks.extend(parsed)
        catalogue_path = self.root / "knowledge" / "services.yaml"
        if catalogue_path.is_symlink():
            raise ValueError("The service catalogue must be a regular local file")
        catalogue = yaml.safe_load(catalogue_path.read_text(encoding="utf-8"))
        if is_sensitive(catalogue):
            raise ValueError("Service catalogue contains excluded diagnostic control content")
        services = catalogue["services"]
        for name, service in sorted(services.items()):
            text = _json({"service": name, **service})
            chunks.append({"id": f"kb:service-{name}#overview", "kind": "service", "document_id": name,
                           "text": text, "file": self._relative(catalogue_path), "section": "overview",
                           "version": str(catalogue.get("version", "1")),
                           "sha256": hashlib.sha256(text.encode()).hexdigest(), "_tokens": tokens(text)})
        warnings = []
        for path in sorted((self.root / "memory" / "store").glob("*.json")):
            try:
                if path.is_symlink():
                    raise ValueError("Symlinks are not memory records")
                chunks.append(self._memory_chunk(json.loads(path.read_text(encoding="utf-8")), file=path))
            except (ValueError, OSError, TypeError) as exc:
                warnings.append(f"Skipped invalid memory {path.name}: {type(exc).__name__}")
        with self._connect() as db:
            db.execute("DELETE FROM chunks")
            for chunk in chunks:
                self._write(db, chunk)
            db.execute("INSERT OR REPLACE INTO metadata VALUES ('retrieval_mode','bm25')")
            db.execute("INSERT OR REPLACE INTO metadata VALUES ('catalogue_provenance',?)",
                       (_json(catalogue.get("source", {})),))
        return {"runbooks": len(paths), "services": len(services),
                "memories": sum(chunk["kind"] == "memory" for chunk in chunks),
                "chunks": len(chunks), "seconds": round(time.perf_counter() - started, 4),
                "mode": "bm25", "warnings": warnings}

    def upsert_memory(self, record: dict[str, Any], *, file: str | Path | None = None) -> None:
        if not self.path.exists():
            self.build()
        chunk = self._memory_chunk(record, file)
        with self._connect() as db:
            self._write(db, chunk)

    def search(self, query: str, *, section: str | None = None, runbook_k: int = 3,
               memory_k: int = 3, service_k: int = 1) -> dict[str, Any]:
        if not isinstance(query, str):
            raise TypeError("Query must be text")
        # Drop sensitive lines wholesale: surrounding setting values cannot survive.
        query = "\n".join(line for line in query.splitlines() if not is_sensitive(line))
        result: dict[str, Any] = {"runbook_refs": [], "memory_refs": [], "service_refs": [],
                                  "mode": "bm25", "warnings": []}
        if not query.strip():
            return result
        if not self.path.exists():
            result["warnings"] = self.build()["warnings"]
        with self._connect() as db:
            rows = db.execute("SELECT * FROM chunks ORDER BY id").fetchall()
        if not rows:
            return result
        corpus = [json.loads(row["tokens"]) for row in rows]
        scores = BM25Okapi(corpus).get_scores(tokens(query))
        ranked = sorted(zip(rows, scores), key=lambda pair: (-float(pair[1]), pair[0]["id"]))
        limits = {"runbook": ("runbook_refs", max(0, runbook_k)),
                  "memory": ("memory_refs", max(0, memory_k)), "service": ("service_refs", max(0, service_k))}
        seen: set[tuple[str, str]] = set()
        for row, score in ranked:
            key, limit = limits[row["kind"]]
            if score <= 0 or len(result[key]) >= limit or (row["kind"], row["document_id"]) in seen:
                continue
            if row["kind"] == "runbook" and section and row["section"] != section:
                continue
            seen.add((row["kind"], row["document_id"]))
            result[key].append({key: row[key] for key in ("id", "kind", "text", "file", "section", "version", "sha256")}
                               | {"score": round(float(score), 6)} | json.loads(row["attributes"]))
        return result

    def explain(self, report: dict[str, Any]) -> dict[str, Any]:
        """Explain retained citations without requiring mutable current index state."""
        clean = sanitize(report) or {}
        return {"incident_id": clean.get("incident_id"),
                "knowledge_consulted": clean.get("knowledge_consulted", {}),
                "runbook_refs": clean.get("runbook_refs", []), "memory_refs": clean.get("memory_refs", [])}
