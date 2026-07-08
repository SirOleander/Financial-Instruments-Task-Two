#!/usr/bin/env python
"""run_pipeline.py — repo-root entry point for the whole pipeline.

Thin shim: puts src/ on the path and hands off to fi.pipeline. All logic lives in the
package. See `python run_pipeline.py --help` (or --list) for the stages and flags.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from fi.pipeline import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
