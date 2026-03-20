#!/usr/bin/env python3
"""
compile_precis.py — Compile a per-plant reference précis from pharmacopoeia PDFs.

Input:  A JSON manifest (from stdin or file) with structure:
        {
          "plant": "Achillea millefolium",
          "lenses": ["traditional", "modern"],    (optional — filter sources)
          "sources": [
            {"file": "...", "pages": "209-212", "citation": "...", "lens": ["modern"]},
            ...
          ]
        }

        Page numbers in the manifest are PRINTED page numbers from each book's index.
        This script handles the offset to PDF page numbers internally via books.json.
        File paths may be relative (to the project dir) or absolute (external/Zotero).

Output: A single PDF in the output directory with:
        - A generated TOC cover page listing each source grouped by lens
        - The extracted pages from each source appended sequentially
"""

import json
import sys
import os
import re
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from precis_common import load_books, BASE_DIR, OUTPUT_DIR


def get_book_by_filename(books, filename):
    """Find a book config entry by PDF filename."""
    for book in books:
        if book["file"] == filename:
            return book
    return None


def load_lookup(book):
    """Load a search-based lookup file for books with offset_mode='lookup'."""
    lookup_path = BASE_DIR / book["lookup_file"]
    if lookup_path.exists():
        with open(lookup_path) as f:
            return json.load(f)
    return {}


def parse_page_range(page_str):
    """Parse a page range string like '209-212' or '209' into (start, end) inclusive."""
    page_str = page_str.strip()
    if '-' in page_str:
        parts = page_str.split('-')
        return int(parts[0]), int(parts[1])
    else:
        return int(page_str), int(page_str)


def printed_to_pdf_pages(book, start_printed, end_printed, lookup_key=None):
    """Convert printed page numbers to 0-indexed PDF page numbers.

    For fixed-offset books: PDF_page_0idx = printed_page + offset - 1
    For lookup books: uses lookup_key to find the base PDF page,
        then 'pages' in the manifest means page count from that start.
    """
    mode = book.get("offset_mode", "fixed")

    if mode == "fixed":
        offset = book["page_offset"]
        start_pdf = start_printed + offset - 1  # 0-indexed
        end_pdf = end_printed + offset - 1
        return start_pdf, end_pdf

    if mode == "lookup" and lookup_key:
        lookup = load_lookup(book)
        if lookup_key in lookup and lookup[lookup_key] is not None:
            base_pdf_page = lookup[lookup_key]  # 1-indexed
            num_pages = end_printed - start_printed
            start_pdf = base_pdf_page - 1  # 0-indexed
            end_pdf = start_pdf + num_pages
            return start_pdf, end_pdf

    raise ValueError(
        f"Cannot resolve pages for {book['file']}. "
        f"Mode={mode}, lookup_key={lookup_key}"
    )


def extract_pages(pdf_path, start_page_0idx, end_page_0idx):
    """Extract pages from a PDF. Returns list of page objects."""
    reader = PdfReader(str(pdf_path))
    total = len(reader.pages)
    start = max(0, start_page_0idx)
    end = min(total - 1, end_page_0idx)
    return [reader.pages[i] for i in range(start, end + 1)]


