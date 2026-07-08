"""DEPRECATED shim — the real module is `fi.features` (target stage)."""
import sys

from fi.features import *  # noqa: F401,F403
from fi.features import main_target as main

if __name__ == "__main__":
    main(write="--write" in sys.argv)
