#!/usr/bin/env python3
"""
index_new_book.py — Index a new PDF for use with the précis compilation system.

This script:
  1. Extracts candidate TOC/index pages from the front and back of the PDF
  2. Attempts to auto-detect the page offset (printed page → PDF page)
  3. Optionally builds a search-based lookup for PDFs with non-linear page numbering
  4. Saves the index text to _indexes/
  5. Registers the book in books.json

Usage:
    python3 index_new_book.py <pdf_file> [options]

    Interactive mode (recommended first time):
        python3 index_new_book.py "My New Pharmacopoeia.pdf"

    With known parameters:
        python3 index_new_book.py "My Book.pdf" \\
            --id mybook \\
            --short-name "MyBook" \\
            --index-pages 5-12 \\
            --offset 15 \\
            --citation "Author. (Year). Title. pp. {pages}." \\
            --monograph-pages "2-4"

    For books with non-linear page numbering (like the EP):
        python3 index_new_book.py "Complex Book.pdf" \\
            --id complexbook \\
            --offset-mode lookup \\
            --index-pages 900-920 \\
            --filter-terms "herba,radix,folium,flos"
"""

import argparse
import json
import subprocess
import re
import sys
from pathlib import Path

from precis_common import (
    load_books, save_books, extract_text_range, get_pdf_page_count,
    BASE_DIR, INDEXES_DIR,
)


def extract_page_text(pdf_path, page):
    """Extract text from a single PDF page."""
    return extract_text_range(pdf_path, page, page)


def detect_offset(pdf_path, index_text, total_pages):
    """
    Auto-detect page offset by finding page-number-like references in the index text,
    then searching for the referenced content in the PDF.

    Returns (offset, confidence) or (None, 0) if detection fails.
    """
    # Find patterns like "Plant Name ... NNN" or "Plant Name    NNN"
    candidates = re.findall(r'([A-Z][a-z]{2,}[a-z\s]+\w+)\s*\.{3,}\s*(\d{1,4})', index_text)
    if not candidates:
        candidates = re.findall(r'([A-Z][a-z]{2,}[a-z\s]+\w+)\s{3,}(\d{1,4})', index_text)

    if not candidates:
        return None, 0

    offsets_found = []

    for name, page_str in candidates[:10]:  # Try first 10 candidates
        printed_page = int(page_str)
        if printed_page < 1 or printed_page > total_pages + 200:
            continue

        name = name.strip()
        # Search a window around the expected page for this name
        for test_offset in range(-100, 200):
            test_page = printed_page + test_offset
            if test_page < 1 or test_page > total_pages:
                continue

            text = extract_page_text(pdf_path, test_page)
            # Check if the first ~50 chars of the name appear on this page
            search_term = name[:30]
            if search_term.lower() in text.lower():
                offsets_found.append(test_offset)
                print(f"  Offset candidate: {name} (printed {printed_page}) "
                      f"found at PDF page {test_page} → offset {test_offset:+d}",
                      file=sys.stderr)
                break

        if len(offsets_found) >= 3:
            break

    if not offsets_found:
        return None, 0

    # Check if offsets are consistent
    from collections import Counter
    counts = Counter(offsets_found)
    most_common_offset, count = counts.most_common(1)[0]

    if count == len(offsets_found):
        return most_common_offset, 1.0  # All agree
    elif count >= len(offsets_found) * 0.5:
        return most_common_offset, 0.5  # Majority agree
    else:
        return None, 0  # No consensus → likely non-linear


