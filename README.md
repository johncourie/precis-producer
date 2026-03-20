# Precis Producer

A tool for compiling per-plant reference précis from pharmacopoeia and botanical reference PDFs. Given a plant name, it searches pre-extracted indexes across multiple source books, identifies the relevant pages, and compiles them into a single PDF with a generated table of contents.

Built to work with [Claude Code](https://claude.ai/claude-code) as an AI-assisted lookup agent — see `PRECIS_PROMPT.md` for the full prompt.

## Prerequisites

- Python 3.8+
- [pypdf](https://pypi.org/project/pypdf/)
- [reportlab](https://pypi.org/project/reportlab/)

```bash
pip install pypdf reportlab
```

## Setup

1. Clone this repository.
2. Copy `books.example.json` to `books.json`.
3. Place your source PDFs in the project root.
4. Index each book using `index_new_book.py` (see below), or manually create index files in `_indexes/`.

## Usage

### Compile a précis

Create a JSON manifest describing the plant and which pages to extract from each source:

```json
{
  "plant": "Achillea millefolium",
  "sources": [
    {
      "file": "Some Pharmacopoeia.pdf",
      "pages": "209-214",
      "citation": "Author. (Year). Title. pp. 209–214."
    }
  ]
}
```

Then compile:

```bash
python3 compile_precis.py manifest.json
```

The output PDF appears in `precis/`.

**Page numbers** in the manifest are *printed* page numbers from the book's index. The script converts them to PDF page numbers using the offset in `books.json`.

For books with non-linear page numbering (offset mode `"lookup"`), provide a `lookup_key` instead:

```json
{
  "file": "European Pharmacopoeia 5th Ed.pdf",
  "pages": "1-2",
  "lookup_key": "Millefolii herba",
  "citation": "Council of Europe. (2004). European Pharmacopoeia 5th Ed. Millefolii herba."
}
```

### Add a new book

#### Phase 1: Probe

Extract the first and last pages as text to identify where the index/TOC lives:

```bash
python3 index_new_book.py "New Book.pdf" --id newbook --probe-only
```

Inspect the generated text files in `_indexes/` to find index page ranges and entry format.

#### Phase 2: Index

For books with consistent page offsets (most books):

```bash
python3 index_new_book.py "New Book.pdf" \
    --id newbook \
    --short-name "NewBook" \
    --index-pages 5-12 \
    --citation "Author. (Year). Title. pp. {pages}." \
    --monograph-pages "2-4" \
    --notes "Entries by Latin binomial."
```

The script auto-detects the page offset by cross-referencing index entries against the PDF.

For books with non-linear page numbering:

```bash
python3 index_new_book.py "New Book.pdf" \
    --id newbook \
    --short-name "NewBook" \
    --offset-mode lookup \
    --index-pages 900-920 \
    --filter-terms "herba,radix,folium" \
    --citation "Author. (Year). Title. {lookup_key}."
```

#### Phase 3: Verify

Compile a test précis for a plant you know is in the new book and check the extracted pages.

## File structure

```
├── compile_precis.py          # Main compilation script
├── index_new_book.py          # Book indexing script
├── books.json                 # Book registry (your local config, gitignored)
├── books.example.json         # Example book registry
├── PRECIS_PROMPT.md           # Claude Code agent prompt
├── _indexes/                  # Extracted index files (gitignored)
│   ├── bookid.txt             # Text index for each book
│   └── bookid_lookup.json     # Lookup map for non-linear books
├── precis/                    # Generated précis PDFs (gitignored)
└── *.pdf                      # Source PDFs (gitignored)
```

## License

GPL-3.0 — see [LICENSE](LICENSE).
