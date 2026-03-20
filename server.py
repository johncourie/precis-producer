#!/usr/bin/env python3
"""
server.py — Plant Precis Producer web interface.

Local FastAPI server that loads indexes into memory at startup and serves
a browser UI for searching, selecting sources, and compiling précis PDFs.

Launch: python3 server.py  (or via start.sh)
Port: 7734
"""

import json
import os
import re
import sqlite3
import sys
import time
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from precis_common import load_books, save_books, load_config, BASE_DIR, INDEXES_DIR, OUTPUT_DIR
from compile_precis import compile_precis
from scan_external import scan_directory, scan_directory_iter
from zotero_scan import search_plant, open_zotero_db

# ── In-memory state ──────────────────────────────────────────────────────

class AppState:
    """Holds all indexes and config in memory for the session."""

    def __init__(self):
        self.books = []
        self.indexes = {}       # book_id → index text
        self.config = None
        self.zotero_available = False
        self.loaded_at = None

    def load(self):
        """Load books.json, all indexes, and validate Zotero/external dirs."""
        books_data = load_books()
        self.books = books_data.get("books", [])
        self.config = load_config()
        self.loaded_at = time.time()

        # Load all index files into memory
        self.indexes = {}
        for book in self.books:
            index_file = book.get("index_file")
            if not index_file:
                continue
            index_path = BASE_DIR / index_file
            if index_path.exists():
                self.indexes[book["id"]] = index_path.read_text(errors="replace")

        # Validate Zotero
        self.zotero_available = False
        if self.config and self.config.get("zotero", {}).get("enabled"):
            db_path = os.path.expanduser(self.config["zotero"]["db_path"])
            if os.path.exists(db_path):
                try:
                    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2)
                    conn.execute("PRAGMA query_only = ON")
                    conn.execute("SELECT COUNT(*) FROM items")
                    conn.close()
                    self.zotero_available = True
                except Exception:
                    pass

        print(f"Loaded {len(self.books)} books, {len(self.indexes)} indexes", file=sys.stderr)
        if self.zotero_available:
            print("Zotero: available", file=sys.stderr)
        else:
            print("Zotero: not available", file=sys.stderr)

        # Validate external directories
        if self.config:
            for ext_dir in self.config.get("external_dirs", []):
                path = os.path.expanduser(ext_dir["path"])
                status = "OK" if os.path.isdir(path) else "MISSING"
                print(f"External dir: {path} [{status}]", file=sys.stderr)

    def search_indexes(self, plant_name, synonyms=None):
        """Search in-memory indexes for a plant. Returns matches per book."""
        terms = [plant_name.lower()]
        if synonyms:
            terms.extend(s.lower() for s in synonyms)

        # Also try genus only (first word of binomial)
        parts = plant_name.split()
        if len(parts) >= 2:
            terms.append(parts[0].lower())

        results = []
        for book in self.books:
            index_text = self.indexes.get(book["id"], "")
            if not index_text:
                continue

            index_lower = index_text.lower()
            matched_lines = []
            for term in terms:
                if term in index_lower:
                    # Find matching lines
                    for line in index_text.splitlines():
                        if term in line.lower() and line.strip():
                            matched_lines.append(line.strip())

            if matched_lines:
                # Deduplicate
                seen = set()
                unique = []
                for l in matched_lines:
                    if l not in seen:
                        seen.add(l)
                        unique.append(l)

                results.append({
                    "book_id": book["id"],
                    "short_name": book["short_name"],
                    "file": book["file"],
                    "lens": book.get("lens", []),
                    "offset_mode": book.get("offset_mode", "fixed"),
                    "matched_lines": unique[:10],
                })

        return results

    def get_all_lenses(self):
        """Get set of all lens tags across books."""
        lenses = set()
        for book in self.books:
            lenses.update(book.get("lens", []))
        if self.zotero_available:
            lenses.add("peer_reviewed")
        return sorted(lenses)


state = AppState()


@asynccontextmanager
async def lifespan(app):
    state.load()
    yield


# ── FastAPI app ──────────────────────────────────────────────────────────

app = FastAPI(title="Plant Precis Producer", lifespan=lifespan)


# ── API endpoints ────────────────────────────────────────────────────────

@app.get("/status")
def status():
    """Report loaded books, index freshness, and Zotero availability."""
    books_summary = []
    for book in state.books:
        has_index = book["id"] in state.indexes
        index_size = len(state.indexes.get(book["id"], ""))
        books_summary.append({
            "id": book["id"],
            "short_name": book["short_name"],
            "lens": book.get("lens", []),
            "total_pages": book.get("total_pages"),
            "indexed": has_index,
            "index_chars": index_size,
        })

    return {
        "books": books_summary,
        "book_count": len(state.books),
        "index_count": len(state.indexes),
        "zotero_available": state.zotero_available,
        "loaded_at": state.loaded_at,
        "lenses": state.get_all_lenses(),
    }


class SearchRequest(BaseModel):
    plant_name: str
    synonyms: list[str] = []
    lenses: list[str] = []
    include_zotero: bool = False


@app.post("/search")
def search(req: SearchRequest):
    """Search in-memory indexes and optionally Zotero for a plant."""
    # Filter books by lens if specified
    results = state.search_indexes(req.plant_name, req.synonyms)

    if req.lenses:
        lens_set = set(req.lenses)
        results = [r for r in results if set(r["lens"]) & lens_set]

    # Zotero search
    zotero_results = []
    if req.include_zotero and state.zotero_available:
        zotero_results = search_plant(
            req.plant_name,
            synonyms=req.synonyms,
            config=state.config,
            max_results=10,
        )

    return {
        "book_results": results,
        "zotero_results": zotero_results,
    }


