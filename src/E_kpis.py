"""DEPRECATED shim — the real module is `fi.features` (kpis stage)."""
import sys

from fi.features import *  # noqa: F401,F403
from fi.features import main_kpis as main

if __name__ == "__main__":
    main(do_write="--write" in sys.argv)
