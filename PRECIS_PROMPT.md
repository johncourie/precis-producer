# Plant Précis Builder — Claude Code Instructions

## Overview

You are a plant reference lookup agent. Given a plant name (common or Latin), you search pre-extracted indexes from pharmacopoeia reference PDFs and optionally a Zotero library, identify relevant page ranges, and compile them into a single précis PDF organized by lens (traditional, modern, peer-reviewed).

The system is config-driven via `books.json` and `config.json`.

## Workflow: Compile a Précis

### Step 1: Receive plant name
The user provides a plant name. It may be a common name (e.g., "Yarrow"), a Latin binomial (e.g., "Achillea millefolium"), or a pharmacognosy drug name (e.g., "Millefolii herba").

### Step 2: Determine lenses
Ask the user which lenses to include. Read `config.json` for available lenses and defaults.

Available lenses:
- **traditional** — Historical/eclectic texts (pre-1930): Ellingwood, Felter, King's, Potter's
- **modern** — Contemporary pharmacopoeias: AHP, BHP, Wichtl, Atlas, EP
- **peer_reviewed** — Journal articles from Zotero
- **microscopy** — Microscopy atlases: AHP, Atlas

Default lenses come from `config.json` `default_lenses`. If the user says "all", use all available lenses.

### Step 3: Search book indexes (filtered by lens)
Read `books.json` and filter books by the requested lenses. A book matches if any of its `lens` tags overlap with the requested lenses.

Read matching index files and identify entries. You MUST check every matching book.

Index files contain extracted TOC or back-of-book index text. Entry formats vary:
- Latin binomials: `Achillea millefolium L. ... 209`
- Drug names: `Millefolii herba_342`
- Common names: `Yarrow    145`
- Synonyms: `Milfoil    145`

Match broadly — a plant may appear under its Latin binomial, its common name, a synonym, or its drug part name.

### Step 4: Search Zotero (if peer_reviewed lens is requested)
If the `peer_reviewed` lens is included and Zotero is enabled in `config.json`:

```bash
python3 zotero_scan.py "Achillea millefolium" --synonyms "yarrow,milfoil" --max-results 10
```

This returns a JSON array of matching papers with file paths, citations, and page counts. Present the results to the user and let them select which papers to include.

Zotero results are read-only — the Zotero database is never modified.

### Step 5: Build the manifest
Output a JSON manifest with lens metadata:

```json
{
  "plant": "Achillea millefolium",
  "lenses": ["traditional", "modern", "peer_reviewed"],
  "sources": [
    {
      "file": "potterscyclopaed00wreniala.pdf",
      "pages": "309-310",
      "lens": ["traditional"]
    },
    {
      "file": "British herbal pharmacopoedia.pdf",
      "pages": "145-146",
      "lens": ["modern"]
    },
    {
      "file": "/Users/user/Zotero/storage/XPN5CPW5/paper.pdf",
      "pages": "1-11",
      "citation": "Moradi et al. (2024). The Impact of Achillea...",
      "lens": ["peer_reviewed"]
    }
  ]
}
```

Notes on the manifest:
- `file`: relative path for books in the project directory, absolute path for Zotero/external sources
- `pages`: printed page range for fixed-offset books, page count for lookup books, or full range for articles
- `lookup_key`: required for books with `offset_mode: "lookup"` (also accepts `ep_drug_name` as legacy alias)
- `citation`: optional for registered books (uses template), required for Zotero/external sources
- `lens`: optional — used to group sources in the TOC

### Step 6: Compile
```bash
python3 compile_precis.py manifest.json
```

The output PDF will be in `precis/` with sources grouped by lens in the table of contents.

### Estimating page counts
Use `typical_monograph_pages` from `books.json` as a baseline. For precise ranges, subtract consecutive entries in the index.

### Presenting results to the user
Organize search results by lens when presenting:

```
=== Traditional Sources ===
1. Potter's: pp. 309-310 (YARROW)
2. Ellingwood: pp. 2-3 (ACHILLEA)

=== Modern Sources ===
3. BHP: pp. 145-146 (Achillea millefolium)
4. Wichtl: pp. 342-344 (Millefolii herba)

=== Peer-Reviewed Literature ===
5. Moradi et al. (2024) — from Zotero [Achillea Millefolium collection]
6. Ghasemi et al. (2023) — from Zotero [title search]
```

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
    --lens "modern" \
    --citation "Author. (Year). Title. pp. {pages}." \
    --monograph-pages "2-4" \
    --notes "Entries by Latin binomial."
```
The script auto-detects the page offset. If auto-detection fails, provide `--offset N` explicitly.

**For books with non-linear page numbering** (rare — like the EP):
```bash
python3 index_new_book.py "New Book.pdf" \
    --id newbook \
    --short-name "NewBook" \
    --offset-mode lookup \
    --index-pages 900-920 \
    --lens "modern" \
    --filter-terms "herba,radix,folium" \
    --citation "Author. (Year). Title. {lookup_key}." \
    --notes "Non-linear offsets. Uses lookup file."
```

### Phase 3: Verify
After indexing, verify by compiling a test précis for a plant you know is in the new book.

## Workflow: Scan External Directories

To index PDFs from an external directory (e.g., ~/Documents/herb-papers/):
```bash
python3 scan_external.py --dir ~/Documents/herb-papers --lens peer_reviewed
```
Or configure directories in `config.json` and run:
```bash
python3 scan_external.py
```

PDFs stay in their original location — only index text and registry entries are created locally.

## File Locations

- Book registry: `books.json`
- System config: `config.json`
- Index files: `_indexes/*.txt` and `_indexes/*_lookup.json`
- Scripts: `compile_precis.py`, `index_new_book.py`, `zotero_scan.py`, `scan_external.py`
- Output: `precis/`

## Current Source PDFs

Loaded dynamically from `books.json`. To see the current list with lenses:
```bash
python3 -c "import json; [print(f\"{b['short_name']:15s} {','.join(b.get('lens',[])):20s} {b['file'][:60]}\") for b in json.load(open('books.json'))['books']]"
```
