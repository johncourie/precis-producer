#!/usr/bin/env python3
"""
scan_external.py — Scan external directories for PDFs and register them.

Reads config.json for external directory paths. For each directory:
  1. Finds all PDFs
  2. Extracts first few pages as text for indexing
  3. Registers new books in books.json with absolute paths

PDFs stay where they are — no copying.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader

BASE_DIR = Path(__file__).parent
INDEXES_DIR = BASE_DIR / "_indexes"


def load_config():
    """Load config.json."""
    config_path = BASE_DIR / "config.json"
    if not config_path.exists():
        print("ERROR: config.json not found. Copy config.example.json first.", file=sys.stderr)
        sys.exit(1)
    with open(config_path) as f:
        return json.load(f)


def load_books():
    """Load books.json."""
    config_path = BASE_DIR / "books.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {"books": []}


def save_books(books_data):
    """Save books.json."""
    with open(BASE_DIR / "books.json", "w") as f:
        json.dump(books_data, f, indent=2)


def extract_text(pdf_path, start=1, end=5):
    """Extract text from a range of PDF pages using pdftotext."""
    try:
        result = subprocess.run(
            ['pdftotext', '-f', str(start), '-l', str(end), '-layout', str(pdf_path), '-'],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def make_book_id(pdf_path):
    """Generate a book ID from a PDF path."""
    stem = Path(pdf_path).stem.lower()
    # Simplify: keep alphanumeric and underscores, limit length
    clean = "".join(c if c.isalnum() or c == '_' else '_' for c in stem)
    clean = clean.strip('_')[:30]
    return f"ext_{clean}"


def scan_directory(dir_config, books_data):
    """Scan a directory for PDFs and register new ones."""
    dir_path = os.path.expanduser(dir_config["path"])
    lens_tags = dir_config.get("lens", [])
    label = dir_config.get("label", dir_path)

    if not os.path.isdir(dir_path):
        print(f"WARNING: Directory not found: {dir_path}", file=sys.stderr)
        return 0

    # Get already-registered absolute paths
    registered = {b["file"] for b in books_data["books"]}

    new_count = 0
    for root, _, files in os.walk(dir_path):
        for fname in sorted(files):
            if not fname.lower().endswith('.pdf'):
                continue

            abs_path = os.path.join(root, fname)

            if abs_path in registered:
                continue

            print(f"  Indexing: {fname}", file=sys.stderr)

            # Get page count
            try:
                reader = PdfReader(abs_path)
                total_pages = len(reader.pages)
            except Exception as e:
                print(f"    WARNING: Could not read {fname}: {e}", file=sys.stderr)
                continue

            # Extract first 5 pages as index text
            book_id = make_book_id(abs_path)

            # Ensure unique ID
            existing_ids = {b["id"] for b in books_data["books"]}
            if book_id in existing_ids:
                suffix = 1
                while f"{book_id}_{suffix}" in existing_ids:
                    suffix += 1
                book_id = f"{book_id}_{suffix}"

            index_text = extract_text(abs_path, 1, min(5, total_pages))
            INDEXES_DIR.mkdir(exist_ok=True)
            index_path = INDEXES_DIR / f"{book_id}.txt"
            with open(index_path, "w") as f:
                f.write(index_text)

            # Register
            book_config = {
                "id": book_id,
                "file": abs_path,
                "short_name": Path(fname).stem[:40],
                "lens": lens_tags,
                "citation_template": f"{Path(fname).stem}. pp. {{pages}}.",
                "total_pages": total_pages,
                "page_offset": 0,
                "offset_mode": "fixed",
                "index_file": f"_indexes/{book_id}.txt",
                "index_pdf_pages": f"1-{min(5, total_pages)}",
                "typical_monograph_pages": "1-1",
                "notes": f"External: {label}",
                "source": "external",
            }

            books_data["books"].append(book_config)
            new_count += 1
            print(f"    Registered as '{book_id}' ({total_pages} pages)", file=sys.stderr)

    return new_count


def main_cli():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Scan external directories for PDFs and register them in books.json."
    )
    parser.add_argument("--dir", help="Scan a specific directory (overrides config.json)")
    parser.add_argument("--lens", default="", help="Lens tags for --dir (comma-separated)")
    parser.add_argument("--rescan", action="store_true", help="Re-scan all dirs in config.json")

    args = parser.parse_args()
    books_data = load_books()

    if args.dir:
        lens_tags = [t.strip() for t in args.lens.split(",") if t.strip()]
        dir_config = {"path": args.dir, "lens": lens_tags, "label": args.dir}
        count = scan_directory(dir_config, books_data)
    else:
        config = load_config()
        external_dirs = config.get("external_dirs", [])
        if not external_dirs:
            print("No external directories configured in config.json.", file=sys.stderr)
            return

        count = 0
        for dir_config in external_dirs:
            print(f"\nScanning: {dir_config['path']}", file=sys.stderr)
            count += scan_directory(dir_config, books_data)

    if count > 0:
        save_books(books_data)
        print(f"\nRegistered {count} new PDFs in books.json.", file=sys.stderr)
    else:
        print("\nNo new PDFs found.", file=sys.stderr)


if __name__ == "__main__":
    main_cli()
