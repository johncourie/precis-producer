# Precis Producer

A tool for compiling per-plant reference précis from pharmacopoeia and botanical reference PDFs. Given a plant name, it searches pre-extracted indexes across multiple source books, identifies the relevant pages, and compiles them into a single PDF with a generated table of contents.

Built to work with [Claude Code](https://claude.ai/claude-code) as an AI-assisted lookup agent — see `PRECIS_PROMPT.md` for the full prompt.

## Quick Start

```bash
# Clone and install dependencies
git clone https://github.com/johncourie/precis-producer.git
cd precis-producer
pip install pypdf reportlab

# Set up the book registry from the included public domain texts
cp books.example.json books.json

# Compile a test précis (e.g., Yarrow — appears in all 4 included books)
cat > manifest.json << 'EOF'
{
  "plant": "Achillea millefolium",
  "sources": [
    {"file": "potterscyclopaed00wreniala.pdf", "pages": "309-310"},
    {"file": "1919-Ellingwood-American-Materia-Medica-Therapeutics-Pharmacognosy.pdf", "pages": "2-3"},
    {"file": "Felters_Materia_Medica.pdf", "pages": "4-4"}
  ]
}
EOF
python3 compile_precis.py manifest.json
```

The output PDF appears in `precis/`.

## Included Public Domain Texts

These four texts ship with the repository and are ready to use immediately:

| Book | Author | Year | Pages |
|------|--------|------|-------|
| Potter's Cyclopaedia of Botanical Drugs | R.C. Wren | 1907 | 386 |
| American Materia Medica, Therapeutics and Pharmacognosy | F. Ellingwood | 1919 | 470 |
| The Eclectic Materia Medica, Pharmacology and Therapeutics | H.W. Felter | 1922 | 480 |
| King's American Dispensatory | H.W. Felter & J.U. Lloyd | 1898 | 2,977 |

All are in the public domain (pre-1927 US publication).

## Adding Your Own Books

You can add any PDF reference book to the system. Your own books and their indexes are automatically gitignored — only the included public domain texts are tracked.

### Prerequisites

- [poppler](https://poppler.freedesktop.org/) (provides `pdftotext`): `brew install poppler` on macOS

### Phase 1: Probe

Extract sample pages to locate the book's table of contents or index:

```bash
python3 index_new_book.py "New Book.pdf" --id newbook --probe-only
```

Review the generated `_indexes/newbook_front.txt` and `_indexes/newbook_back.txt` to identify:
1. Which pages contain the TOC or alphabetical index
2. The format of entries (Latin names, common names, page numbers)

### Phase 2: Index

**For books with consistent page numbering** (most books):

```bash
python3 index_new_book.py "New Book.pdf" \
    --id newbook \
    --short-name "NewBook" \
    --index-pages 5-12 \
    --citation "Author. (Year). Title. pp. {pages}." \
    --monograph-pages "2-4" \
    --notes "Entries by Latin binomial."
```

The script auto-detects the page offset. If auto-detection fails, provide `--offset N` explicitly.

**For books with non-linear page numbering** (rare):

```bash
python3 index_new_book.py "New Book.pdf" \
    --id newbook \
    --short-name "NewBook" \
    --offset-mode lookup \
    --index-pages 900-920 \
    --filter-terms "herba,radix,folium" \
    --citation "Author. (Year). Title. {lookup_key}."
```

This builds a lookup mapping each entry to its actual PDF page.

### Phase 3: Verify

Compile a test précis for a plant you know is in the new book and check the extracted pages.

## How It Works

1. **`books.json`** — Registry of all source books with metadata: filename, page offset, citation template, index file path, and offset mode (fixed or lookup).

2. **`_indexes/`** — Pre-extracted text indexes from each book's TOC or back-of-book index. These allow fast plant lookup without opening the PDFs.

3. **`compile_precis.py`** — Takes a JSON manifest specifying a plant name and page ranges from each source. Converts printed page numbers to PDF page numbers using the offset from `books.json`, extracts the pages, and compiles them into a single PDF with a generated table of contents.

4. **`index_new_book.py`** — Onboards new PDFs: extracts index text, auto-detects page offsets, and registers the book in `books.json`.

Two offset modes handle different book formats:
- **Fixed**: `PDF_page = printed_page + offset` (most books)
- **Lookup**: A JSON file maps entry names to PDF page numbers (for books with non-linear numbering)

## File Structure

```
├── compile_precis.py          # Main compilation script
├── index_new_book.py          # Book indexing script
├── books.json                 # Book registry (local, gitignored)
├── books.example.json         # Default registry (PD books only)
├── PRECIS_PROMPT.md           # Claude Code agent prompt
│
├── _indexes/                  # Index files
│   ├── potters.txt            # ✓ tracked (public domain)
│   ├── ellingwood.txt         # ✓ tracked (public domain)
│   ├── felter_mm.txt          # ✓ tracked (public domain)
│   ├── kings.txt              # ✓ tracked (public domain)
│   ├── kings_lookup.json      # ✓ tracked (public domain)
│   └── <your_book>.txt        # ✗ gitignored (your additions)
│
├── *.pdf                      # Source PDFs
│   ├── (4 PD texts)           # ✓ tracked (public domain)
│   └── <your_books>.pdf       # ✗ gitignored (your additions)
│
├── precis/                    # Generated output (gitignored)
└── manifest.json              # Per-run input (gitignored)
```

## License

Code: GPL-3.0 — see [LICENSE](LICENSE).

The included public domain texts are not subject to copyright restrictions.
