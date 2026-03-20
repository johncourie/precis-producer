<div align="center">
  <img src="resources/ppp-logo.jpg" alt="Plant Precis Producer" width="120"/>
  <h1>Plant Precis Producer</h1>
  <p><em>Compile per-plant reference sheets from pharmacopoeia and journal sources</em></p>
</div>

---

## Hey. We need to talk about your workflow.

You're a modern herbalist. You've got all these PDFs — Felter, King's, Ellingwood, Potter's, that AHP monograph you paid actual money for, three Wichtl editions in two languages — and then there's your Zotero library, which at this point is basically a second career. Hundreds of peer-reviewed papers, lovingly tagged, sitting there full of alkaloid profiles and clinical outcomes and ethnobotanical edge cases.

And when you want to look up a specific plant?

You open six PDFs. You Ctrl+F. You lose the thread in King's American Dispensatory because that thing is three thousand pages long and the index is in the back and the page numbers don't match the PDF pages. You tab over to Zotero. You search. You get fourteen results. You open them. You lose the thread again. You check your notes from last semester. The notes are in a folder called "Herbs Final?" on a desktop you no longer have.

That's so, like, *last century*, man.

Plant Precis Producer takes your plant name, reaches into all of your sources simultaneously — traditional pharmacopoeias, modern references, your entire Zotero library, loose PDFs in whatever folder you've been dumping them into — and compiles a single, lens-organized reference document. Traditional sources grouped together. Peer-reviewed separately. Microscopy if you need it. One PDF, table of contents included, ready in seconds.

It runs locally. Your books stay on your machine. Nothing is uploaded anywhere. It's just you, your library, and significantly less yak-shaving.

<div align="center">
  <img src="resources/WebView.png" alt="Plant Precis Producer interface" width="700"/>
  <br/>
  <em>The full interface — search by plant name, select lenses, compile.</em>
</div>

---

## Installation

### Option A — Let Claude Cowork install it for you