def build_search_lookup(pdf_path, index_text, filter_terms=None):
    """
    Build a drug-name → PDF-page lookup by searching the full text dump.
    Used for books with non-linear page numbering.
    """
    print("  Building full-text dump (this may take a few minutes)...", file=sys.stderr)

    result = subprocess.run(
        ['pdftotext', '-layout', str(pdf_path), '-'],
        capture_output=True, text=True, timeout=600
    )
    full_text = result.stdout
    pages = full_text.split('\f')
    print(f"  Full text: {len(pages)} pages", file=sys.stderr)

    # Parse drug/entry names from the index text
    entries = re.findall(r'^([A-Z][^\n]{3,60}?)\s*\.{3,}\s*\d', index_text, re.MULTILINE)

    if filter_terms:
        terms = [t.strip().lower() for t in filter_terms.split(',')]
        entries = [e for e in entries if any(t in e.lower() for t in terms)]

    print(f"  Searching for {len(entries)} index entries...", file=sys.stderr)

    lookup = {}
    for entry_name in entries:
        entry_name = entry_name.strip()
        for i, page_text in enumerate(pages):
            if entry_name in page_text:
                lookup[entry_name] = i + 1  # 1-indexed
                break
        else:
            lookup[entry_name] = None

    found = sum(1 for v in lookup.values() if v is not None)
    print(f"  Mapped {found}/{len(lookup)} entries to PDF pages", file=sys.stderr)
    return lookup


