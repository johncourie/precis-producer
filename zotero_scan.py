#!/usr/bin/env python3
"""
zotero_scan.py — Search a local Zotero library for papers about a plant.

Reads the Zotero SQLite database in READ-ONLY mode. Never modifies Zotero data.

Three-tier search:
  1. Collection match — check subcollections of priority collections
  2. Title search — search item titles for the plant name
  3. Full-text word search — query Zotero's pre-built word index

Output: JSON array of results to stdout, suitable for inclusion in a précis manifest.
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent


def load_config():
    """Load config.json for Zotero settings."""
    config_path = BASE_DIR / "config.json"
    if not config_path.exists():
        return None
    with open(config_path) as f:
        return json.load(f)


def open_zotero_db(db_path):
    """Open Zotero SQLite database in read-only mode."""
    db_path = os.path.expanduser(db_path)
    if not os.path.exists(db_path):
        print(f"ERROR: Zotero database not found at {db_path}", file=sys.stderr)
        sys.exit(1)
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def resolve_attachment_path(conn, attachment_item_id, storage_path):
    """Resolve a Zotero attachment to an absolute filesystem path."""
    row = conn.execute("""
        SELECT ia.path, i.key
        FROM itemAttachments ia
        JOIN items i ON ia.itemID = i.itemID
        WHERE ia.itemID = ?
    """, (attachment_item_id,)).fetchone()

    if not row or not row["path"]:
        return None

    path_field = row["path"]
    att_key = row["key"]
    storage_path = os.path.expanduser(storage_path)

    if path_field.startswith("storage:"):
        filename = path_field[len("storage:"):]
        full_path = os.path.join(storage_path, att_key, filename)
        if os.path.exists(full_path):
            return full_path

    return None


def get_item_metadata(conn, item_id):
    """Get citation metadata for a Zotero item."""
    # Get fields
    fields = {}
    rows = conn.execute("""
        SELECT f.fieldName, idv.value
        FROM itemData id
        JOIN fields f ON id.fieldID = f.fieldID
        JOIN itemDataValues idv ON id.valueID = idv.valueID
        WHERE id.itemID = ?
    """, (item_id,)).fetchall()
    for row in rows:
        fields[row["fieldName"]] = row["value"]

    # Get creators
    creators = conn.execute("""
        SELECT c.firstName, c.lastName, ct.creatorType
        FROM itemCreators ic
        JOIN creators c ON ic.creatorID = c.creatorID
        JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
        WHERE ic.itemID = ?
        ORDER BY ic.orderIndex
    """, (item_id,)).fetchall()

    return fields, creators


def format_citation(fields, creators):
    """Format Zotero metadata into a citation string."""
    # Authors
    if len(creators) == 0:
        author_str = "Unknown"
    elif len(creators) == 1:
        author_str = creators[0]["lastName"]
    elif len(creators) == 2:
        author_str = f"{creators[0]['lastName']} & {creators[1]['lastName']}"
    else:
        author_str = f"{creators[0]['lastName']} et al."

    year = fields.get("date", "n.d.")
    if year and len(year) >= 4:
        year = year[:4]

    title = fields.get("title", "Untitled")
    journal = fields.get("publicationTitle", "")

    citation = f"{author_str}. ({year}). {title}."
    if journal:
        volume = fields.get("volume", "")
        pages = fields.get("pages", "")
        citation += f" {journal}"
        if volume:
            citation += f", {volume}"
        if pages:
            citation += f", {pages}"
        citation += "."

    return citation


def get_item_collections(conn, item_id):
    """Get collection names for an item."""
    rows = conn.execute("""
        SELECT c.collectionName
        FROM collectionItems ci
        JOIN collections c ON ci.collectionID = c.collectionID
        WHERE ci.itemID = ?
    """, (item_id,)).fetchall()
    return [row["collectionName"] for row in rows]


def get_pdf_page_count(pdf_path):
    """Get page count of a PDF."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception:
        return None


def get_pdf_attachments(conn, parent_item_id, storage_path):
    """Get all PDF attachments for a parent item."""
    rows = conn.execute("""
        SELECT ia.itemID as att_id
        FROM itemAttachments ia
        WHERE ia.parentItemID = ?
        AND ia.contentType = 'application/pdf'
    """, (parent_item_id,)).fetchall()

    results = []
    for row in rows:
        path = resolve_attachment_path(conn, row["att_id"], storage_path)
        if path:
            results.append(path)
    return results


