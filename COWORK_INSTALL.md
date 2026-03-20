# Plant Precis Producer — Cowork Installation Guide

This document defines the installation workflow for Claude Desktop Cowork sessions. Each step calls an idempotent function from `install_steps.sh`. Cowork provides the permission UI; the student never sees a terminal.

## Prerequisites

The student has cloned or downloaded the repository to their machine.

## Installation Steps

Execute each step in order. All functions are idempotent — safe to re-run if a step fails or is interrupted.

### Step 1: Check Python

Verify Python 3.9+ is installed.

```bash
source install_steps.sh && step_check_python
```

If this fails, guide the student to install Python from https://python.org before continuing.

### Step 2: Install poppler

Install the `pdftotext` tool required for PDF text extraction.

```bash
source install_steps.sh && step_install_poppler
```

This will use `brew install poppler` on macOS or `apt-get install poppler-utils` on Linux. Requires permission to install system packages.

### Step 3: Install Python dependencies

Install pypdf, reportlab, fastapi, and uvicorn.

```bash
source install_steps.sh && step_install_python_deps
```

Runs `pip3 install -e .` in the project directory.

### Step 4: Write configuration files

Create `books.json` and `config.json` from templates. Auto-detects Zotero if installed.

```bash
source install_steps.sh && step_write_configs
```

No permissions required — only writes to the project directory.

### Step 5: Verify installation

Run all checks: commands, imports, config files, indexes, server load.

```bash
source install_steps.sh && step_verify_install
```

If any check fails, re-run the corresponding step above.

### Step 6: Launch

Start the web server and open the browser to the first-run setup page.

```bash
source install_steps.sh && step_launch
```

The server runs on `http://localhost:7734`. The first-run setup page (`/setup`) lets the student confirm Zotero integration and add external PDF directories through the browser.

## Post-Install

After launch, the browser opens to `/setup` where the student can:
1. Confirm Zotero connection (if detected)
2. Add external PDF directories via a folder path input
3. Save configuration and proceed to the main search UI

The student can always return to setup via the gear icon or `/setup` URL.

## Troubleshooting

Re-run any step individually — they are idempotent:

```bash
source install_steps.sh && step_install_poppler   # if pdftotext missing
source install_steps.sh && step_install_python_deps  # if imports fail
source install_steps.sh && step_verify_install       # to re-check everything
```