If you have [Claude Desktop](https://claude.ai) with Cowork, you don't need to touch a terminal. The repository includes a [`COWORK_INSTALL.md`](COWORK_INSTALL.md) workflow that Cowork can follow:

1. **Open Claude Desktop** and start a Cowork session.
2. **Tell it:** *"Install Plant Precis Producer from https://github.com/johncourie/plant-precis-producer — follow the COWORK_INSTALL.md workflow"*
3. Cowork will execute six supervised steps — checking Python, installing poppler, installing dependencies, writing configs, verifying the install, and launching the server. **Each step pauses for your permission** before doing anything to your system.
4. When done, the browser opens to the setup page at `http://localhost:7734/setup`.

Every step calls an idempotent function from `install_steps.sh`. If something fails, Cowork can safely re-run that step.

On first launch, the setup page will ask you:
- Whether you want to connect your Zotero library (auto-detected if installed)
- Whether you have any other PDF directories you want to include

Both are configured through the browser — no config file editing required.

---

### Option B — Claude Code users

If you already have [Claude Code](https://claude.ai/claude-code) running, you can install and manage Plant Precis Producer from within your Claude Code session.

**To install:**

Open Claude Code and paste this prompt:

```
Clone https://github.com/johncourie/plant-precis-producer, install its 
dependencies (poppler and the Python packages), copy the example config 
files to their working names, and start the local server. Then open 
localhost:7734 in my browser.
```

Claude Code will handle the setup and tell you if anything needs your attention.

**To add your books:**

Put your PDFs in the `plant-precis-producer/` folder on your machine. Then tell Claude Code:

```
Index the new book I added to plant-precis-producer — it's called 
[filename.pdf], it's a [modern / traditional / peer-reviewed] source, 
and the author and year are [X].
```

Claude Code will probe the PDF, find the index pages, extract the index, and register the book. You don't need to know what any of that means.

**To start it again later:**

```
Start the Plant Precis Producer server and open it in my browser.
```

---

### Option C — Command line install

For users comfortable with a terminal.

#### Prerequisites

- Python 3.9+
- **poppler** (provides `pdftotext`):
  - macOS: `brew install poppler`
  - Ubuntu/Debian: `sudo apt install poppler-utils`

#### Install

```bash
git clone https://github.com/johncourie/plant-precis-producer.git
cd plant-precis-producer
make setup
```

Or manually:

```bash
pip install pypdf reportlab fastapi uvicorn
cp books.example.json books.json
cp config.example.json config.json
```

#### Run

```bash
make serve
```

This starts the local server and opens `http://localhost:7734` in your browser.

#### Configure Zotero and external directories

Edit `config.json`:

```json
{
  "zotero": {
    "enabled": true,
    "db_path": "~/Zotero/zotero.sqlite",
    "storage_path": "~/Zotero/storage",
    "priority_collections": ["Herbs"]
  },
  "external_dirs": [
    {
      "path": "~/Documents/herb-papers",
      "lens": ["peer_reviewed"]
    }
  ]
}
```

Then scan your external directories:

```bash
python3 scan_external.py
```

#### Adding a new book (CLI)

```bash
# Phase 1: find the index/TOC pages
python3 index_new_book.py "New Book.pdf" --id newbook --probe-only

# Phase 2: extract and register
python3 index_new_book.py "New Book.pdf" \
    --id newbook \
    --short-name "NewBook" \
    --index-pages 5-12 \
    --lens "modern" \
    --citation "Author. (Year). Title. pp. {pages}."
```

---

## Usage

### Starting the app

Once installed, here's how to open Plant Precis Producer:

- **If you used Cowork to install:** Open Claude Desktop and say: *"Start the Plant Precis Producer server and open it in my browser."*
- **If you used Claude Code:** Open Claude Code in the `plant-precis-producer` folder and say: *"Start the Plant Precis Producer server and open it in my browser."*
- **If you're a terminal user:** Run `make serve` or `./start.sh` from the project folder.

In all cases, a page opens in your browser at `http://localhost:7734`. That's the app. It runs until you close the terminal window or press Ctrl+C.

### First-time setup

The very first time you launch, the app opens to a **Setup** page. Here you can:

1. **Connect Zotero** — If Zotero is installed on your computer, the app will detect it automatically. Flip the toggle to enable it. Your Zotero library is never modified — the app only reads from it.
2. **Add PDF folders** — Click "Add folder", then "Browse..." to navigate to any folder on your computer that contains PDFs you want to search. You can add as many folders as you want. The files stay where they are.
3. Click **Save & Continue** to go to the search page.

You can always get back to setup later by clicking "Setup" in the top-right corner of the search page.

### Searching and compiling

1. **Type a plant name** — common name (Yarrow), Latin name (Achillea millefolium), or drug name (Millefolii herba) all work.
2. **Check the lenses** you want — traditional, modern, peer-reviewed, microscopy. Check all of them if you want everything.
3. **Click Search** — the app searches all your books and (if enabled) your Zotero library.
4. **Review the results** — they're grouped by lens. Each result shows the book name and the matching index entry. Adjust the page ranges if needed.
5. **Click Compile Precis** — a PDF downloads to your computer. It includes a table of contents and all the selected pages from your sources, organized by lens.

That's it. You now have a single reference document for that plant, compiled from all your sources.

---

## Included public domain texts

Four texts ship with the repository, pre-indexed and ready to use:

| Book | Author | Year |
|---|---|---|
| Potter's Cyclopaedia of Botanical Drugs | R.C. Wren | 1907 |
| American Materia Medica, Therapeutics and Pharmacognosy | F. Ellingwood | 1919 |
| The Eclectic Materia Medica, Pharmacology and Therapeutics | H.W. Felter | 1922 |
| King's American Dispensatory | H.W. Felter & J.U. Lloyd | 1898 |

---

## Lenses

Each source is tagged with one or more lenses that describe its perspective:

| Lens | Description | Examples |
|---|---|---|
| `traditional` | Historical/eclectic texts (pre-1930) | Ellingwood, Felter, King's, Potter's |
| `modern` | Contemporary pharmacopoeias | AHP, BHP, Wichtl, EP |
| `peer_reviewed` | Journal articles | Zotero library, external papers |
| `microscopy` | Microscopy atlases | AHP, Atlas (Jackson) |

The compiled précis groups sources by lens in the table of contents.

---

## How it works

1. **`books.json`** — Registry of all source books with lens tags, page offsets, and citation templates.
2. **`config.json`** — System settings: Zotero path, external directories, lens definitions.
3. **`_indexes/`** — Pre-extracted text indexes loaded into memory at startup for fast plant lookup. Never rebuilt per-request.
4. **`compile_precis.py`** — Takes a manifest, extracts pages from PDFs, compiles into a single PDF with a lens-grouped table of contents.
5. **`zotero_scan.py`** — Searches Zotero's SQLite database read-only.
6. **`scan_external.py`** — Scans external directories and registers PDFs.

---

## License

Code: GPL-3.0 — see [LICENSE](LICENSE).  
Included public domain texts are not subject to copyright restrictions.
