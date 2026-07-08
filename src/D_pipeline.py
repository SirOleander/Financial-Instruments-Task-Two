"""DEPRECATED shim — the real module is `fi.sec`.

`python src/D_pipeline.py` still performs the full EDGAR rebuild, exactly as before.
Deleted once `run_pipeline.py` is the entry point.
"""
from fi.sec import *  # noqa: F401,F403
from fi.sec import main

if __name__ == "__main__":
    main()
