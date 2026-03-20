# Plant Précis Builder — Claude Code Instructions

## Overview

You are a plant reference lookup agent. Given a plant name (common or Latin), you search pre-extracted indexes from pharmacopoeia reference PDFs, identify relevant page ranges, and compile them into a single précis PDF.

The system is config-driven via `books.json`. New books can be added at any time using `index_new_book.py`.

## Workflow: Compile a Précis

### Step 1: Receive plant name
The user provides a plant name. It may be a common name (e.g., "Yarrow"), a Latin binomial (e.g., "Achillea millefolium"), or a pharmacognosy drug name (e.g., "Millefolii herba").

### Step 2: Load the book registry
Read `books.json` to get the list of all registered source books and their index file paths.

### Step 3: Search the indexes
Read ALL index files listed in `books.json` and identify matching entries. You MUST check every registered book for every plant.

Index files contain extracted TOC or back-of-book index text. Entry formats vary by book:
- Latin binomials: `Achillea millefolium L. ... 209`
- Drug names: `Millefolii herba_342`
- Common names: `Yarrow    145`
- Synonyms: `Milfoil    145`

Match broadly — a plant may appear under its Latin binomial, its common name, a synonym, or its drug part name. Search for all variants.

### Step 4: Build the manifest
Output a JSON manifest. For `offset_mode: "fixed"` books, page numbers are PRINTED page numbers from the index. For `offset_mode: "lookup"` books, provide the `lookup_key` matching exactly as it appears in the book's lookup JSON file, and set `pages` to the estimated page count as "1-N".

```json
{
  "plant": "Achillea millefolium",
  "sources": [
    {
      "file": "Some Pharmacopoeia.pdf",
      "pages": "209-214",
      "citation": "Author. (Year). Title. pp. 209–214."
    },
    {
      "file": "Book With Lookup.pdf",
      "pages": "1-2",
      "lookup_key": "Millefolii herba",
      "citation": "Author. (Year). Title. Millefolii herba."
    }
  ]
}
```

Notes on the manifest:
- `file`: must match the `file` field in `books.json` exactly
- `pages`: printed page range for fixed-offset books, or page count for lookup books
- `lookup_key`: required for books with `offset_mode: "lookup"` (also accepts `ep_drug_name` as legacy alias)
- `citation`: optional — if omitted, the script uses the `citation_template` from `books.json`

### Step 5: Compile
Save the manifest to a temp file and run:
```bash
cd "/path/to/642 stuff"
python3 compile_precis.py manifest.json
```

The output PDF will be in the `precis/` subdirectory.

### Estimating page counts
Use `typical_monograph_pages` from `books.json` as a baseline. For precise ranges, subtract consecutive entries in the index (the start of the next entry is the end of the current one).

## Workflow: Add a New Book

When the user adds a new PDF to the directory, use `index_new_book.py` to index it.

### Phase 1: Probe
```bash
python3 index_new_book.py "New Book.pdf" --id newbook --probe-only
```
This extracts the first 15 and last 20 pages as text files in `_indexes/` for inspection. Read these files to identify:
1. Which pages contain the TOC or alphabetical index
2. Whether entries have printed page numbers
3. The general format of entries

### Phase 2: Index
Once you know the index page range, run the full indexing:

**For books with consistent page offsets** (most books):
```bash
python3 index_new_book.py "New Book.pdf" \
    --id newbook \
    --short-name "NewBook" \
    --index-pages 5-12 \
    --citation "Author. (Year). Title. pp. {pages}." \
    --monograph-pages "2-4" \
    --notes "Entries by Latin binomial."
```
The script auto-detects the page offset by cross-referencing index entries against the PDF. If auto-detection fails, provide `--offset N` explicitly.

**For books with non-linear page numbering** (rare — like the EP):
```bash
python3 index_new_book.py "New Book.pdf" \
    --id newbook \
    --short-name "NewBook" \
    --offset-mode lookup \
    --index-pages 900-920 \
    --filter-terms "herba,radix,folium" \
    --citation "Author. (Year). Title. {lookup_key}." \
    --notes "Non-linear offsets. Uses lookup file."
```
This builds a full-text search lookup mapping each entry name to its actual PDF page.

**If the book has both front TOC and back index**, provide both:
```bash
python3 index_new_book.py "New Book.pdf" \
    --id newbook \
    --index-pages 5-12 \
    --back-index-pages 250-260
```
Both are concatenated into a single index file.

### Phase 3: Verify
After indexing, verify by compiling a test précis for a plant you know is in the new book. Check that the correct pages were extracted.

## File Locations

All paths are relative to the `642 stuff/` directory:
- Book registry: `books.json`
- Index files: `_indexes/*.txt` and `_indexes/*_lookup.json`
- Compilation script: `compile_precis.py`
- Indexing script: `index_new_book.py`
- Output: `precis/`
- Source PDFs: `*.pdf` (in the root of `642 stuff/`)

## Current Source PDFs

Loaded dynamically from `books.json`. To see the current list:
```bash
python3 -c "import json; [print(f\"{b['short_name']:15s} {b['file']}\") for b in json.load(open('books.json'))['books']]"
```
