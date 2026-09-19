#!/usr/bin/env python3
"""Cross-platform entry point for pdfx.

Run this file with any Python 3 interpreter. It puts its own directory on
``sys.path`` itself, so no ``PYTHONPATH`` is needed and one spelling works in
bash, zsh, PowerShell, and cmd:

    python run_pdfx.py init paper.pdf -o work/

``python3 -m pdfx`` stays available for callers that already set PYTHONPATH.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pdfx.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
