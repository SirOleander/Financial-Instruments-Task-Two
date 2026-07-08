"""DEPRECATED shim — the real module is `fi.features` (scores stage)."""
import sys

from fi.features import *  # noqa: F401,F403
from fi.features import main_scores as main

if __name__ == "__main__":
    main(do_write="--write" in sys.argv)
