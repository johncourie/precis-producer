# Plant Precis Producer

A tool for compiling per-plant reference précis from pharmacopoeia PDFs, Zotero libraries, and external directories. Sources can be viewed through different **lenses** — traditional, modern, or peer-reviewed — giving you control over the perspective of your research compilation.

Built to work with [Claude Code](https://claude.ai/claude-code) as an AI-assisted lookup agent — see `PRECIS_PROMPT.md` for the full prompt.

## Setup

### Prerequisites

- **Python 3.9+**
- **poppler** (provides `pdftotext`):
  - macOS: `brew install poppler`
  - Ubuntu/Debian: `sudo apt install poppler-utils`

### Install

```bash
git clone https://github.com/johncourie/plant-precis-producer.git
cd plant-precis-producer
make setup
```

Or manually:

```bash
pip install pypdf reportlab
cp books.example.json books.json
cp config.example.json config.json
```

### Configure (optional)

Edit `config.json` to:
- Enable **Zotero integration** (if Zotero is installed locally)
- Add **external directories** containing your own PDFs
- Set **default lenses** for compilation

## Quick Start

The repo includes 4 public domain texts ready to use:

```bash
# Compile a test précis for Yarrow
cat > manifest.json << 'EOF'
{
  "plant": "Achillea millefolium",
  "lenses": ["traditional"],
  "sources": [
    {"file": "potterscyclopaed00wreniala.pdf", "pages": "309-310", "lens": ["traditional"]},
    {"file": "1919-Ellingwood-American-Materia-Medica-Therapeutics-Pharmacognosy.pdf", "pages": "2-3", "lens": ["traditional"]},
    {"file": "Felters_Materia_Medica.pdf", "pages": "4-4", "lens": ["traditional"]}
  ]
}
EOF
python3 compile_precis.py manifest.json
```

Output appears in `precis/` with sources grouped by lens in the table of contents.

## Lenses

Each book is tagged with one or more **lenses** that describe its perspective:

| Lens | Description | Examples |
|------|-------------|----------|
| `traditional` | Historical/eclectic texts (pre-1930) | Ellingwood, Felter, King's, Potter's |
| `modern` | Contemporary pharmacopoeias | AHP, BHP, Wichtl, EP |
| `peer_reviewed` | Journal articles | Zotero library, external papers |
| `microscopy` | Microscopy atlases | AHP, Atlas (Jackson) |

When compiling a précis, specify which lenses to include. The table of contents groups sources by lens.

## Included Public Domain Texts

These four texts ship with the repository (`traditional` lens):

| Book | Author | Year | Pages |
|------|--------|------|-------|
| Potter's Cyclopaedia of Botanical Drugs | R.C. Wren | 1907 | 386 |
| American Materia Medica, Therapeutics and Pharmacognosy | F. Ellingwood | 1919 | 470 |
| The Eclectic Materia Medica, Pharmacology and Therapeutics | H.W. Felter | 1922 | 480 |
| King's American Dispensatory | H.W. Felter & J.U. Lloyd | 1898 | 2,977 |

## Adding Your Own Books

Your own books and their indexes are automatically gitignored.

### Probe, Index, Verify

```bash
# Phase 1: Probe — find the index/TOC pages
python3 index_new_book.py "New Book.pdf" --id newbook --probe-only

# Phase 2: Index — extract and register
python3 index_new_book.py "New Book.pdf" \
    --id newbook \
    --short-name "NewBook" \
    --index-pages 5-12 \
    --lens "modern" \
    --citation "Author. (Year). Title. pp. {pages}."

# Phase 3: Verify — compile a test précis
```

The script auto-detects page offsets. If auto-detection fails, provide `--offset N`.

## Zotero Integration

If you have [Zotero](https://www.zotero.org/) installed locally, the system can search your library for peer-reviewed papers about a plant.

1. Enable in `config.json`:
   ```json
   {
     "zotero": {
       "enabled": true,
       "db_path": "~/Zotero/zotero.sqlite",
       "storage_path": "~/Zotero/storage",
       "priority_collections": ["Herbs"]
     }
   }
   ```

2. Search:
   ```bash
   python3 zotero_scan.py "Achillea millefolium" --synonyms "yarrow,milfoil"
   ```

3. Results are returned as JSON, ready for inclusion in a manifest.

Zotero access is **strictly read-only** — the database is never modified.

## External Directories

Register directories of loose PDFs without copying them:

```bash
# One-off scan
python3 scan_external.py --dir ~/Documents/herb-papers --lens peer_reviewed

# Or configure in config.json and scan all
python3 scan_external.py
```

PDFs stay where they are. Only index text and registry entries are created locally.

## How It Works

1. **`books.json`** — Registry of all source books with lens tags, page offsets, and citation templates.
2. **`config.json`** — System settings: Zotero path, external directories, lens definitions.
3. **`_indexes/`** — Pre-extracted text indexes for fast plant lookup.
4. **`compile_precis.py`** — Takes a JSON manifest, extracts pages from PDFs, compiles into a single PDF with a lens-grouped table of contents.
5. **`zotero_scan.py`** — Searches Zotero's SQLite database (read-only) using collection match, title search, and full-text word search.
6. **`scan_external.py`** — Scans external directories and registers PDFs in books.json.

## File Structure

```
├── compile_precis.py          # Main compilation script
├── index_new_book.py          # Book indexing script
├── zotero_scan.py             # Zotero search (read-only)
├── scan_external.py           # External directory scanner
├── pyproject.toml             # Python packaging
├── Makefile                   # Setup automation
│
├── books.json                 # Book registry (local, gitignored)
├── books.example.json         # Default registry (PD books)
├── config.json                # System config (local, gitignored)
├── config.example.json        # Config template
├── PRECIS_PROMPT.md           # Claude Code agent prompt
│
├── _indexes/                  # Index files
│   ├── potters.txt            # ✓ tracked (public domain)
│   ├── ellingwood.txt         # ✓ tracked
│   ├── felter_mm.txt          # ✓ tracked
│   ├── kings.txt              # ✓ tracked
│   ├── kings_lookup.json      # ✓ tracked
│   └── <your_book>.txt        # ✗ gitignored
│
├── *.pdf                      # Source PDFs
│   ├── (4 PD texts)           # ✓ tracked
│   └── <your_books>.pdf       # ✗ gitignored
│
├── precis/                    # Generated output (gitignored)
└── manifest.json              # Per-run input (gitignored)
```

## License

Code: GPL-3.0 — see [LICENSE](LICENSE).

The included public domain texts are not subject to copyright restrictions.