def register_book(book_config):
    """Add or update a book entry in books.json."""
    data = load_books()
    data["books"] = [b for b in data["books"] if b["id"] != book_config["id"]]
    data["books"].append(book_config)
    save_books(data)
    print(f"  Registered '{book_config['id']}' in books.json", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Index a new PDF for the précis compilation system."
    )
    parser.add_argument('pdf_file', help='PDF filename (relative to 642 stuff/)')
    parser.add_argument('--id', help='Short identifier for this book (e.g., "bhp")')
    parser.add_argument('--short-name', help='Display name (e.g., "BHP 1983")')
    parser.add_argument('--index-pages', help='PDF page range for TOC/index (e.g., "5-15")')
    parser.add_argument('--back-index-pages', help='PDF page range for back-of-book index (e.g., "250-260")')
    parser.add_argument('--offset', type=int, help='Fixed page offset (PDF_page = printed_page + offset)')
    parser.add_argument('--offset-mode', choices=['fixed', 'lookup'], default='fixed',
                        help='Page resolution mode')
    parser.add_argument('--citation', help='Citation template. Use {pages} for page range, {lookup_key} for drug name.')
    parser.add_argument('--monograph-pages', default='2-4', help='Typical monograph length (e.g., "2-4")')
    parser.add_argument('--filter-terms', help='Comma-separated terms to filter index entries (for lookup mode)')
    parser.add_argument('--lens', default='', help='Comma-separated lens tags (e.g., "traditional,modern")')
    parser.add_argument('--notes', default='', help='Free-text notes about the book')
    parser.add_argument('--probe-only', action='store_true',
                        help='Only extract candidate index pages for inspection, do not register')

    args = parser.parse_args()
    pdf_path = BASE_DIR / args.pdf_file

    if not pdf_path.exists():
        print(f"ERROR: {pdf_path} not found", file=sys.stderr)
        sys.exit(1)

    INDEXES_DIR.mkdir(exist_ok=True)

    # ── Step 1: Basic info ─────────────────────────────────────────────
    total_pages = get_pdf_page_count(pdf_path)
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Indexing: {args.pdf_file}", file=sys.stderr)
    print(f"Pages: {total_pages}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    # ── Step 2: Extract candidate index pages ──────────────────────────
    if args.probe_only or (not args.index_pages and not args.back_index_pages):
        print("── Front matter (first 15 pages) ──", file=sys.stderr)
        front_text = extract_text_range(pdf_path, 1, 15)
        front_path = INDEXES_DIR / f"{args.id or 'probe'}_front.txt"
        with open(front_path, 'w') as f:
            f.write(front_text)
        print(f"  Saved to {front_path}", file=sys.stderr)

        back_start = max(1, total_pages - 20)
        print(f"\n── Back matter (pages {back_start}-{total_pages}) ──", file=sys.stderr)
        back_text = extract_text_range(pdf_path, back_start, total_pages)
        back_path = INDEXES_DIR / f"{args.id or 'probe'}_back.txt"
        with open(back_path, 'w') as f:
            f.write(back_text)
        print(f"  Saved to {back_path}", file=sys.stderr)

        if args.probe_only:
            print(f"\n── Probe complete ──", file=sys.stderr)
            print(f"Review the front/back text files to identify:", file=sys.stderr)
            print(f"  1. Which pages contain the TOC or index", file=sys.stderr)
            print(f"  2. Whether entries have printed page numbers", file=sys.stderr)
            print(f"Then re-run with --index-pages and/or --back-index-pages", file=sys.stderr)
            return

    # ── Step 3: Extract the actual index ───────────────────────────────
    index_text = ""

    if args.index_pages:
        start, end = map(int, args.index_pages.split('-'))
        print(f"Extracting TOC/index from PDF pages {start}-{end}...", file=sys.stderr)
        index_text += extract_text_range(pdf_path, start, end)

    if args.back_index_pages:
        start, end = map(int, args.back_index_pages.split('-'))
        print(f"Extracting back index from PDF pages {start}-{end}...", file=sys.stderr)
        index_text += "\n" + extract_text_range(pdf_path, start, end)

    if not index_text.strip():
        print("ERROR: No index text extracted. Check page ranges.", file=sys.stderr)
        sys.exit(1)

    book_id = args.id or Path(args.pdf_file).stem.lower().replace(' ', '_')[:20]
    index_path = INDEXES_DIR / f"{book_id}.txt"
    with open(index_path, 'w') as f:
        f.write(index_text)
    print(f"  Index saved to {index_path} ({len(index_text)} bytes)", file=sys.stderr)

    # ── Step 4: Determine page offset ──────────────────────────────────
    offset = args.offset
    offset_mode = args.offset_mode
    lookup_file = None

    if offset is None and offset_mode == 'fixed':
        print("\nAuto-detecting page offset...", file=sys.stderr)
        detected_offset, confidence = detect_offset(pdf_path, index_text, total_pages)

        if detected_offset is not None and confidence >= 0.5:
            offset = detected_offset
            print(f"  Detected offset: {offset:+d} (confidence: {confidence:.0%})", file=sys.stderr)
        else:
            print("  Could not auto-detect a consistent offset.", file=sys.stderr)
            print("  Options:", file=sys.stderr)
            print("    1. Re-run with --offset N (if you know the offset)", file=sys.stderr)
            print("    2. Re-run with --offset-mode lookup (for non-linear page numbering)", file=sys.stderr)
            sys.exit(1)

    if offset_mode == 'lookup':
        print("\nBuilding search-based lookup...", file=sys.stderr)
        lookup = build_search_lookup(pdf_path, index_text, args.filter_terms)
        lookup_filename = f"{book_id}_lookup.json"
        lookup_path = INDEXES_DIR / lookup_filename
        with open(lookup_path, 'w') as f:
            json.dump(lookup, f, indent=2)
        lookup_file = f"_indexes/{lookup_filename}"
        print(f"  Lookup saved to {lookup_path}", file=sys.stderr)

    # ── Step 5: Register in books.json ─────────────────────────────────
    short_name = args.short_name or book_id.upper()
    citation = args.citation or f"{short_name}. pp. {{pages}}."

    lens_tags = [t.strip() for t in args.lens.split(',') if t.strip()] if args.lens else []

    book_config = {
        "id": book_id,
        "file": args.pdf_file,
        "short_name": short_name,
        "lens": lens_tags,
        "citation_template": citation,
        "total_pages": total_pages,
        "page_offset": offset,
        "offset_mode": offset_mode,
        "index_file": f"_indexes/{book_id}.txt",
        "index_pdf_pages": args.index_pages or args.back_index_pages or "",
        "typical_monograph_pages": args.monograph_pages,
        "notes": args.notes,
    }
    if lookup_file:
        book_config["lookup_file"] = lookup_file

    register_book(book_config)

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Indexing complete for: {args.pdf_file}", file=sys.stderr)
    print(f"  ID:              {book_id}", file=sys.stderr)
    print(f"  Index file:      {index_path}", file=sys.stderr)
    print(f"  Offset mode:     {offset_mode}", file=sys.stderr)
    if offset_mode == 'fixed':
        print(f"  Page offset:     {offset:+d}", file=sys.stderr)
    else:
        print(f"  Lookup file:     {lookup_file}", file=sys.stderr)
    print(f"  Registered in:   books.json", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)


if __name__ == "__main__":
    main()
