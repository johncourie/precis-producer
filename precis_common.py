#!/usr/bin/env python3
"""
precis_common.py — Shared utilities for the Plant Precis Producer.

Consolidates books.json/config.json I/O, pdftotext extraction,
and PDF page counting used across multiple scripts.
"""

import json
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent
INDEXES_DIR = BASE_DIR / "_indexes"
OUTPUT_DIR = BASE_DIR / "precis"


def load_books():
    """Load books.json. Returns the full dict (with 'books' key).

    Returns {"books": []} if file doesn't exist.
    """
    config_path = BASE_DIR / "books.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {"books": []}


def save_books(books_data):
    """Write books_data dict to books.json."""
    with open(BASE_DIR / "books.json", "w") as f:
        json.dump(books_data, f, indent=2)


def load_config():
    """Load config.json. Returns None if file doesn't exist."""
    config_path = BASE_DIR / "config.json"
    if not config_path.exists():
        return None
    with open(config_path) as f:
        return json.load(f)


def extract_text_range(pdf_path, start=1, end=None, timeout=120):
    """Extract text from a PDF page range using pdftotext.

    Returns extracted text, or empty string on failure.
    """
    cmd = ['pdftotext', '-f', str(start)]
    if end is not None:
        cmd += ['-l', str(end)]
    cmd += ['-layout', str(pdf_path), '-']

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def get_pdf_page_count(pdf_path):
    """Get total page count of a PDF. Returns None on failure."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        return len(reader.pages)
    except Exception:
        return None