def search_collections(conn, plant_name, synonyms, priority_collections, storage_path):
    """Tier 1: Search within priority collection subcollections."""
    results = []
    search_terms = [plant_name] + synonyms

    # Get priority collection IDs
    placeholders = ",".join("?" * len(priority_collections))
    parent_rows = conn.execute(f"""
        SELECT collectionID, collectionName FROM collections
        WHERE collectionName IN ({placeholders})
    """, priority_collections).fetchall()

    if not parent_rows:
        return results

    parent_ids = [r["collectionID"] for r in parent_rows]

    # Get subcollections matching plant name
    sub_rows = conn.execute(f"""
        SELECT collectionID, collectionName FROM collections
        WHERE parentCollectionID IN ({",".join("?" * len(parent_ids))})
    """, parent_ids).fetchall()

    matched_collections = []
    for row in sub_rows:
        name_lower = row["collectionName"].lower()
        for term in search_terms:
            if term.lower() in name_lower or name_lower in term.lower():
                matched_collections.append(row)
                break

    if not matched_collections:
        return results

    # Get items from matched collections
    col_ids = [c["collectionID"] for c in matched_collections]
    placeholders = ",".join("?" * len(col_ids))
    items = conn.execute(f"""
        SELECT DISTINCT ci.itemID
        FROM collectionItems ci
        JOIN items i ON ci.itemID = i.itemID
        LEFT JOIN deletedItems di ON i.itemID = di.itemID
        WHERE di.itemID IS NULL
        AND ci.collectionID IN ({placeholders})
    """, col_ids).fetchall()

    seen = set()
    for item_row in items:
        item_id = item_row["itemID"]
        if item_id in seen:
            continue
        seen.add(item_id)

        pdfs = get_pdf_attachments(conn, item_id, storage_path)
        if not pdfs:
            continue

        fields, creators = get_item_metadata(conn, item_id)
        citation = format_citation(fields, creators)
        collections = get_item_collections(conn, item_id)

        for pdf_path in pdfs:
            page_count = get_pdf_page_count(pdf_path)
            results.append({
                "file": pdf_path,
                "pages": f"1-{page_count}" if page_count else "1-1",
                "citation": citation,
                "lens": ["peer_reviewed"],
                "search_method": "collection",
                "collections": collections,
                "title": fields.get("title", ""),
            })

    return results


def search_titles(conn, plant_name, synonyms, storage_path):
    """Tier 2: Search item titles for the plant name."""
    results = []
    search_terms = [plant_name] + synonyms

    conditions = []
    params = []
    for term in search_terms:
        conditions.append("idv.value LIKE ?")
        params.append(f"%{term}%")

    where = " OR ".join(conditions)

    rows = conn.execute(f"""
        SELECT DISTINCT i.itemID, idv.value as title
        FROM items i
        JOIN itemData id ON i.itemID = id.itemID
        JOIN fields f ON id.fieldID = f.fieldID AND f.fieldName = 'title'
        JOIN itemDataValues idv ON id.valueID = idv.valueID
        LEFT JOIN deletedItems di ON i.itemID = di.itemID
        WHERE di.itemID IS NULL
        AND ({where})
    """, params).fetchall()

    seen = set()
    for row in rows:
        item_id = row["itemID"]
        if item_id in seen:
            continue
        seen.add(item_id)

        pdfs = get_pdf_attachments(conn, item_id, storage_path)
        if not pdfs:
            continue

        fields, creators = get_item_metadata(conn, item_id)
        citation = format_citation(fields, creators)
        collections = get_item_collections(conn, item_id)

        for pdf_path in pdfs:
            page_count = get_pdf_page_count(pdf_path)
            results.append({
                "file": pdf_path,
                "pages": f"1-{page_count}" if page_count else "1-1",
                "citation": citation,
                "lens": ["peer_reviewed"],
                "search_method": "title",
                "collections": collections,
                "title": fields.get("title", row["title"]),
            })

    return results