class CompileRequest(BaseModel):
    plant_name: str
    sources: list[dict]


@app.post("/compile")
def compile_endpoint(req: CompileRequest):
    """Compile a précis and return the PDF as a download."""
    manifest = {
        "plant": req.plant_name,
        "sources": req.sources,
    }

    try:
        output_path = compile_precis(manifest)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    if not output_path or not Path(output_path).exists():
        return JSONResponse(status_code=500, content={"error": "Compilation produced no output"})

    pdf_bytes = Path(output_path).read_bytes()
    safe_name = re.sub(r'[^\w\s-]', '', req.plant_name).strip().replace(' ', '_')
    filename = f"{safe_name}_precis.pdf"

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/reload")
def reload_indexes():
    """Reload books.json and all indexes from disk."""
    state.load()
    return {"status": "reloaded", "book_count": len(state.books), "index_count": len(state.indexes)}


# ── Folder browser API ────────────────────────────────────────────────────

@app.get("/browse")
def browse_directory(path: str = "~"):
    """List directories at a given path for the folder picker UI.

    Restricted to the user's home directory tree.
    """
    home = os.path.expanduser("~")
    resolved = os.path.expanduser(path)
    resolved = os.path.realpath(resolved)

    # Safety: restrict to home directory tree
    if not resolved.startswith(home):
        resolved = home

    if not os.path.isdir(resolved):
        resolved = home

    dirs = []
    try:
        for entry in sorted(os.scandir(resolved), key=lambda e: e.name.lower()):
            if entry.name.startswith("."):
                continue
            if entry.is_dir(follow_symlinks=False):
                dirs.append(entry.name)
    except PermissionError:
        pass

    parent = os.path.dirname(resolved)
    if not parent.startswith(home):
        parent = home

    return {
        "current": resolved,
        "parent": parent,
        "dirs": dirs,
        "at_home": resolved == home,
    }


# ── Setup API ────────────────────────────────────────────────────────────

def find_zotero_db():
    """Try known platform-specific Zotero database paths.

    Returns the first path found, or None.
    """
    candidates = [
        os.path.expanduser("~/Zotero/zotero.sqlite"),
        os.path.expanduser("~/.var/app/org.zotero.Zotero/data/zotero/zotero.sqlite"),
    ]
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(os.path.join(appdata, "Zotero", "Zotero", "zotero.sqlite"))
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


@app.get("/setup/status")
def setup_status():
    """Get current config for the setup page."""
    config = load_config() or {"zotero": {"enabled": False}, "external_dirs": []}
    zotero_cfg = config.get("zotero", {})
    configured_db = zotero_cfg.get("db_path", "~/Zotero/zotero.sqlite")
    db_path = os.path.expanduser(configured_db)

    detected = os.path.exists(db_path)
    suggested_path = None
    if not detected:
        found = find_zotero_db()
        if found:
            detected = True
            suggested_path = found

    result = {
        "zotero_detected": detected,
        "zotero_enabled": zotero_cfg.get("enabled", False),
        "zotero_db_path": configured_db,
        "zotero_storage_path": zotero_cfg.get("storage_path", "~/Zotero/storage"),
        "priority_collections": zotero_cfg.get("priority_collections", []),
        "external_dirs": config.get("external_dirs", []),
        "book_count": len(state.books),
        "index_count": len(state.indexes),
    }
    if suggested_path:
        result["zotero_suggested_path"] = suggested_path
    return result


class SetupSave(BaseModel):
    zotero_enabled: bool = False
    zotero_db_path: str = "~/Zotero/zotero.sqlite"
    zotero_storage_path: str = "~/Zotero/storage"
    priority_collections: list[str] = []
    external_dirs: list[dict] = []


@app.post("/setup/save")
def setup_save(req: SetupSave):
    """Save setup configuration, index new PDFs, and stream progress via SSE."""
    config = {
        "zotero": {
            "enabled": req.zotero_enabled,
            "db_path": req.zotero_db_path,
            "storage_path": req.zotero_storage_path,
            "priority_collections": req.priority_collections,
        },
        "external_dirs": req.external_dirs,
    }

    config_path = BASE_DIR / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    def generate():
        new_pdfs = 0
        if req.external_dirs:
            books_data = load_books()
            for dir_config in req.external_dirs:
                for progress in scan_directory_iter(dir_config, books_data):
                    yield f"data: {json.dumps(progress)}\n\n"
                    if progress["event"] == "done":
                        new_pdfs += progress["new_count"]
            if new_pdfs > 0:
                save_books(books_data)

        state.load()
        result = {
            "event": "complete",
            "status": "saved",
            "zotero_available": state.zotero_available,
            "book_count": len(state.books),
            "index_count": len(state.indexes),
            "new_pdfs_indexed": new_pdfs,
        }
        yield f"data: {json.dumps(result)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── HTML UI ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def ui():
    html_path = BASE_DIR / "templates" / "index.html"
    return html_path.read_text()


@app.get("/setup", response_class=HTMLResponse)
def setup_ui():
    html_path = BASE_DIR / "templates" / "setup.html"
    return html_path.read_text()


# ── Main ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("Plant Precis Producer — http://localhost:7734", file=sys.stderr)
    uvicorn.run(app, host="127.0.0.1", port=7734, log_level="warning")
