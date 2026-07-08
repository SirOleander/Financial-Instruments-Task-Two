"""DEPRECATED shim — the real module is `fi.market` (`main_prices`)."""
import sys

from fi.market import *  # noqa: F401,F403
from fi.market import main_prices as main

if __name__ == "__main__":
    main(write="--write" in sys.argv)