def search_fulltext(conn, plant_name, storage_path, max_results=10):
    """Tier 3: Full-text word search using Zotero's pre-built index."""
    results = []
    words = [w.lower() for w in plant_name.split() if len(w) > 2]
    if not words:
        return results

    placeholders = ",".join("?" * len(words))

    # fulltextItemWords.itemID is the ATTACHMENT itemID
    rows = conn.execute(f"""
        SELECT fiw.itemID as att_item_id, COUNT(DISTINCT fw.word) as matches
        FROM fulltextWords fw
        JOIN fulltextItemWords fiw ON fw.wordID = fiw.wordID
        WHERE fw.word IN ({placeholders})
        GROUP BY fiw.itemID
        HAVING COUNT(DISTINCT fw.word) = ?
        LIMIT ?
    """, words + [len(words), max_results * 3]).fetchall()

    seen = set()
    for row in rows:
        att_item_id = row["att_item_id"]

        # Resolve to parent item
        parent_row = conn.execute("""
            SELECT parentItemID FROM itemAttachments WHERE itemID = ?
        """, (att_item_id,)).fetchone()

        if not parent_row or not parent_row["parentItemID"]:
            continue

        parent_id = parent_row["parentItemID"]
        if parent_id in seen:
            continue
        seen.add(parent_id)

        pdf_path = resolve_attachment_path(conn, att_item_id, storage_path)
        if not pdf_path:
            continue

        fields, creators = get_item_metadata(conn, parent_id)
        citation = format_citation(fields, creators)
        collections = get_item_collections(conn, parent_id)

        page_count = get_pdf_page_count(pdf_path)
        results.append({
            "file": pdf_path,
            "pages": f"1-{page_count}" if page_count else "1-1",
            "citation": citation,
            "lens": ["peer_reviewed"],
            "search_method": "fulltext",
            "collections": collections,
            "title": fields.get("title", ""),
        })

        if len(results) >= max_results:
            break

    return results


def search_plant(plant_name, synonyms=None, config=None, max_results=20):
    """Search Zotero for papers about a given plant.

    Three-tier search:
      1. Collection match (curated)
      2. Title search (broader)
      3. Full-text word search (broadest)

    Returns deduplicated results with collection results first.
    """
    if config is None:
        config = load_config()
    if not config or not config.get("zotero", {}).get("enabled"):
        return []

    zotero_cfg = config["zotero"]
    db_path = zotero_cfg["db_path"]
    storage_path = zotero_cfg["storage_path"]
    priority_collections = zotero_cfg.get("priority_collections", [])
    synonyms = synonyms or []

    try:
        conn = open_zotero_db(db_path)
    except sqlite3.OperationalError as e:
        print(f"WARNING: Could not open Zotero database: {e}", file=sys.stderr)
        return []

    all_results = []
    seen_paths = set()

    def add_unique(results):
        for r in results:
            if r["file"] not in seen_paths:
                seen_paths.add(r["file"])
                all_results.append(r)

    # Tier 1: Collection search
    if priority_collections:
        print(f"  Searching Zotero collections...", file=sys.stderr)
        add_unique(search_collections(conn, plant_name, synonyms, priority_collections, storage_path))

    # Tier 2: Title search
    print(f"  Searching Zotero titles...", file=sys.stderr)
    add_unique(search_titles(conn, plant_name, synonyms, storage_path))

    # Tier 3: Full-text search (only if we need more results)
    remaining = max_results - len(all_results)
    if remaining > 0:
        print(f"  Searching Zotero full-text index...", file=sys.stderr)
        add_unique(search_fulltext(conn, plant_name, storage_path, max_results=remaining))

    conn.close()
    return all_results[:max_results]


def main_cli():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Search Zotero for papers about a plant (read-only)."
    )
    parser.add_argument("plant_name", help="Plant name to search for (e.g., 'Achillea millefolium')")
    parser.add_argument("--synonyms", default="",
                        help="Comma-separated synonyms (e.g., 'yarrow,milfoil')")
    parser.add_argument("--max-results", type=int, default=20,
                        help="Maximum number of results (default: 20)")

    args = parser.parse_args()
    synonyms = [s.strip() for s in args.synonyms.split(",") if s.strip()]

    results = search_plant(args.plant_name, synonyms=synonyms, max_results=args.max_results)

    print(f"\nFound {len(results)} results.", file=sys.stderr)
    for r in results:
        method = r["search_method"]
        title = r.get("title", "")[:60]
        print(f"  [{method}] {title}", file=sys.stderr)

    # Output JSON to stdout
    json.dump(results, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main_cli()
