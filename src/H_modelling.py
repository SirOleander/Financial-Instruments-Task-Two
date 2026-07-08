"""DEPRECATED shim — the real module is `fi.features` (modelling-table stage)."""
import sys

from fi.features import *  # noqa: F401,F403
from fi.features import main_modelling as main

if __name__ == "__main__":
    main(sys.argv[1:])