def build_toc_pdf(plant_name, toc_entries, toc_path):
    """Generate a TOC cover page as a PDF."""
    doc = SimpleDocTemplate(
        str(toc_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=1 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'PrecisTitle', parent=styles['Title'],
        fontSize=18, spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        'PrecisSubtitle', parent=styles['Normal'],
        fontSize=10, textColor=colors.grey, spaceAfter=24,
    )
    citation_style = ParagraphStyle(
        'Citation', parent=styles['Normal'],
        fontSize=9, leading=13, spaceAfter=4,
    )
    page_ref_style = ParagraphStyle(
        'PageRef', parent=styles['Normal'],
        fontSize=9, textColor=colors.Color(0.3, 0.3, 0.3),
        spaceAfter=14, leftIndent=18,
    )

    section_style = ParagraphStyle(
        'SectionHeader', parent=styles['Heading3'],
        fontSize=11, spaceAfter=6, spaceBefore=14,
        textColor=colors.Color(0.2, 0.2, 0.5),
    )

    story = []
    story.append(Paragraph(plant_name, title_style))
    story.append(Paragraph("Reference Pr&eacute;cis", subtitle_style))
    story.append(Spacer(1, 12))

    # Group entries by lens for display
    lens_labels = {
        "traditional": "Traditional Sources",
        "modern": "Modern Pharmacopoeias",
        "peer_reviewed": "Peer-Reviewed Literature",
        "microscopy": "Microscopy References",
    }

    # Check if any entries have lens info
    has_lenses = any(entry.get("lens") for entry in toc_entries)

    if has_lenses:
        # Group by primary lens (first in the array)
        grouped = {}
        for entry in toc_entries:
            primary = entry.get("lens", ["other"])[0] if entry.get("lens") else "other"
            grouped.setdefault(primary, []).append(entry)

        # Display order
        lens_order = ["traditional", "modern", "microscopy", "peer_reviewed", "other"]
        entry_num = 1
        for lens_key in lens_order:
            if lens_key not in grouped:
                continue
            label = lens_labels.get(lens_key, lens_key.replace("_", " ").title())
            story.append(Paragraph(label, section_style))
            for entry in grouped[lens_key]:
                citation_text = f"{entry_num}. {entry['citation']}"
                story.append(Paragraph(citation_text, citation_style))
                page_text = (
                    f"pp. {entry['compiled_start']}&ndash;{entry['compiled_end']} "
                    f"({entry['page_count']} pages)"
                )
                story.append(Paragraph(page_text, page_ref_style))
                entry_num += 1
    else:
        for i, entry in enumerate(toc_entries, 1):
            citation_text = f"{i}. {entry['citation']}"
            story.append(Paragraph(citation_text, citation_style))
            page_text = (
                f"pp. {entry['compiled_start']}&ndash;{entry['compiled_end']} "
                f"({entry['page_count']} pages)"
            )
            story.append(Paragraph(page_text, page_ref_style))

    doc.build(story)


def compile_precis(manifest):
    """Main compilation function."""
    books = load_books()["books"]
    plant_name = manifest["plant"]
    sources = manifest["sources"]

    safe_name = re.sub(r'[^\w\s-]', '', plant_name).strip().replace(' ', '_')
    output_path = OUTPUT_DIR / f"{safe_name}_precis.pdf"
    OUTPUT_DIR.mkdir(exist_ok=True)

    writer = PdfWriter()
    toc_entries = []
    current_page = 2  # Page 1 is the TOC

    for source in sources:
        filename = source["file"]

        # Resolve path: absolute or relative to BASE_DIR
        if os.path.isabs(filename):
            pdf_path = Path(filename)
        else:
            pdf_path = BASE_DIR / filename

        if not pdf_path.exists():
            print(f"WARNING: {pdf_path} not found, skipping.", file=sys.stderr)
            continue

        book = get_book_by_filename(books, filename)
        if book is None:
            # Unregistered source (e.g., Zotero article) — treat as simple PDF
            book = {
                "file": filename,
                "page_offset": 0,
                "offset_mode": "fixed",
                "citation_template": source.get("citation", os.path.basename(filename)),
            }

        page_range = source["pages"]
        start_printed, end_printed = parse_page_range(page_range)

        # lookup_key is used for lookup-mode books (e.g., ep_drug_name)
        lookup_key = source.get("lookup_key") or source.get("ep_drug_name")

        start_0idx, end_0idx = printed_to_pdf_pages(
            book, start_printed, end_printed, lookup_key
        )

        pages = extract_pages(pdf_path, start_0idx, end_0idx)
        page_count = len(pages)

        if page_count == 0:
            print(f"WARNING: No pages extracted from {filename} ({page_range})", file=sys.stderr)
            continue

        # Citation: explicit in manifest > template from books.json > filename
        citation = source.get("citation")
        if not citation:
            template = book.get("citation_template", filename)
            citation = template.replace("{pages}", page_range)
            if lookup_key:
                citation = citation.replace("{ep_drug_name}", lookup_key)
                citation = citation.replace("{lookup_key}", lookup_key)

        # Determine lens for this source
        source_lens = source.get("lens", [])
        if not source_lens and book:
            source_lens = book.get("lens", [])

        toc_entries.append({
            "citation": citation,
            "compiled_start": current_page,
            "compiled_end": current_page + page_count - 1,
            "page_count": page_count,
            "lens": source_lens,
        })

        for page in pages:
            writer.add_page(page)

        print(f"  Added {page_count} pages from {filename} (printed {page_range})", file=sys.stderr)
        current_page += page_count

    if not toc_entries:
        print("ERROR: No pages were extracted from any source.", file=sys.stderr)
        sys.exit(1)

    # Generate TOC
    toc_path = OUTPUT_DIR / "_toc_temp.pdf"
    build_toc_pdf(plant_name, toc_entries, str(toc_path))

    # Merge: TOC first, then extracted pages
    final_writer = PdfWriter()

    toc_reader = PdfReader(str(toc_path))
    for page in toc_reader.pages:
        final_writer.add_page(page)

    for page in writer.pages:
        final_writer.add_page(page)

    with open(output_path, "wb") as f:
        final_writer.write(f)

    # Cleanup temp TOC
    try:
        toc_path.unlink(missing_ok=True)
    except PermissionError:
        pass  # mounted filesystem may not allow delete

    total_pages = len(final_writer.pages)
    print(f"\nCompiled: {output_path}", file=sys.stderr)
    print(f"Total pages: {total_pages} (1 TOC + {total_pages - 1} source pages)", file=sys.stderr)
    return str(output_path)


def main_cli():
    """CLI entry point."""
    if len(sys.argv) > 1:
        manifest_path = sys.argv[1]
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = json.load(sys.stdin)

    compile_precis(manifest)


if __name__ == "__main__":
    main_cli()
